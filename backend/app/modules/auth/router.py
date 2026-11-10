import logging
from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.dependencies import get_current_user
from app.core.rate_limit import allow, check, client_ip, hit, record
from app.core.security import create_access_token
from app.db.session import get_db

from . import service
from .models import User
from .schemas import (
    ChangePasswordIn, ForgotPasswordIn, LoginIn, MessageOut, ResetPasswordIn,
    SignupIn, UserOut, VerifyEmailIn, GoogleConfigOut, GoogleLoginIn
)

router = APIRouter(prefix="/auth", tags=["Auth"])
COOKIE_NAME = "access_token"
log = logging.getLogger("security")

HOUR = timedelta(hours=1)
LOGIN_WINDOW = timedelta(minutes=15)
FORGOT_MESSAGE = "If an account exists for that email, we've sent a link to reset the password."


def _set_session_cookie(response: Response, user: User) -> None:
    response.set_cookie(
        COOKIE_NAME,
        create_access_token(str(user.id), user.token_version),
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
        max_age=settings.access_token_expire_minutes * 60,
        path="/",
    )


@router.post("/signup", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def signup(data: SignupIn, request: Request, response: Response, db: Session = Depends(get_db)):
    hit(db, "signup:ip", client_ip(request), limit=20, window=HOUR)
    try:
        user = service.create_user(db, data)
    except service.EmailTakenError:
        raise HTTPException(status.HTTP_409_CONFLICT, "An account with this email already exists")
    _set_session_cookie(response, user)
    return user


@router.post("/login", response_model=UserOut)
def login(data: LoginIn, request: Request, response: Response, db: Session = Depends(get_db)):
    ip, email = client_ip(request), data.email.lower()
    # Only failures count, so a legitimate login never uses up the allowance.
    check(db, "login:ip", ip, limit=30, window=LOGIN_WINDOW)
    check(db, "login:email", email, limit=10, window=LOGIN_WINDOW)
    user = service.authenticate(db, email, data.password)
    if not user:
        record(db, "login:ip", ip, window=LOGIN_WINDOW)
        record(db, "login:email", email, window=LOGIN_WINDOW)
        log.warning("failed login ip=%s", ip)
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Incorrect email or password")
    _set_session_cookie(response, user)
    return user


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(response: Response):
    response.delete_cookie(COOKIE_NAME, path="/")


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)):
    return user


@router.post("/verify-email", response_model=MessageOut)
def verify_email(data: VerifyEmailIn, request: Request, db: Session = Depends(get_db)):
    hit(db, "verify:ip", client_ip(request), limit=60, window=HOUR)
    service.verify_email(db, data.token)
    return MessageOut(message="Your email address is verified.")


@router.post("/resend-verification", response_model=MessageOut, status_code=status.HTTP_202_ACCEPTED)
def resend_verification(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    hit(db, "resend:user", str(user.id), limit=3, window=HOUR)
    if service.send_verification_email(db, user):
        db.commit()
        return MessageOut(message="We've sent a new verification link to your email.")
    return MessageOut(message="Your email address is already verified.")


@router.post("/forgot-password", response_model=MessageOut, status_code=status.HTTP_202_ACCEPTED)
def forgot_password(data: ForgotPasswordIn, request: Request, db: Session = Depends(get_db)):
    hit(db, "forgot:ip", client_ip(request), limit=20, window=HOUR)
    # Past 3 emails an hour to one address we quietly stop sending. The latest link stays valid,
    # so someone spamming a victim's address can neither flood their inbox nor lock them out.
    may_send = allow(db, "forgot:email", data.email.lower(), limit=3, window=HOUR)
    service.request_password_reset(db, data.email, may_send=may_send)
    return MessageOut(message=FORGOT_MESSAGE)


@router.post("/reset-password", response_model=MessageOut)
def reset_password(data: ResetPasswordIn, request: Request, db: Session = Depends(get_db)):
    hit(db, "reset:ip", client_ip(request), limit=30, window=HOUR)
    service.reset_password(db, data.token, data.new_password)
    return MessageOut(message="Your password has been changed. You can log in now.")


@router.post("/change-password", response_model=MessageOut)
def change_password(
    data: ChangePasswordIn,
    response: Response,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    window = LOGIN_WINDOW
    check(db, "change_pw:user", str(user.id), limit=5, window=window)
    try:
        service.change_password(db, user, data.current_password, data.new_password)
    except service.AuthError as exc:
        if exc.code == "incorrect_password":
            record(db, "change_pw:user", str(user.id), window=window)
        raise
    _set_session_cookie(response, user)      # this device stays signed in; every other one is signed out
    return MessageOut(message="Your password has been changed. Other devices have been signed out.")

@router.get("/google/config", response_model=GoogleConfigOut)
def google_config():
    return GoogleConfigOut(enabled=bool(settings.google_client_id), client_id=settings.google_client_id or None)


@router.post("/google", response_model=UserOut)
def google_login(data: GoogleLoginIn, request: Request, response: Response, db: Session = Depends(get_db)):
    if not settings.google_client_id:
        raise service.AuthError("google_not_configured", "Google sign-in isn't available.", 503)
    # Generous: many phones share one mobile-carrier address.
    hit(db, "google:ip", client_ip(request), limit=300, window=HOUR)
    user = service.google_sign_in(db, data.credential, data.accept_terms)
    _set_session_cookie(response, user)
    return user

@router.post("/accept-terms", response_model=UserOut)
def accept_terms(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return service.accept_terms(db, user)