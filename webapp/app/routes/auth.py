from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter(prefix="/auth", tags=["auth"])

VALID_USER = "admin"
VALID_PASS = "secret123"


class LoginRequest(BaseModel):
    username: str
    password: str


@router.post("/login")
async def login(body: LoginRequest):
    if body.username == VALID_USER and body.password == VALID_PASS:
        return {"status": "ok", "token": "demo-token"}
    raise HTTPException(status_code=401, detail="Invalid credentials")
