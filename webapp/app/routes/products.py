import random
import sqlite3

from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse

from app.db import get_connection

router = APIRouter(prefix="/products", tags=["products"])


@router.get("")
async def list_products():
    if random.random() < 0.03:
        raise HTTPException(status_code=500, detail="Inventory service unavailable")
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT id, name, price, description FROM products ORDER BY id"
        ).fetchall()
        return {"products": [dict(row) for row in rows]}
    finally:
        conn.close()


@router.get("/search")
async def search_products(q: str = ""):
    conn = get_connection()
    try:
        sql = (
            f"SELECT id, name, price, description FROM products "
            f"WHERE name LIKE '%{q}%' OR description LIKE '%{q}%'"
        )
        rows = conn.execute(sql).fetchall()
        return {"query": q, "results": [dict(row) for row in rows]}
    except sqlite3.Error as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    finally:
        conn.close()


@router.get("/preview", response_class=HTMLResponse)
async def preview_search(q: str = ""):
    return HTMLResponse(
        content=(
            "<!DOCTYPE html><html><head><title>Search preview</title></head>"
            f"<body><h1>Results for: {q}</h1>"
            "<p>Reflected term shown above for demo purposes.</p></body></html>"
        )
    )


@router.get("/{product_id}")
async def get_product(product_id: int):
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT id, name, price, description FROM products WHERE id = ?",
            (product_id,),
        ).fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="Product not found")
        return dict(row)
    finally:
        conn.close()
