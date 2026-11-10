from fastapi import APIRouter, Depends
from sqlmodel import func, select

from app.api.deps import SessionDep, require_permission
from app.authorization import Permission
from app.models import Item, User

router = APIRouter(prefix="/metrics", tags=["metrics"])


@router.get("/", dependencies=[Depends(require_permission(Permission.READ_METRICS))])
def read_metrics(session: SessionDep) -> dict[str, int]:
    return {
        "users": session.exec(select(func.count()).select_from(User)).one(),
        "items": session.exec(select(func.count()).select_from(Item)).one(),
    }
