from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.schemas.auth import MagicLinkRequest, TokenResponse, VerifyOTPRequest
from app.services.auth_service import request_magic_link, verify_magic_link, verify_otp

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/request-magic-link")
async def request_link(body: MagicLinkRequest, db: AsyncSession = Depends(get_db)):
    success = await request_magic_link(db, body.email)
    # Always return success to avoid leaking email existence
    return {"message": "If that email is valid, a verification code has been sent."}


@router.post("/verify-otp", response_model=TokenResponse)
async def otp_verify(body: VerifyOTPRequest, db: AsyncSession = Depends(get_db)):
    jwt_token = await verify_otp(db, body.email, body.code)
    if not jwt_token:
        raise HTTPException(status_code=400, detail="Invalid or expired code")
    return TokenResponse(access_token=jwt_token)


@router.get("/callback")
async def auth_callback(
    token: str = Query(...),
    redirect: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
):
    jwt_token = await verify_magic_link(db, token)
    if not jwt_token:
        raise HTTPException(status_code=400, detail="Invalid or expired magic link")

    # If redirect=shuvit, redirect to app deep link
    if redirect == "shuvit":
        return RedirectResponse(
            url=f"shuvit://auth?token={jwt_token}",
            status_code=302,
        )

    return TokenResponse(access_token=jwt_token)
