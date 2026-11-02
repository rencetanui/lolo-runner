from fastapi import FastAPI

app = FastAPI(title="Lolo Runner API")

@app.get("/health")
def health_check():
    return {"status": "ok"}