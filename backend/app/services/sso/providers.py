"""SSO provider abstraction — Azure AD / Google / Okta / SAML (Module 11 stub)."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional


@dataclass
class SSOIdentity:
    email: str
    external_id: str
    full_name: str | None = None
    provider: str = "unknown"


class SSOProvider(ABC):
    """Future SSO providers implement this interface. No live IdP calls yet."""

    name: str

    @abstractmethod
    def authorize_url(self, *, redirect_uri: str, state: str) -> str:
        ...

    @abstractmethod
    async def exchange_code(self, *, code: str, redirect_uri: str) -> SSOIdentity:
        ...


class AzureADProvider(SSOProvider):
    name = "azure_ad"

    def authorize_url(self, *, redirect_uri: str, state: str) -> str:
        return f"https://login.microsoftonline.com/common/oauth2/v2.0/authorize?state={state}&redirect_uri={redirect_uri}"

    async def exchange_code(self, *, code: str, redirect_uri: str) -> SSOIdentity:
        raise NotImplementedError("Azure AD SSO is not enabled yet")


class GoogleWorkspaceProvider(SSOProvider):
    name = "google_workspace"

    def authorize_url(self, *, redirect_uri: str, state: str) -> str:
        return f"https://accounts.google.com/o/oauth2/v2/auth?state={state}&redirect_uri={redirect_uri}"

    async def exchange_code(self, *, code: str, redirect_uri: str) -> SSOIdentity:
        raise NotImplementedError("Google Workspace SSO is not enabled yet")


class OktaProvider(SSOProvider):
    name = "okta"

    def authorize_url(self, *, redirect_uri: str, state: str) -> str:
        return f"https://okta.example/oauth2/v1/authorize?state={state}&redirect_uri={redirect_uri}"

    async def exchange_code(self, *, code: str, redirect_uri: str) -> SSOIdentity:
        raise NotImplementedError("Okta SSO is not enabled yet")


class SAMLProvider(SSOProvider):
    name = "saml"

    def authorize_url(self, *, redirect_uri: str, state: str) -> str:
        return f"/sso/saml/login?state={state}&redirect_uri={redirect_uri}"

    async def exchange_code(self, *, code: str, redirect_uri: str) -> SSOIdentity:
        raise NotImplementedError("SAML SSO is not enabled yet")


_PROVIDERS: dict[str, SSOProvider] = {
    p.name: p
    for p in (
        AzureADProvider(),
        GoogleWorkspaceProvider(),
        OktaProvider(),
        SAMLProvider(),
    )
}


def get_sso_provider(name: str) -> Optional[SSOProvider]:
    return _PROVIDERS.get(name)


def list_sso_providers() -> list[dict[str, str]]:
    return [
        {"name": p.name, "status": "planned", "enabled": "false"}
        for p in _PROVIDERS.values()
    ]
