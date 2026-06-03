import os
from fastapi import APIRouter, Header, HTTPException
from fastapi import FastAPI
from prometheus_fastapi_instrumentator import Instrumentator
from pydantic import BaseModel

from app.routes import admin, auth, products

app = FastAPI(title="Qahwa Shop API", version="1.0.0")
api = APIRouter(prefix="/api/v1")
api.include_router(auth.router)
api.include_router(products.router)
api.include_router(admin.router)
app.include_router(api)


class CartItem(BaseModel):
    product_id: int
    quantity: int = 1


@api.post("/cart")
async def add_to_cart(item: CartItem, authorization: str | None = Header(default=None)):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Authentication required")
    return {"status": "added", "product_id": item.product_id, "quantity": item.quantity}


@app.get("/admin")
async def admin_root():
    from fastapi import HTTPException

    raise HTTPException(status_code=403, detail="Forbidden")


@app.get("/health")
async def health():
    return {"status": "healthy", "instance": os.environ.get("HOSTNAME", "unknown")}


Instrumentator().instrument(app).expose(app, endpoint="/metrics")
