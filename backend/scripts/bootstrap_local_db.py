"""Bootstrap local PostgreSQL database and role for Module 2B testing."""

from __future__ import annotations

import asyncio

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine


async def main() -> None:
    admin = create_async_engine(
        "postgresql+asyncpg://postgres:postgres@127.0.0.1:5432/postgres",
        isolation_level="AUTOCOMMIT",
    )
    async with admin.connect() as conn:
        role = await conn.execute(
            text("SELECT 1 FROM pg_roles WHERE rolname = 'admin'")
        )
        if role.scalar() is None:
            await conn.execute(
                text("CREATE ROLE admin LOGIN PASSWORD 'admin_password'")
            )
            print("created role admin")
        else:
            await conn.execute(text("ALTER ROLE admin WITH PASSWORD 'admin_password'"))
            print("role admin ready")

        db = await conn.execute(
            text("SELECT 1 FROM pg_database WHERE datname = 'enterprise_ai'")
        )
        if db.scalar() is None:
            await conn.execute(text("CREATE DATABASE enterprise_ai OWNER admin"))
            print("created database enterprise_ai")
        else:
            print("database enterprise_ai exists")

    await admin.dispose()

    app_engine = create_async_engine(
        "postgresql+asyncpg://admin:admin_password@127.0.0.1:5432/enterprise_ai"
    )
    async with app_engine.connect() as conn:
        row = (await conn.execute(text("SELECT current_user, current_database()"))).first()
        print("connected as", row)
    await app_engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
