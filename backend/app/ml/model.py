"""Inference layer: loads trained artifacts once and exposes
predict / explain / forecast / simulate used by the API routes.

Explainability: uses the `shap` library's TreeExplainer (true Shapley-value
attributions) against the trained XGBoost classifier -- the
originally-proposed explainability stack. SHAP is a hard dependency here
(see requirements.txt); the previous built-in counterfactual/occlusion
explainer fallback is preserved in git history but intentionally dropped by
this rewrite in favor of the one real stack.
"""
import os
import functools
import copy

import joblib
import numpy as np
import pandas as pd
import shap

from app.config import settings
from app.ml.features import build_feature_matrix, FEATURE_LABELS
from app.ml import recommendation


class ModelBundle:
    def __init__(self):
        self.clf = joblib.load(os.path.join(settings.model_dir, "risk_classifier.joblib"))
        self.reg = joblib.load(os.path.join(settings.model_dir, "delay_regressor.joblib"))
        self.feature_columns = joblib.load(os.path.join(settings.model_dir, "feature_columns.joblib"))
        self.explainer = shap.TreeExplainer(self.clf)


@functools.lru_cache(maxsize=1)
def get_bundle() -> ModelBundle:
    return ModelBundle()


def risk_tier_from_score(score: float) -> str:
    if score >= settings.risk_high_threshold:
        return "high"
    if score >= settings.risk_medium_threshold:
        return "medium"
    return "low"


def project_to_features(project: dict) -> dict:
    """`project` is a dict with the derived fields already computed
    (see services.derive_project_fields)."""
    return {
        "land_area_hectares": project["land_area_hectares"],
        "affected_families": project["affected_families"],
        "ownership_complexity": project["ownership_complexity"],
        "compensation_pct_disbursed": project["compensation_pct_disbursed"],
        "num_active_disputes": project["active_legal_disputes"],
        "departments_involved": project["departments_involved"],
        "pending_approvals": project["pending_approvals"],
        "district_historical_delay_rate": project["district_historical_delay_rate"],
        "max_approval_days_pending": project["max_approval_days_pending"],
        "project_type": project["project_type"],
    }


def _row_from_features(features: dict) -> pd.DataFrame:
    df = pd.DataFrame([features])
    return build_feature_matrix(df)


def predict(features: dict) -> dict:
    bundle = get_bundle()
    row = _row_from_features(features)
    risk_score = float(bundle.clf.predict_proba(row)[0, 1])
    delay_days = float(max(0, bundle.reg.predict(row)[0]))
    return {
        "risk_score": round(risk_score, 4),
        "risk_tier": risk_tier_from_score(risk_score),
        "predicted_delay_days": round(delay_days, 1),
    }


def _label_for_column(col: str, row: pd.DataFrame) -> str | None:
    if col.startswith("project_type_"):
        if row.iloc[0][col] == 0:
            return None  # only show the active project type, not every dummy column
        return f"Project type: {col.replace('project_type_', '').replace('_', ' ')}"
    return FEATURE_LABELS.get(col, col)


def _explain_shap(row: pd.DataFrame, top_n: int) -> list[dict]:
    bundle = get_bundle()
    shap_values = bundle.explainer.shap_values(row)
    # Cast every value to a plain Python float up front (not just raw_score
    # below) -- these get stored in a JSON column, and a lingering
    # numpy.float32/float64 scalar anywhere in that dict makes the stdlib
    # json encoder raise "Object of type float32 is not JSON serializable"
    # (round() on a numpy scalar returns another numpy scalar, not a float,
    # so doing the cast only on raw_score and rounding contribution_pct
    # afterwards was not enough).
    values = [float(v) for v in np.array(shap_values).reshape(-1)]
    total_abs = sum(abs(v) for v in values) or 1.0

    contributions = []
    for col, val in zip(row.columns, values):
        label = _label_for_column(col, row)
        if label is None:
            continue
        contributions.append({
            "factor": label,
            "raw_score": val,
            "contribution_pct": round(abs(val) / total_abs * 100, 1),
            "direction": "increases" if val > 0 else "decreases",
        })
    contributions.sort(key=lambda c: abs(c["raw_score"]), reverse=True)
    return contributions[:top_n]


def explain(features: dict, top_n: int = 5) -> list[dict]:
    row = _row_from_features(features)
    return _explain_shap(row, top_n)


def forecast_30_60_90(features: dict) -> dict:
    """Projects how risk evolves if nothing changes, by advancing the
    'longest-pending approval' clock forward in time (the model then
    re-scores the project as if that approval kept sitting unresolved)."""
    out = {}
    for horizon in (0, 30, 60, 90):
        f = copy.deepcopy(features)
        f["max_approval_days_pending"] = f["max_approval_days_pending"] + horizon
        result = predict(f)
        out[str(horizon)] = result["risk_score"]
    return out


def simulate(features: dict, resolve_legal_disputes=False, release_compensation=False,
             complete_pending_approvals=False, reduce_approval_days_to: int | None = None) -> dict:
    baseline = predict(features)

    sim_features = copy.deepcopy(features)
    if resolve_legal_disputes:
        sim_features["num_active_disputes"] = 0
    if release_compensation:
        sim_features["compensation_pct_disbursed"] = 1.0
    if complete_pending_approvals:
        sim_features["pending_approvals"] = 0
        sim_features["max_approval_days_pending"] = 0
    if reduce_approval_days_to is not None:
        sim_features["max_approval_days_pending"] = min(
            sim_features["max_approval_days_pending"], reduce_approval_days_to
        )

    new = predict(sim_features)
    reduction_pct = round((baseline["risk_score"] - new["risk_score"]) / max(baseline["risk_score"], 1e-6) * 100, 1)

    return {
        "baseline_risk_score": baseline["risk_score"],
        "new_risk_score": new["risk_score"],
        "risk_reduction_pct": reduction_pct,
        "baseline_tier": baseline["risk_tier"],
        "new_tier": new["risk_tier"],
    }


def recommendations_for(top_factors: list[dict]) -> list[str]:
    return recommendation.get_recommendations(top_factors)
