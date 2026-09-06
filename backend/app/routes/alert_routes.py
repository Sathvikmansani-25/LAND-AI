from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app import auth, services
from app.database import get_db
from app.models import Alert, User

router = APIRouter(prefix="/api/alerts", tags=["alerts"])


@router.get("")
def list_alerts(
    severity: str | None = None,
    acknowledged: bool | None = None,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: User = Depends(auth.get_current_user),
):
    query = db.query(Alert)
    if severity:
        query = query.filter(Alert.severity == severity)
    if acknowledged is not None:
        query = query.filter(Alert.acknowledged.is_(acknowledged))
    rows = query.order_by(Alert.created_at.desc()).limit(limit).all()
    return [services.to_dict(r) for r in rows]


@router.post("/{alert_id}/acknowledge")
def acknowledge(
    alert_id: int, db: Session = Depends(get_db), current_user: User = Depends(auth.get_current_user)
):
    row = db.query(Alert).filter(Alert.id == alert_id).first()
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Alert not found")
    row.acknowledged = True
    db.commit()
    db.refresh(row)
    return services.to_dict(row)
