from typing import Annotated

from pydantic import AfterValidator, BaseModel, EmailStr

NormalizedEmail = Annotated[EmailStr, AfterValidator(str.lower)]


class MagicLinkRequest(BaseModel):
    email: NormalizedEmail


class VerifyOTPRequest(BaseModel):
    email: NormalizedEmail
    code: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
