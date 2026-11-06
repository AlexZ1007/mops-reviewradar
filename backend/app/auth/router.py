from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.db import get_db
from app.models import Profile
from app.schemas import ProfileOut, ProfileUpdate

router = APIRouter(tags=["auth"])


@router.get("/me", response_model=ProfileOut)
def read_me(user: Profile = Depends(get_current_user)) -> Profile:
    return user


@router.patch("/me", response_model=ProfileOut)
def update_me(
    data: ProfileUpdate,
    user: Profile = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Profile:
    user.full_name = data.full_name.strip()
    db.commit()
    return user
