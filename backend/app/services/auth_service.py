import hashlib
import logging
import secrets
import string
from datetime import datetime, timedelta, timezone

import resend
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.user import MagicLinkToken, User
from app.utils.security import create_access_token

logger = logging.getLogger(__name__)


def _hash(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def _generate_otp() -> str:
    return "".join(secrets.choice(string.digits) for _ in range(6))


async def request_magic_link(db: AsyncSession, email: str) -> bool:
    """Generate and send a magic link + OTP code. Returns True on success."""
    # Rate limit: check for recent token
    recent = await db.execute(
        select(MagicLinkToken)
        .where(MagicLinkToken.email == email, MagicLinkToken.used == False)  # noqa: E712
        .order_by(MagicLinkToken.created_at.desc())
        .limit(1)
    )
    recent_token = recent.scalar_one_or_none()

    if recent_token:
        age = (datetime.now(timezone.utc) - recent_token.created_at.replace(tzinfo=timezone.utc)).total_seconds()
        if age < settings.MAGIC_LINK_RATE_LIMIT_SECONDS:
            return True  # Silently succeed to avoid leaking email existence

    raw_token = secrets.token_urlsafe(32)
    otp_code = _generate_otp()

    magic_link = MagicLinkToken(
        email=email,
        token_hash=_hash(raw_token),
        otp_hash=_hash(otp_code),
        expires_at=datetime.now(timezone.utc)
        + timedelta(minutes=settings.MAGIC_LINK_EXPIRE_MINUTES),
    )
    db.add(magic_link)
    await db.flush()

    callback_url = f"{settings.BASE_URL}/api/v1/auth/callback?token={raw_token}&redirect=shuvit"
    expire_min = settings.MAGIC_LINK_EXPIRE_MINUTES

    try:
        resend.api_key = settings.RESEND_API_KEY
        resend.Emails.send(
            {
                "from": settings.RESEND_FROM_EMAIL,
                "to": [email],
                "subject": f"Your Shuvit code: {otp_code}",
                "html": _build_email_html(otp_code, callback_url, expire_min),
            }
        )
    except Exception:
        logger.exception("Failed to send auth email")
        return False

    return True


async def verify_magic_link(db: AsyncSession, raw_token: str) -> str | None:
    """Verify a magic link token and return a JWT, or None if invalid."""
    token_hash = _hash(raw_token)
    now = datetime.now(timezone.utc)

    result = await db.execute(
        select(MagicLinkToken).where(
            MagicLinkToken.token_hash == token_hash,
            MagicLinkToken.used == False,  # noqa: E712
            MagicLinkToken.expires_at > now,
        )
    )
    magic_token = result.scalar_one_or_none()
    if not magic_token:
        return None

    return await _complete_auth(db, magic_token)


async def verify_otp(db: AsyncSession, email: str, code: str) -> str | None:
    """Verify a 6-digit OTP code and return a JWT, or None if invalid."""
    otp_hash = _hash(code)
    now = datetime.now(timezone.utc)

    result = await db.execute(
        select(MagicLinkToken).where(
            MagicLinkToken.email == email,
            MagicLinkToken.otp_hash == otp_hash,
            MagicLinkToken.used == False,  # noqa: E712
            MagicLinkToken.expires_at > now,
        )
    )
    magic_token = result.scalar_one_or_none()
    if not magic_token:
        return None

    return await _complete_auth(db, magic_token)


async def _complete_auth(db: AsyncSession, magic_token: MagicLinkToken) -> str:
    """Mark token used, upsert user, return JWT."""
    now = datetime.now(timezone.utc)
    magic_token.used = True

    user_result = await db.execute(
        select(User).where(User.email == magic_token.email)
    )
    user = user_result.scalar_one_or_none()

    if user is None:
        user = User(email=magic_token.email)
        db.add(user)
        await db.flush()

    user.last_login = now
    await db.flush()

    return create_access_token({"sub": str(user.id), "email": user.email})


def _build_email_html(otp_code: str, callback_url: str, expire_min: int) -> str:
    digits = "".join(
        f'<td style="width:44px;height:52px;text-align:center;font-size:28px;font-weight:700;font-family:\'SF Mono\',Menlo,Consolas,monospace;background:#f4f4f5;border-radius:10px;letter-spacing:0;">{d}</td>'
        for d in otp_code
    )

    return f"""
<!DOCTYPE html>
<html>
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1.0"></head>
<body style="margin:0;padding:0;background:#f8f8f8;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;">
<table width="100%" cellpadding="0" cellspacing="0" style="background:#f8f8f8;padding:40px 0;">
<tr><td align="center">
<table width="440" cellpadding="0" cellspacing="0" style="background:#ffffff;border-radius:16px;overflow:hidden;box-shadow:0 2px 8px rgba(0,0,0,0.06);">

  <!-- Header -->
  <tr><td style="background:#000;padding:28px 32px;text-align:center;">
    <span style="font-size:28px;font-weight:800;color:#fff;letter-spacing:-0.5px;">Shuvit</span>
  </td></tr>

  <!-- Body -->
  <tr><td style="padding:36px 32px 20px;">
    <p style="margin:0 0 6px;font-size:20px;font-weight:700;color:#111;">Your verification code</p>
    <p style="margin:0 0 28px;font-size:14px;color:#666;line-height:1.5;">Enter this code in the app to sign in. It expires in {expire_min} minutes.</p>

    <!-- OTP Code -->
    <table cellpadding="0" cellspacing="6" style="margin:0 auto 28px;">
      <tr>{digits}</tr>
    </table>

    <!-- Divider -->
    <table width="100%" cellpadding="0" cellspacing="0" style="margin:0 0 24px;">
      <tr>
        <td style="border-bottom:1px solid #eee;font-size:0;height:1px;">&nbsp;</td>
        <td style="padding:0 16px;white-space:nowrap;font-size:12px;color:#999;">or</td>
        <td style="border-bottom:1px solid #eee;font-size:0;height:1px;">&nbsp;</td>
      </tr>
    </table>

    <!-- Magic Link Button -->
    <table width="100%" cellpadding="0" cellspacing="0">
      <tr><td align="center">
        <a href="{callback_url}" style="display:inline-block;background:#000;color:#fff;padding:14px 36px;border-radius:10px;text-decoration:none;font-weight:600;font-size:15px;">Sign in with link</a>
      </td></tr>
    </table>
  </td></tr>

  <!-- Footer -->
  <tr><td style="padding:20px 32px 28px;">
    <p style="margin:0;font-size:12px;color:#aaa;text-align:center;line-height:1.5;">If you didn't request this, just ignore this email.<br>No account will be created.</p>
  </td></tr>

</table>
</td></tr>
</table>
</body>
</html>
"""
