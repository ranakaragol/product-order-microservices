from fastapi import FastAPI

from app.routers.auth import router as auth_router

app = FastAPI()
app.include_router(auth_router)


@app.get("/health")
def health():
    # Used by Kubernetes liveness/readiness probes.
    return {"status": "ok"}

