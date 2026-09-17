import asyncio

from sqlalchemy import select

from app.core.database import async_session_factory
from app.core.security import verify_password
from app.models.user import User


async def main():
    async with async_session_factory() as s:
        res = (await s.scalars(select(User))).all()
        print(f"Total users: {len(res)}")
        for u in res:
            v1 = verify_password("Password123!", u.password_hash)
            v2 = verify_password("FlagOps@Secure2026!", u.password_hash)
            msg = (
                f"Email: {u.email} | Active: {u.is_active} | "
                f"'Password123!': {v1} | 'FlagOps@Secure2026!': {v2}"
            )
            print(msg)


if __name__ == "__main__":
    asyncio.run(main())
