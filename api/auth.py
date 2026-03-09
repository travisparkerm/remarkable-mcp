"""
Google OAuth2 authentication routes.
JWT session tokens stored in httponly cookies.
"""

import os
from datetime import datetime, timedelta, timezone

from authlib.integrations.starlette_client import OAuth
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from jose import jwt
from sqlalchemy import select

from api.database import User, UserSettings, async_session

router = APIRouter(prefix="/auth", tags=["auth"])

# --- Configuration ---

GOOGLE_CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID", "")
GOOGLE_CLIENT_SECRET = os.environ.get("GOOGLE_CLIENT_SECRET", "")
APP_SECRET_KEY = os.environ.get("APP_SECRET_KEY", "change-me-in-production")
APP_URL = os.environ.get("APP_URL", "http://localhost:8000")
JWT_ALGORITHM = "HS256"
JWT_EXPIRY_DAYS = 30
COOKIE_NAME = "session"

# --- OAuth setup ---

oauth = OAuth()
oauth.register(
    name="google",
    client_id=GOOGLE_CLIENT_ID,
    client_secret=GOOGLE_CLIENT_SECRET,
    server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
    client_kwargs={"scope": "openid email profile"},
)


# --- Helpers ---


def create_session_token(user_id: int) -> str:
    """Create a signed JWT session token."""
    payload = {
        "sub": str(user_id),
        "exp": datetime.now(timezone.utc) + timedelta(days=JWT_EXPIRY_DAYS),
    }
    return jwt.encode(payload, APP_SECRET_KEY, algorithm=JWT_ALGORITHM)


async def get_current_user(request: Request) -> User:
    """Dependency: extract and validate session cookie, return User."""
    token = request.cookies.get(COOKIE_NAME)
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")

    try:
        payload = jwt.decode(token, APP_SECRET_KEY, algorithms=[JWT_ALGORITHM])
        user_id = int(payload["sub"])
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid session")

    async with async_session() as session:
        user = await session.get(User, user_id)
        if user is None:
            raise HTTPException(status_code=401, detail="User not found")
        return user


# --- Routes ---


@router.get("/login")
async def login(request: Request):
    """Redirect to Google OAuth2 login."""
    redirect_uri = f"{APP_URL}/auth/callback"
    return await oauth.google.authorize_redirect(request, redirect_uri)


@router.get("/callback")
async def callback(request: Request):
    """Handle Google OAuth2 callback."""
    token = await oauth.google.authorize_access_token(request)
    userinfo = token.get("userinfo")
    if not userinfo:
        raise HTTPException(status_code=400, detail="Failed to get user info")

    google_id = userinfo["sub"]
    email = userinfo["email"]
    name = userinfo.get("name")
    picture = userinfo.get("picture")

    async with async_session() as db:
        result = await db.execute(select(User).where(User.google_id == google_id))
        user = result.scalar_one_or_none()

        if user is None:
            user = User(
                email=email,
                name=name,
                picture=picture,
                google_id=google_id,
            )
            db.add(user)
            await db.flush()
            # Create default settings
            settings = UserSettings(user_id=user.id)
            db.add(settings)
            await db.commit()
            await db.refresh(user)
        else:
            # Update profile info
            user.name = name
            user.picture = picture
            user.email = email
            await db.commit()

    session_token = create_session_token(user.id)

    response = Response(status_code=302)
    response.headers["location"] = APP_URL
    response.set_cookie(
        COOKIE_NAME,
        session_token,
        httponly=True,
        samesite="lax",
        max_age=JWT_EXPIRY_DAYS * 86400,
        secure=APP_URL.startswith("https"),
    )
    return response


@router.get("/me")
async def me(user: User = Depends(get_current_user)):
    """Return current user info."""
    return {
        "id": user.id,
        "email": user.email,
        "name": user.name,
        "picture": user.picture,
    }


@router.post("/logout")
async def logout():
    """Clear the session cookie."""
    response = Response(status_code=200)
    response.delete_cookie(COOKIE_NAME)
    return response
