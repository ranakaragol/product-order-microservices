from fastapi import FastAPI
from bson import ObjectId
from app.routers.orders import router as orders_router

app = FastAPI()

app.include_router(orders_router)

@app.get("/")
def root():
    return {"message": "Order Service is running"}


@app.get("/health")
def health():
    # Used by Kubernetes liveness/readiness probes.
    return {"status": "ok"}

