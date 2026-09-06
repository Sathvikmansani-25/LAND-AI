"""Trains the LandGuard AI risk models on synthetic data and saves artifacts.

Run with:  python -m app.ml.train

Uses XGBoost (the originally-proposed model backend) as a hard dependency --
see requirements.txt. If you need a network-restricted/no-XGBoost fallback,
the previous scikit-learn GradientBoosting version is preserved in git
history, but this rewrite intentionally drops that fallback in favor of the
one real stack.
"""
import os
import joblib
from sklearn.model_selection import train_test_split
from sklearn.metrics import roc_auc_score, mean_absolute_error
from xgboost import XGBClassifier, XGBRegressor

from app.ml.data_generator import generate_training_dataset
from app.ml.features import build_feature_matrix, ALL_FEATURE_COLUMNS
from app.config import settings

BACKEND = "xgboost"


def make_classifier():
    return XGBClassifier(
        n_estimators=200, max_depth=4, learning_rate=0.08,
        subsample=0.9, colsample_bytree=0.9, eval_metric="logloss", random_state=42,
    )


def make_regressor():
    return XGBRegressor(
        n_estimators=200, max_depth=4, learning_rate=0.08,
        subsample=0.9, colsample_bytree=0.9, random_state=42,
    )


def main():
    print(f"Model backend: {BACKEND}")
    print("Generating synthetic training data...")
    df = generate_training_dataset(n=4000, seed=42)
    X = build_feature_matrix(df)
    y_class = df["delayed"]
    y_reg = df["delay_days"]

    X_train, X_test, yc_train, yc_test, yr_train, yr_test = train_test_split(
        X, y_class, y_reg, test_size=0.2, random_state=42, stratify=y_class
    )

    print(f"Training classifier on {len(X_train)} rows, {X.shape[1]} features...")
    clf = make_classifier()
    clf.fit(X_train, yc_train)
    auc = roc_auc_score(yc_test, clf.predict_proba(X_test)[:, 1])
    print(f"  Classifier ROC-AUC on holdout: {auc:.3f}")

    print("Training delay-days regressor...")
    reg = make_regressor()
    reg.fit(X_train, yr_train)
    mae = mean_absolute_error(yr_test, reg.predict(X_test))
    print(f"  Regressor MAE on holdout: {mae:.1f} days")

    os.makedirs(settings.model_dir, exist_ok=True)
    joblib.dump(clf, os.path.join(settings.model_dir, "risk_classifier.joblib"))
    joblib.dump(reg, os.path.join(settings.model_dir, "delay_regressor.joblib"))
    joblib.dump(ALL_FEATURE_COLUMNS, os.path.join(settings.model_dir, "feature_columns.joblib"))

    metrics = {"classifier_auc": float(auc), "regressor_mae_days": float(mae),
               "n_train": len(X_train), "backend": BACKEND}
    joblib.dump(metrics, os.path.join(settings.model_dir, "metrics.joblib"))
    print(f"Saved model artifacts to {settings.model_dir}")
    print(metrics)


if __name__ == "__main__":
    main()
