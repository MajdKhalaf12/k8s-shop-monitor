from fastapi import APIRouter, HTTPException

router = APIRouter(tags=["admin"])


@router.get("/admin")
async def admin_dashboard():
    raise HTTPException(status_code=403, detail="Forbidden")
