import random
from fastapi import APIRouter, HTTPException

router = APIRouter(prefix="/products", tags=["products"])

PRODUCTS = [
    {"id": 1, "name": "Espresso Beans", "price": 12.99},
    {"id": 2, "name": "Ceramic Mug", "price": 8.50},
    {"id": 3, "name": "Pour Over Kit", "price": 34.00},
    {"id": 4, "name": "Cold Brew Bottle", "price": 18.75},
]


@router.get("")
async def list_products():
    if random.random() < 0.03:
        raise HTTPException(status_code=500, detail="Inventory service unavailable")
    return {"products": PRODUCTS}


@router.get("/{product_id}")
async def get_product(product_id: int):
    for p in PRODUCTS:
        if p["id"] == product_id:
            return p
    raise HTTPException(status_code=404, detail="Product not found")
