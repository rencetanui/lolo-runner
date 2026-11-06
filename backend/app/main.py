from fastapi import FastAPI
from fastapi import Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

from app.modules.organizer.router import router as organizer_router
from app.modules.organizer.service import OrganizerError
from app.modules.events.router import router as events_router
from app.core.config import settings
from app.core.rate_limit import RateLimitError
from app.modules.auth.service import AuthError
from app.modules.auth.router import router as auth_router
from app.modules.runners.router import router as runners_router
from app.modules.registrations.router import router as registrations_router
from app.modules.registrations.service import RegistrationError
from app.modules.payments.router import router as payments_router
from app.modules.payments.service import PaymentError
from app.modules.admin.router import router as admin_router
from app.modules.refunds.router import router as refunds_router
from app.modules.refunds.service import RefundError


app = FastAPI(title="Lolo Runner API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(events_router, prefix="/api/v1")
app.include_router(auth_router, prefix="/api/v1")
app.include_router(runners_router, prefix="/api/v1")
app.include_router(registrations_router, prefix="/api/v1")
app.include_router(payments_router, prefix="/api/v1")
app.include_router(organizer_router, prefix="/api/v1")
app.include_router(admin_router, prefix="/api/v1")
app.include_router(refunds_router, prefix="/api/v1")

@app.exception_handler(RefundError)
async def refund_error_handler(request: Request, exc: RefundError):
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": {"code": exc.code, "message": exc.message}},
    )

@app.exception_handler(RateLimitError)
async def rate_limit_handler(request: Request, exc: RateLimitError):
    minutes = -(-exc.retry_after // 60)
    wait = f"{minutes} minute{'s' if minutes != 1 else ''}"
    return JSONResponse(
        status_code=429,
        headers={"Retry-After": str(exc.retry_after)},      # ← this line
        content={"detail": {"code": "rate_limited", "message": f"Too many attempts. Please try again in {wait}."}},
    )

@app.exception_handler(AuthError)
async def auth_error_handler(request: Request, exc: AuthError):
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": {"code": exc.code, "message": exc.message}},
    )
    
@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("Referrer-Policy", "no-referrer")
    path = request.url.path
    public = request.method == "GET" and path.startswith("/api/v1/events")
    if path.startswith("/api/v1") and not public:
        response.headers["Cache-Control"] = "no-store"     # personal data shouldn't sit in browser caches
    return response

@app.exception_handler(OrganizerError)
async def organizer_error_handler(request: Request, exc: OrganizerError):
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": {"code": exc.code, "message": exc.message}},
    )
    
@app.exception_handler(RegistrationError)
async def registration_error_handler(request: Request, exc: RegistrationError):
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": {"code": exc.code, "message": exc.message}},
    )
    
@app.exception_handler(PaymentError)
async def payment_error_handler(request: Request, exc: PaymentError):
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": {"code": exc.code, "message": exc.message}},
    )
    
@app.get("/health")
def health_check():
    return {"status": "ok"}