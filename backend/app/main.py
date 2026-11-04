from fastapi import FastAPI
from fastapi import Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

from app.modules.organizer.router import router as organizer_router
from app.modules.organizer.service import OrganizerError
from app.modules.events.router import router as events_router
from app.core.config import settings
from app.modules.auth.router import router as auth_router
from app.modules.runners.router import router as runners_router
from app.modules.registrations.router import router as registrations_router
from app.modules.registrations.service import RegistrationError
from app.modules.payments.router import router as payments_router
from app.modules.payments.service import PaymentError


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