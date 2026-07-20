"""Compatibility shim — prefer ``app.middlewares.jwt``."""

from app.middlewares.jwt import JWTAuthMiddleware, JWTMiddleware

__all__ = ["JWTAuthMiddleware", "JWTMiddleware"]
