from __future__ import annotations

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import decode_access_token
from app.db.models import CompanyMembership, User
from app.db.session import get_db

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login", auto_error=False)


def get_current_user(
    request: Request,
    token: str | None = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> User:
    session_cookie = request.cookies.get(settings.session_cookie_name) if request else None
    token = token or session_cookie
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")
    user_id = decode_access_token(token)
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    return user


def get_primary_membership(user: User, db: Session) -> CompanyMembership:
    membership = db.execute(select(CompanyMembership).where(CompanyMembership.user_id == user.id)).scalar_one_or_none()
    if not membership:
        raise HTTPException(status_code=403, detail="User is not attached to a company")
    return membership


def require_roles(*roles: str):
    def dependency(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> User:
        membership = get_primary_membership(user, db)
        if membership.role not in roles:
            raise HTTPException(status_code=403, detail="Insufficient permissions")
        return user

    return dependency
