from collections import defaultdict

from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from app import auth, services
from app.database import get_db
from app.models import Alert, LegalDispute, Project, User

router = APIRouter(prefix="/api", tags=["dashboard"])


@router.get("/heatmap/districts")
def heatmap_districts(db: Session = Depends(get_db), current_user: User = Depends(auth.get_current_user)):
    projects = [services.to_dict(r) for r in db.query(Project).all()]
    risk_map = services.latest_risk_map(db)

    buckets = defaultdict(lambda: {"total": 0, "high": 0, "medium": 0, "low": 0, "scores": [], "lats": [], "lngs": []})
    for p in projects:
        key = (p["state"], p["district"])
        b = buckets[key]
        b["total"] += 1
        b["lats"].append(p["latitude"])
        b["lngs"].append(p["longitude"])
        ra = risk_map.get(p["id"])
        if ra:
            b["scores"].append(ra["risk_score"])
            b[ra["risk_tier"]] += 1

    result = []
    for (state, district), b in buckets.items():
        result.append({
            "state": state, "district": district, "total_projects": b["total"],
            "high_risk": b["high"], "medium_risk": b["medium"], "low_risk": b["low"],
            "avg_risk_score": round(sum(b["scores"]) / len(b["scores"]), 3) if b["scores"] else 0.0,
            "lat": sum(b["lats"]) / len(b["lats"]), "lng": sum(b["lngs"]) / len(b["lngs"]),
        })
    result.sort(key=lambda d: -d["high_risk"])
    return result


@router.get("/dashboard/summary")
def dashboard_summary(db: Session = Depends(get_db), current_user: User = Depends(auth.get_current_user)):
    projects = [services.to_dict(r) for r in db.query(Project).all()]
    risk_map = services.latest_risk_map(db)

    high = medium = low = 0
    comp_pending = 0.0
    for p in projects:
        ra = risk_map.get(p["id"])
        if ra:
            if ra["risk_tier"] == "high":
                high += 1
            elif ra["risk_tier"] == "medium":
                medium += 1
            else:
                low += 1
        comp_pending += max(0.0, p["compensation_total_inr"] - p["compensation_disbursed_inr"])

    critical_alerts = (
        db.query(func.count(Alert.id)).filter(Alert.severity == "critical", Alert.acknowledged.is_(False)).scalar()
    )
    active_legal_cases = db.query(func.count(LegalDispute.id)).filter(LegalDispute.status == "active").scalar()

    return {
        "total_projects": len(projects), "high_risk": high, "medium_risk": medium, "low_risk": low,
        "critical_alerts": critical_alerts,
        "total_compensation_pending_inr": round(comp_pending, 2),
        "total_active_legal_cases": active_legal_cases,
    }
