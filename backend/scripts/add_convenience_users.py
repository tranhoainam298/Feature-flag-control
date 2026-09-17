import asyncio

from sqlalchemy import select

from app.core.database import async_session_factory
from app.core.security import hash_password
from app.models.enums import MemberRole
from app.models.organization import Membership, Organization
from app.models.user import User


async def add_convenience_users():
    async with async_session_factory() as session:
        org = await session.scalar(
            select(Organization).where(Organization.slug == "global-core-infrastructure")
        )
        if not org:
            org = await session.scalar(select(Organization))

        users_to_ensure = [
            {
                "email": "admin@flagops.dev",
                "full_name": "FlagOps Admin",
                "password": "Password123!",
                "role": MemberRole.OWNER,
            },
            {
                "email": "dev@flagops.dev",
                "full_name": "FlagOps Developer",
                "password": "Password123!",
                "role": MemberRole.DEVELOPER,
            },
        ]

        for u_data in users_to_ensure:
            existing = await session.scalar(select(User).where(User.email == u_data["email"]))
            if existing:
                existing.password_hash = hash_password(u_data["password"])
                existing.is_active = True
                user_obj = existing
                print(f"Updated password for existing user: {u_data['email']}")
            else:
                user_obj = User(
                    email=u_data["email"],
                    password_hash=hash_password(u_data["password"]),
                    full_name=u_data["full_name"],
                    is_active=True,
                )
                session.add(user_obj)
                await session.flush()
                print(f"Created user: {u_data['email']}")

            if org:
                membership = await session.scalar(
                    select(Membership).where(
                        Membership.organization_id == org.id, Membership.user_id == user_obj.id
                    )
                )
                if not membership:
                    membership = Membership(
                        organization_id=org.id, user_id=user_obj.id, role=u_data["role"]
                    )
                    session.add(membership)
                    print(
                        f"Added user {u_data['email']} to org {org.name} as {u_data['role'].value}"
                    )
                else:
                    membership.role = u_data["role"]

        await session.commit()
        print("Convenience users ensured successfully!")


if __name__ == "__main__":
    asyncio.run(add_convenience_users())
