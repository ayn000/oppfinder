import asyncio

from fastapi import APIRouter, Cookie, Depends, HTTPException, Response
from sqlalchemy.orm import Session as DbSession

from ..auth import (
    COOKIE_NAME,
    create_session,
    destroy_session,
    get_current_user,
    get_db,
    verify_password,
)
from ..models import User
from ..schemas import LoginIn, UserOut

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/login", response_model=UserOut)
async def login(payload: LoginIn, response: Response, db: DbSession = Depends(get_db)):
    user = db.query(User).filter(User.username == payload.username.strip().lower()).one_or_none()
    if user is None or not verify_password(payload.password, user.password_hash):
        await asyncio.sleep(0.8)  # slow down brute force
        raise HTTPException(status_code=401, detail="Identifiants invalides")
    create_session(db, user, response)
    return UserOut(username=user.username, display_name=user.display_name)


@router.post("/logout", status_code=204)
def logout(
    response: Response,
    db: DbSession = Depends(get_db),
    token: str | None = Cookie(default=None, alias=COOKIE_NAME),
):
    destroy_session(db, token, response)


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)):
    return UserOut(username=user.username, display_name=user.display_name)
