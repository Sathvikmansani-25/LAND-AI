"""Shared feature engineering used identically at training time and at
inference time, so the live API predictions are produced by the exact same
transformation the model was trained on."""
import pandas as pd

from app.ml.data_generator import PROJECT_TYPES

NUMERIC_FEATURES = [
    "land_area_hectares",
    "affected_families",
    "ownership_complexity",
    "compensation_pct_disbursed",
    "num_active_disputes",
    "departments_involved",
    "pending_approvals",
    "district_historical_delay_rate",
    "max_approval_days_pending",
]

# Human-readable labels for SHAP output / dashboard display
FEATURE_LABELS = {
    "land_area_hectares": "Land area required",
    "affected_families": "Number of affected families",
    "ownership_complexity": "Land ownership complexity",
    "compensation_pct_disbursed": "Compensation NOT yet disbursed",
    "num_active_disputes": "Active legal disputes",
    "departments_involved": "Departments involved",
    "pending_approvals": "Pending approvals",
    "district_historical_delay_rate": "District's historical delay pattern",
    "max_approval_days_pending": "Longest-pending approval (days)",
}

PROJECT_TYPE_COLUMNS = [f"project_type_{t.replace(' ', '_')}" for t in PROJECT_TYPES]

ALL_FEATURE_COLUMNS = NUMERIC_FEATURES + PROJECT_TYPE_COLUMNS


def build_feature_matrix(df: pd.DataFrame) -> pd.DataFrame:
    """df must contain NUMERIC_FEATURES columns plus a 'project_type' column."""
    out = df.copy()

    # compensation_pct_disbursed is stored as "% disbursed"; the model is more
    # sensitive to what's OUTSTANDING, so we invert it into its own feature
    # for readability but keep training/inference consistent either way.
    for col in NUMERIC_FEATURES:
        if col not in out.columns:
            out[col] = 0

    dummies = pd.get_dummies(out["project_type"], prefix="project_type")
    for col in PROJECT_TYPE_COLUMNS:
        if col not in dummies.columns:
            dummies[col] = 0
    dummies = dummies[PROJECT_TYPE_COLUMNS]

    matrix = pd.concat([out[NUMERIC_FEATURES].reset_index(drop=True), dummies.reset_index(drop=True)], axis=1)
    return matrix[ALL_FEATURE_COLUMNS]
