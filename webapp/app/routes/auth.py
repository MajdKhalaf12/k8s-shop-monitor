import sqlite3

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.db import get_connection

router = APIRouter(prefix="/auth", tags=["auth"])


class LoginRequest(BaseModel):
    username: str
    password: str


@router.post("/login")
async def login(body: LoginRequest):
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT username FROM users WHERE username = ? AND password = ?",
            (body.username, body.password),
        ).fetchone()
    except sqlite3.Error as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    finally:
        conn.close()

    if row is not None:
        return {"status": "ok", "token": "demo-token"}
    raise HTTPException(status_code=401, detail="Invalid credentials")
