"""Domain enumerations for ORM models and application logic."""

from __future__ import annotations

from enum import StrEnum


class RoleName(StrEnum):
    """Canonical role identifiers used across authorization checks."""

    ADMIN = "admin"
    MANAGER = "manager"
    EMPLOYEE = "employee"
