from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.modules.events.router import router as events_router
from app.core.config import settings
from app.modules.auth.router import router as auth_router
from app.modules.runners.router import router as runners_router

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

@app.get("/health")
def health_check():
    return {"status": "ok"}