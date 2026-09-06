from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app import auth, services
from app.database import get_db
from app.models import User

router = APIRouter(prefix="/api/projects", tags=["risk"])


@router.get("/{project_id}/risk")
def get_risk(
    project_id: int, db: Session = Depends(get_db), current_user: User = Depends(auth.get_current_user)
):
    project = services.get_project_full(db, project_id)
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

    ra = services.get_latest_risk(db, project_id)
    if not ra:
        ra = services.recompute_risk(db, project)
    return ra


@router.post("/{project_id}/recompute")
def recompute(
    project_id: int, db: Session = Depends(get_db), current_user: User = Depends(auth.get_current_user)
):
    project = services.get_project_full(db, project_id)
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    return services.recompute_risk(db, project)
