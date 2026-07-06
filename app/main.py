from fastapi import FastAPI
from app.routes.health import router as health_router
from app.routes.items import router as items_router

app = FastAPI(title="FastAPI AKS Jenkins", version="1.0.0")
app.include_router(health_router)
app.include_router(items_router, prefix="/api")
