from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app import auth, services
from app.database import get_db
from app.models import Project, User

router = APIRouter(prefix="/api/projects", tags=["projects"])


@router.get("")
def list_projects(
    state: str | None = None,
    district: str | None = None,
    project_type: str | None = None,
    search: str | None = None,
    risk_tier: str | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(auth.get_current_user),
):
    query = db.query(Project)
    if state:
        query = query.filter(Project.state == state)
    if district:
        query = query.filter(Project.district == district)
    if project_type:
        query = query.filter(Project.project_type == project_type)
    if search:
        query = query.filter(Project.name.ilike(f"%{search}%"))

    projects = [services.to_dict(r) for r in query.all()]
    risk_map = services.latest_risk_map(db, [p["id"] for p in projects])

    items = []
    for p in projects:
        ra = risk_map.get(p["id"])
        if risk_tier and (not ra or ra["risk_tier"] != risk_tier):
            continue
        items.append({
            "id": p["id"], "name": p["name"], "project_type": p["project_type"],
            "state": p["state"], "district": p["district"],
            "latitude": p["latitude"], "longitude": p["longitude"], "status": p["status"],
            "risk_score": ra["risk_score"] if ra else None,
            "risk_tier": ra["risk_tier"] if ra else None,
        })
    items.sort(key=lambda i: (i["risk_score"] is None, -(i["risk_score"] or 0)))
    return items


@router.get("/meta/filters")
def filter_options(db: Session = Depends(get_db), current_user: User = Depends(auth.get_current_user)):
    states = [r[0] for r in db.query(Project.state).distinct().order_by(Project.state).all()]
    districts = [r[0] for r in db.query(Project.district).distinct().order_by(Project.district).all()]
    types = [r[0] for r in db.query(Project.project_type).distinct().order_by(Project.project_type).all()]
    return {"states": states, "districts": districts, "project_types": types}


@router.get("/{project_id}")
def get_project(
    project_id: int, db: Session = Depends(get_db), current_user: User = Depends(auth.get_current_user)
):
    project = services.get_project_full(db, project_id)
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    return project
