import asyncio
from app.core.database import async_session_factory
from app.models.user import User
from app.core.security import verify_password
from sqlalchemy import select

async def main():
    async with async_session_factory() as s:
        emails = [
            "security.admin@flagops.internal",
            "lead.engineer@flagops.internal",
            "platform.dev@flagops.internal",
            "compliance.auditor@flagops.internal",
        ]
        for email in emails:
            u = await s.scalar(select(User).where(User.email == email))
            if u:
                valid = verify_password("FlagOps@Secure2026!", u.password_hash)
                print(f"User found: {u.email} | Password 'FlagOps@Secure2026!' valid: {valid}")
            else:
                print(f"User NOT found: {email}")

if __name__ == "__main__":
    asyncio.run(main())
