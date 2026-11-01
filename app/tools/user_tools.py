from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.database.models import User
from app.tools import ToolError

MAX_RESULTS = 100


def _serialize(user: User) -> dict:
    return {
        "id": user.id,
        "name": user.name,
        "email": user.email,
        "role": user.role,
        "is_active": user.is_active,
    }


def get_user(db: Session, user_id: int) -> dict:
    user = db.get(User, user_id)
    if user is None:
        raise ToolError(f"No user found with id {user_id}.")
    return _serialize(user)


def get_all_users(db: Session) -> dict:
    total = db.scalar(select(func.count()).select_from(User)) or 0
    users = db.scalars(select(User).order_by(User.id).limit(MAX_RESULTS)).all()
    return {
        "total": total,
        "returned": len(users),
        "truncated": total > len(users),
        "users": [_serialize(u) for u in users],
    }


def search_user(db: Session, name: str) -> dict:
    query = (
        select(User)
        .where(User.name.icontains(name.strip(), autoescape=True))
        .order_by(User.name)
        .limit(MAX_RESULTS)
    )
    users = db.scalars(query).all()
    return {"query": name, "count": len(users), "users": [_serialize(u) for u in users]}
