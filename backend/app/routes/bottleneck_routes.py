from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app import auth, services
from app.database import get_db
from app.models import Project, User

router = APIRouter(prefix="/api/bottleneck", tags=["bottleneck"])


@router.get("")
def global_bottleneck(db: Session = Depends(get_db), current_user: User = Depends(auth.get_current_user)):
    approvals = services.get_all_approvals(db)
    return services.build_bottleneck_report(approvals, project_id=None)


@router.get("/project/{project_id}")
def project_bottleneck(
    project_id: int, db: Session = Depends(get_db), current_user: User = Depends(auth.get_current_user)
):
    exists = db.query(Project.id).filter(Project.id == project_id).first()
    if not exists:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    approvals = services.get_approvals(db, project_id)
    return services.build_bottleneck_report(approvals, project_id=project_id)
