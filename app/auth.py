import hashlib
import hmac
import secrets
from datetime import timedelta

from fastapi import Cookie, Depends, HTTPException, Response
from sqlalchemy.orm import Session as DbSession

from .config import settings
from .database import SessionLocal
from .models import AuthSession, User, utcnow

COOKIE_NAME = "opp_session"
_PBKDF2_ITERATIONS = 600_000


def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), _PBKDF2_ITERATIONS)
    return f"pbkdf2${_PBKDF2_ITERATIONS}${salt}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        _, iterations, salt, expected = stored.split("$")
        digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), int(iterations))
        return hmac.compare_digest(digest.hex(), expected)
    except (ValueError, TypeError):
        return False


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def create_session(db: DbSession, user: User, response: Response) -> None:
    token = secrets.token_urlsafe(32)
    lifetime = timedelta(days=settings.session_lifetime_days)
    db.query(AuthSession).filter(AuthSession.expires_at < utcnow()).delete()
    db.add(AuthSession(token=token, user_id=user.id, expires_at=utcnow() + lifetime))
    db.commit()
    response.set_cookie(
        COOKIE_NAME,
        token,
        max_age=int(lifetime.total_seconds()),
        httponly=True,
        samesite="lax",
        secure=settings.cookie_secure,
        path="/",
    )


def destroy_session(db: DbSession, token: str | None, response: Response) -> None:
    if token:
        db.query(AuthSession).filter(AuthSession.token == token).delete()
        db.commit()
    response.delete_cookie(COOKIE_NAME, path="/")


def get_current_user(
    db: DbSession = Depends(get_db),
    token: str | None = Cookie(default=None, alias=COOKIE_NAME),
) -> User:
    if not token:
        raise HTTPException(status_code=401, detail="Non authentifié")
    session = db.get(AuthSession, token)
    if session is None or session.expires_at < utcnow():
        raise HTTPException(status_code=401, detail="Session expirée")
    user = db.get(User, session.user_id)
    if user is None:
        raise HTTPException(status_code=401, detail="Utilisateur inconnu")
    return user
