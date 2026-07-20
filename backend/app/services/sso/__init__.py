"""SSO package — abstraction only (Module 11)."""

from app.services.sso.providers import (
    SSOIdentity,
    SSOProvider,
    get_sso_provider,
    list_sso_providers,
)

__all__ = [
    "SSOIdentity",
    "SSOProvider",
    "get_sso_provider",
    "list_sso_providers",
]
