"""Token-related API schemas."""

from __future__ import annotations

from pydantic import BaseModel, Field


class TokenPair(BaseModel):
    """Access + refresh token pair returned after auth."""

    access_token: str = Field(..., examples=["eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."])
    refresh_token: str = Field(..., examples=["dGhpcyBpcyBhIHJlZnJlc2gtdG9rZW4..."])
    token_type: str = Field(default="bearer", examples=["bearer"])
    expires_in: int = Field(
        ...,
        description="Access token lifetime in seconds",
        examples=[1800],
    )


# Backward-compatible alias
TokenResponse = TokenPair
