from fastapi import FastAPI
from app.modules.events.router import router as events_router


app = FastAPI(title="Lolo Runner API")
app.include_router(events_router, prefix="/api/v1")

@app.get("/health")
def health_check():
    return {"status": "ok"}