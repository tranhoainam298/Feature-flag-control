import uuid

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app

BASE = "http://test"
PREFIX = "/api/v1/auth"


def _unique_email() -> str:
    return f"test-auth-{uuid.uuid4().hex[:12]}@example.com"


STRONG_PASSWORD = "Str0ngP@ss1"


@pytest.fixture
async def client():
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
        yield c


@pytest.fixture
async def registered_user(client: AsyncClient) -> dict:
    """Register a user and return the login tokens."""
    email = _unique_email()
    await client.post(
        f"{PREFIX}/register",
        json={"email": email, "password": STRONG_PASSWORD, "full_name": "Test User"},
    )
    resp = await client.post(
        f"{PREFIX}/login",
        json={"email": email, "password": STRONG_PASSWORD},
    )
    data = resp.json()
    data["email"] = email
    return data


# ─── REGISTER ───


@pytest.mark.asyncio
async def test_register_success(client: AsyncClient) -> None:
    email = _unique_email()
    resp = await client.post(
        f"{PREFIX}/register",
        json={"email": email, "password": STRONG_PASSWORD, "full_name": "New User"},
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["email"] == email
    assert body["full_name"] == "New User"
    assert body["is_active"] is True
    # Password must NEVER appear in response
    assert "password" not in body
    assert "password_hash" not in body


@pytest.mark.asyncio
async def test_register_duplicate_email_409(client: AsyncClient) -> None:
    email = _unique_email()
    await client.post(
        f"{PREFIX}/register",
        json={"email": email, "password": STRONG_PASSWORD, "full_name": "U1"},
    )
    resp = await client.post(
        f"{PREFIX}/register",
        json={"email": email, "password": STRONG_PASSWORD, "full_name": "U2"},
    )
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "CONFLICT"


@pytest.mark.asyncio
async def test_register_invalid_email_422(client: AsyncClient) -> None:
    resp = await client.post(
        f"{PREFIX}/register",
        json={"email": "not-an-email", "password": STRONG_PASSWORD, "full_name": "Bad"},
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_register_weak_password_422(client: AsyncClient) -> None:
    email = _unique_email()
    # Too short, no uppercase, no digit
    resp = await client.post(
        f"{PREFIX}/register",
        json={"email": email, "password": "short", "full_name": "Weak"},
    )
    assert resp.status_code == 422


# ─── LOGIN ───


@pytest.mark.asyncio
async def test_login_success(client: AsyncClient) -> None:
    email = _unique_email()
    await client.post(
        f"{PREFIX}/register",
        json={"email": email, "password": STRONG_PASSWORD, "full_name": "Login User"},
    )
    resp = await client.post(
        f"{PREFIX}/login",
        json={"email": email, "password": STRONG_PASSWORD},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert "access_token" in body
    assert "refresh_token" in body
    assert body["token_type"] == "bearer"
    # Password must NOT appear in token response
    assert "password" not in body


@pytest.mark.asyncio
async def test_login_wrong_password_401(client: AsyncClient) -> None:
    email = _unique_email()
    await client.post(
        f"{PREFIX}/register",
        json={"email": email, "password": STRONG_PASSWORD, "full_name": "U"},
    )
    resp = await client.post(
        f"{PREFIX}/login",
        json={"email": email, "password": "WrongPass1"},
    )
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "UNAUTHORIZED"


@pytest.mark.asyncio
async def test_login_nonexistent_user_401_same_message(client: AsyncClient) -> None:
    """Error message must be identical for wrong-password and nonexistent-user."""
    email_exists = _unique_email()
    await client.post(
        f"{PREFIX}/register",
        json={"email": email_exists, "password": STRONG_PASSWORD, "full_name": "U"},
    )
    wrong_pw = await client.post(
        f"{PREFIX}/login",
        json={"email": email_exists, "password": "WrongPass1"},
    )
    no_user = await client.post(
        f"{PREFIX}/login",
        json={"email": "noone@example.com", "password": STRONG_PASSWORD},
    )
    assert wrong_pw.status_code == 401
    assert no_user.status_code == 401
    # Identical error message — prevents user enumeration
    assert wrong_pw.json()["error"]["message"] == no_user.json()["error"]["message"]


# ─── TOKEN VALIDATION ───


@pytest.mark.asyncio
async def test_expired_token_401(client: AsyncClient) -> None:
    """A mangled/expired token must return 401."""
    resp = await client.get(
        f"{PREFIX}/me",
        headers={"Authorization": "Bearer expired.token.value"},
    )
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "UNAUTHORIZED"


@pytest.mark.asyncio
async def test_wrong_signature_token_401(client: AsyncClient) -> None:
    """A token signed with a different key must be rejected."""
    import jwt

    bad_token = jwt.encode({"sub": "fake-id", "type": "access"}, "wrong-secret", algorithm="HS256")
    resp = await client.get(
        f"{PREFIX}/me",
        headers={"Authorization": f"Bearer {bad_token}"},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_no_token_401(client: AsyncClient) -> None:
    resp = await client.get(f"{PREFIX}/me")
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "UNAUTHORIZED"


# ─── REFRESH ───


@pytest.mark.asyncio
async def test_refresh_success(registered_user: dict, client: AsyncClient) -> None:
    resp = await client.post(
        f"{PREFIX}/refresh",
        json={"refresh_token": registered_user["refresh_token"]},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert "access_token" in body
    assert "refresh_token" in body
    # New tokens should differ from old (rotation)
    assert body["refresh_token"] != registered_user["refresh_token"]


@pytest.mark.asyncio
async def test_refresh_revoked_token_401(registered_user: dict, client: AsyncClient) -> None:
    """After logout, the old refresh token is revoked and must be rejected."""
    # Logout revokes the refresh token
    await client.post(
        f"{PREFIX}/logout",
        headers={"Authorization": f"Bearer {registered_user['access_token']}"},
    )
    # Try using the old refresh token
    resp = await client.post(
        f"{PREFIX}/refresh",
        json={"refresh_token": registered_user["refresh_token"]},
    )
    assert resp.status_code == 401


# ─── ME ───


@pytest.mark.asyncio
async def test_me_success(registered_user: dict, client: AsyncClient) -> None:
    resp = await client.get(
        f"{PREFIX}/me",
        headers={"Authorization": f"Bearer {registered_user['access_token']}"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["email"] == registered_user["email"]
    # Password must NEVER appear
    assert "password" not in body
    assert "password_hash" not in body


# ─── RBAC: VIEWER WRITE BLOCKED ───


@pytest.mark.asyncio
async def test_viewer_cannot_write_403(client: AsyncClient) -> None:
    """A user with VIEWER role trying a write endpoint gets 403.

    Since we don't have CRUD endpoints yet, we test the require_role dependency
    directly by importing it and calling through a mock endpoint.
    """
    from uuid import uuid4

    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
    from sqlalchemy.pool import NullPool

    from app.core.config import settings
    from app.core.security import create_access_token, hash_password
    from app.models.enums import MemberRole
    from app.models.organization import Membership, Organization
    from app.models.user import User

    test_engine = create_async_engine(settings.DATABASE_URL, poolclass=NullPool)
    session_factory = async_sessionmaker(bind=test_engine, expire_on_commit=False)

    async with session_factory() as session:
        # Create a viewer user
        org = Organization(name="RBAC Org", slug=f"rbac-{uuid4().hex[:8]}")
        session.add(org)
        await session.flush()

        user = User(
            email=f"viewer-{uuid4().hex[:8]}@example.com",
            password_hash=hash_password(STRONG_PASSWORD),
            full_name="Viewer User",
        )
        session.add(user)
        await session.flush()

        membership = Membership(user_id=user.id, organization_id=org.id, role=MemberRole.VIEWER)
        session.add(membership)
        await session.commit()

        # Get an access token for this viewer
        access_token = create_access_token(str(user.id))

    # Test via the permissions check — we register a temp endpoint
    from fastapi import Depends

    from app.core.permissions import require_role

    @app.post(
        "/test-rbac-write",
        dependencies=[Depends(require_role(MemberRole.DEVELOPER))],
    )
    async def _test_write() -> dict:
        return {"ok": True}

    resp = await client.post(
        "/test-rbac-write",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "FORBIDDEN"

    # Cleanup: remove the temp route
    app.routes[:] = [r for r in app.routes if getattr(r, "path", "") != "/test-rbac-write"]


# ─── PASSWORD NEVER IN RESPONSE ───


@pytest.mark.asyncio
async def test_password_never_in_any_response(client: AsyncClient) -> None:
    """Verify password/password_hash never appears in register, login, me, or refresh responses."""
    email = _unique_email()
    pw = STRONG_PASSWORD

    reg = await client.post(
        f"{PREFIX}/register",
        json={"email": email, "password": pw, "full_name": "PW Check"},
    )
    login = await client.post(f"{PREFIX}/login", json={"email": email, "password": pw})
    tokens = login.json()

    me = await client.get(
        f"{PREFIX}/me",
        headers={"Authorization": f"Bearer {tokens['access_token']}"},
    )
    refresh = await client.post(
        f"{PREFIX}/refresh", json={"refresh_token": tokens["refresh_token"]}
    )

    for resp, name in [(reg, "register"), (login, "login"), (me, "me"), (refresh, "refresh")]:
        text = resp.text
        assert pw not in text, f"Raw password found in {name} response"
        assert "password_hash" not in text, f"password_hash found in {name} response"
