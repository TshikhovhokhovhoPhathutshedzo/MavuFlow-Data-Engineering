from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.dependencies import get_db
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    get_password_hash,
    verify_password,
)
from app.models.auth_session import AuthSession
from app.models.user import User
from app.schemas.auth import RefreshTokenRequest, TokenResponse, UserCreate, UserLogin, UserOut

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])
security = HTTPBearer()


def _issue_tokens(user: User, session_id: str) -> TokenResponse:
    return TokenResponse(
        access_token=create_access_token(user.email, session_id),
        refresh_token=create_refresh_token(user.email, session_id),
        user=UserOut.model_validate(user),
    )


def _start_session(db: Session, user: User) -> TokenResponse:
    db.query(User).filter(User.id == user.id).with_for_update().first()
    db.query(AuthSession).filter(AuthSession.user_id == user.id, AuthSession.is_active.is_(True)).update(
        {AuthSession.is_active: False}, synchronize_session=False
    )
    session_id = str(uuid4())
    db.add(AuthSession(user_id=user.id, session_id=session_id, is_active=True))
    db.commit()
    return _issue_tokens(user, session_id)


def _require_active_session(db: Session, user: User, session_id: object) -> str:
    if not isinstance(session_id, str) or not db.query(AuthSession).filter(
        AuthSession.user_id == user.id,
        AuthSession.session_id == session_id,
        AuthSession.is_active.is_(True),
    ).first():
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Session expired; please sign in again")
    return session_id


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
def register_user(payload: UserCreate, db: Session = Depends(get_db)) -> TokenResponse:
    normalized_email = payload.email.lower()
    existing_user = db.query(User).filter(User.email == normalized_email).first()
    if existing_user:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="User is already registered")

    user = User(
        email=normalized_email,
        full_name=payload.full_name.strip(),
        password_hash=get_password_hash(payload.password),
        is_active=True,
        is_verified=False,
        role="user",
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    return _start_session(db, user)


@router.post("/login", response_model=TokenResponse)
def login_user(payload: UserLogin, db: Session = Depends(get_db)) -> TokenResponse:
    normalized_email = payload.email.lower()
    user = db.query(User).filter(User.email == normalized_email).first()
    if not user or not user.is_active or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password")

    return _start_session(db, user)


def get_authenticated_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
) -> User:
    token = credentials.credentials
    claims = decode_token(token, "access")
    email = claims.get("sub")
    if not isinstance(email, str):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token payload")
    user = db.query(User).filter(User.email == email).first()
    if not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    _require_active_session(db, user, claims.get("sid"))
    return user


@router.get("/me", response_model=UserOut)
def get_current_user_profile(current_user: User = Depends(get_authenticated_user)) -> User:
    return current_user


@router.post("/refresh", response_model=TokenResponse)
def refresh_access_token(payload: RefreshTokenRequest, db: Session = Depends(get_db)) -> TokenResponse:
    claims = decode_token(payload.refresh_token, "refresh")
    email = claims.get("sub")
    if not isinstance(email, str):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token")
    user = db.query(User).filter(User.email == email).first()
    if not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token")

    session_id = _require_active_session(db, user, claims.get("sid"))
    return _issue_tokens(user, session_id)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
) -> None:
    claims = decode_token(credentials.credentials, "access")
    session_id = claims.get("sid")
    if isinstance(session_id, str):
        db.query(AuthSession).filter(AuthSession.session_id == session_id).update(
            {AuthSession.is_active: False}, synchronize_session=False
        )
        db.commit()
