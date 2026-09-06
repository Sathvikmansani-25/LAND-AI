from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app import auth, services
from app.database import get_db
from app.ml import model as ml_model
from app.models import User
from app.schemas import SimulationInput

router = APIRouter(prefix="/api/projects", tags=["simulate"])


@router.post("/{project_id}/simulate")
def simulate(
    project_id: int,
    payload: SimulationInput,
    db: Session = Depends(get_db),
    current_user: User = Depends(auth.get_current_user),
):
    project = services.get_project_full(db, project_id)
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

    features = ml_model.project_to_features(project)
    result = ml_model.simulate(
        features,
        resolve_legal_disputes=payload.resolve_legal_disputes,
        release_compensation=payload.release_compensation,
        complete_pending_approvals=payload.complete_pending_approvals,
        reduce_approval_days_to=payload.reduce_approval_days_to,
    )

    actions = []
    if payload.resolve_legal_disputes:
        actions.append("resolving legal disputes")
    if payload.release_compensation:
        actions.append("releasing pending compensation")
    if payload.complete_pending_approvals:
        actions.append("completing all pending approvals")
    if payload.reduce_approval_days_to is not None:
        actions.append(f"capping the longest-pending approval at {payload.reduce_approval_days_to} days")

    if actions and result["risk_reduction_pct"] > 0:
        explanation = (
            f"{' and '.join(actions).capitalize()} could reduce this project's delay risk by "
            f"approximately {result['risk_reduction_pct']:.0f}% "
            f"({result['baseline_risk_score']*100:.0f}% → {result['new_risk_score']*100:.0f}%)."
        )
    elif actions:
        explanation = (
            f"{' and '.join(actions).capitalize()} has little effect on this project's risk score "
            f"({result['baseline_risk_score']*100:.0f}% → {result['new_risk_score']*100:.0f}%); "
            "other factors are the dominant drivers here."
        )
    else:
        explanation = "Select one or more actions to simulate their effect on this project's risk score."

    result["explanation"] = explanation
    return result
