import asyncio
from app.core.database import async_session_factory
from app.services.auth import login_user
from app.core.exceptions import FlagOpsError

async def test():
    async with async_session_factory() as db:
        try:
            res = await login_user(db, "admin@flagops.dev", "Password123!")
            print("Login SUCCESS:", res)
        except FlagOpsError as e:
            print(f"Login FAILED: code={e.code}, msg={e.message}, status={e.status_code}")
        except Exception as e:
            print("Login ERROR:", e)

if __name__ == "__main__":
    asyncio.run(test())
