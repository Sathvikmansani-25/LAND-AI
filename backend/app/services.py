"""Shared business logic: turning ORM rows into the derived project view the
ML layer and API expect, computing/recomputing risk, and alerts. Rewritten
from raw sqlite3 SQL to SQLAlchemy ORM queries against PostgreSQL.

Functions here still return/accept plain dicts (not ORM objects) wherever
the original code did, since the ML layer (app/ml/model.py) and the chatbot
layers were written against plain dict access (`project["name"]`, etc.) --
`to_dict` is the one place that boundary is crossed.
"""
from collections import defaultdict

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database import now_iso
from app.models import Alert, Approval, LegalDispute, Project, RiskAssessment
from app.ml import model as ml_model


def to_dict(obj) -> dict:
    """Converts a SQLAlchemy ORM instance to a plain dict of its columns
    (unchanged if `obj` is already a dict)."""
    if isinstance(obj, dict):
        return dict(obj)
    return {c.key: getattr(obj, c.key) for c in obj.__table__.columns}


def get_approvals(db: Session, project_id: int) -> list[dict]:
    rows = db.query(Approval).filter(Approval.project_id == project_id).all()
    return [to_dict(r) for r in rows]


def get_disputes(db: Session, project_id: int) -> list[dict]:
    rows = db.query(LegalDispute).filter(LegalDispute.project_id == project_id).all()
    return [to_dict(r) for r in rows]


def get_all_approvals(db: Session) -> list[dict]:
    return [to_dict(r) for r in db.query(Approval).all()]


def get_approvals_for_projects(db: Session, project_ids: list[int]) -> list[dict]:
    if not project_ids:
        return []
    return [to_dict(r) for r in db.query(Approval).filter(Approval.project_id.in_(project_ids)).all()]


def derive_project_fields(project_row, approvals: list[dict], disputes: list[dict]) -> dict:
    project = to_dict(project_row)
    total = project["compensation_total_inr"]
    disbursed = project["compensation_disbursed_inr"]
    project["compensation_pct_disbursed"] = round(disbursed / total, 4) if total else 1.0
    project["active_legal_disputes"] = sum(1 for d in disputes if d["status"] == "active")
    pending = [a for a in approvals if a["status"] == "pending"]
    project["pending_approvals"] = len(pending)
    project["max_approval_days_pending"] = max((a["days_pending"] for a in pending), default=0)
    project["approvals"] = approvals
    project["disputes"] = disputes
    return project


def get_project_full(db: Session, project_id: int) -> dict | None:
    row = db.query(Project).filter(Project.id == project_id).first()
    if not row:
        return None
    approvals = get_approvals(db, project_id)
    disputes = get_disputes(db, project_id)
    return derive_project_fields(row, approvals, disputes)


def latest_risk_map(db: Session, project_ids: list[int] | None = None) -> dict:
    """One most-recent RiskAssessment per project_id, keyed by project_id."""
    latest_subq = (
        db.query(
            RiskAssessment.project_id.label("project_id"),
            func.max(RiskAssessment.computed_at).label("max_computed_at"),
        )
        .group_by(RiskAssessment.project_id)
        .subquery()
    )
    rows = (
        db.query(RiskAssessment)
        .join(
            latest_subq,
            (RiskAssessment.project_id == latest_subq.c.project_id)
            & (RiskAssessment.computed_at == latest_subq.c.max_computed_at),
        )
        .all()
    )
    result = {}
    for r in rows:
        d = to_dict(r)
        if project_ids is None or d["project_id"] in project_ids:
            result[d["project_id"]] = d
    return result


def get_latest_risk(db: Session, project_id: int) -> dict | None:
    row = (
        db.query(RiskAssessment)
        .filter(RiskAssessment.project_id == project_id)
        .order_by(RiskAssessment.computed_at.desc())
        .first()
    )
    if not row:
        return None
    return to_dict(row)


def recompute_risk(db: Session, project: dict) -> dict:
    features = ml_model.project_to_features(project)
    pred = ml_model.predict(features)
    top_factors = ml_model.explain(features)
    recs = ml_model.recommendations_for(top_factors)
    forecast = ml_model.forecast_30_60_90(features)

    previous = get_latest_risk(db, project["id"])
    computed_at = now_iso()

    db.add(
        RiskAssessment(
            project_id=project["id"],
            risk_score=pred["risk_score"],
            risk_tier=pred["risk_tier"],
            predicted_delay_days=pred["predicted_delay_days"],
            top_factors=top_factors,
            recommendations=recs,
            forecast_30_60_90=forecast,
            computed_at=computed_at,
        )
    )

    tier_rank = {"low": 0, "medium": 1, "high": 2}
    if previous and tier_rank.get(pred["risk_tier"], 0) > tier_rank.get(previous["risk_tier"], 0):
        top_reason = top_factors[0]["factor"] if top_factors else "multiple factors"
        db.add(
            Alert(
                project_id=project["id"],
                severity="critical" if pred["risk_tier"] == "high" else "warning",
                title=f"{project['name']} moved from {previous['risk_tier'].title()} to {pred['risk_tier'].title()} Risk",
                message=(
                    f"Reason: {top_reason} is the leading risk driver. "
                    f"Suggested action: {recs[0] if recs else 'Review project status.'}"
                ),
                previous_tier=previous["risk_tier"],
                new_tier=pred["risk_tier"],
                acknowledged=False,
                created_at=now_iso(),
            )
        )

    db.commit()

    return {
        "project_id": project["id"],
        "risk_score": pred["risk_score"],
        "risk_tier": pred["risk_tier"],
        "predicted_delay_days": pred["predicted_delay_days"],
        "top_factors": top_factors,
        "recommendations": recs,
        "forecast_30_60_90": forecast,
        "computed_at": computed_at,
    }


def build_bottleneck_report(approvals: list[dict], project_id: int | None) -> dict:
    pending = [a for a in approvals if a["status"] == "pending"]
    buckets: dict[str, dict] = defaultdict(lambda: {"count": 0, "total_days": 0})
    for a in pending:
        b = buckets[a["department"]]
        b["count"] += 1
        b["total_days"] += a["days_pending"]

    total_days_all = sum(b["total_days"] for b in buckets.values()) or 1

    departments = []
    for dept, b in buckets.items():
        departments.append({
            "department": dept,
            "pending_approvals_count": b["count"],
            "avg_days_pending": round(b["total_days"] / b["count"], 1) if b["count"] else 0.0,
            "total_days_pending": b["total_days"],
            "share_of_total_delay_pct": round(b["total_days"] / total_days_all * 100, 1),
        })
    departments.sort(key=lambda d: -d["share_of_total_delay_pct"])

    primary = departments[0]["department"] if departments else None
    if primary:
        narrative = (
            f"Bottleneck: {primary}. {departments[0]['share_of_total_delay_pct']:.0f}% of current pending-approval "
            f"delay is associated with {primary} ({departments[0]['pending_approvals_count']} pending approval(s), "
            f"averaging {departments[0]['avg_days_pending']:.0f} days each)."
        )
    else:
        narrative = "No pending approvals -- no departmental bottleneck detected."

    return {"project_id": project_id, "departments": departments, "primary_bottleneck": primary, "narrative": narrative}
