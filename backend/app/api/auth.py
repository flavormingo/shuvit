from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.redis import is_rate_limited
from app.schemas.auth import MagicLinkRequest, TokenResponse, VerifyOTPRequest
from app.services.auth_service import request_magic_link, verify_magic_link, verify_otp

router = APIRouter(prefix="/auth", tags=["auth"])

REQUESTS_PER_IP_PER_HOUR = 20
VERIFY_ATTEMPTS_PER_IP_PER_HOUR = 30


def _client_ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"


@router.post("/request-magic-link")
async def request_link(
    body: MagicLinkRequest, request: Request, db: AsyncSession = Depends(get_db)
):
    key = f"otp_request_ip:{_client_ip(request)}"
    if await is_rate_limited(key, REQUESTS_PER_IP_PER_HOUR, 3600):
        raise HTTPException(status_code=429, detail="Too many requests. Try again later.")

    if not await request_magic_link(db, body.email):
        raise HTTPException(status_code=503, detail="Couldn't send your code. Try again shortly.")
    return {"message": "If that email is valid, a verification code has been sent."}


@router.post("/verify-otp", response_model=TokenResponse)
async def otp_verify(
    body: VerifyOTPRequest, request: Request, db: AsyncSession = Depends(get_db)
):
    key = f"otp_verify_ip:{_client_ip(request)}"
    if await is_rate_limited(key, VERIFY_ATTEMPTS_PER_IP_PER_HOUR, 3600):
        raise HTTPException(status_code=429, detail="Too many attempts. Try again later.")

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

    if redirect == "shuvit":
        return RedirectResponse(
            url=f"shuvit://auth?token={jwt_token}",
            status_code=302,
        )

    return TokenResponse(access_token=jwt_token)
