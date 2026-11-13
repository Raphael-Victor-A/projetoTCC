from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import FeedbackGroup, User
from app.schemas import Token, UserCreate, UserOut, normalize_login
from app.security import create_access_token, get_current_user, hash_password, verify_password

router = APIRouter(prefix="/auth", tags=["auth"])


def _find_by_login(db: Session, login: str) -> User | None:
    # Comparacao sem diferenciar maiusculas: contas antigas podem ter sido
    # gravadas com letra maiuscula no e-mail.
    return db.query(User).filter(func.lower(User.email) == normalize_login(login)).first()


@router.post("/register", response_model=Token, status_code=status.HTTP_201_CREATED)
def register(payload: UserCreate, db: Session = Depends(get_db)):
    if _find_by_login(db, payload.email):
        raise HTTPException(status_code=400, detail="Esse usuario ja esta em uso")

    # Todo usuario novo comeca no modo socratico. Trocar o modo e exclusivo
    # do admin (PATCH /admin/students/{id}/group).
    user = User(
        email=payload.email,
        hashed_password=hash_password(payload.password),
        group=FeedbackGroup.SOCRATICO,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    token = create_access_token(subject=str(user.id))
    return Token(access_token=token)


@router.post("/login", response_model=Token)
def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    # form_data.username aceita nome de usuario ou e-mail.
    user = _find_by_login(db, form_data.username)
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Usuario ou senha invalidos")

    token = create_access_token(subject=str(user.id))
    return Token(access_token=token)


@router.get("/me", response_model=UserOut)
def me(current_user: User = Depends(get_current_user)):
    return current_user
