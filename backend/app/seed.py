"""Seeds the database with synthetic users + live projects, then runs the
trained ML pipeline over every project to populate initial risk assessments
and early-warning alerts.

Run with:  python -m app.seed
(requires `python -m app.ml.train` to have been run first)

Runs against the direct/unpooled database connection (DATABASE_URL_UNPOOLED,
falling back to DATABASE_URL) rather than the pooled one the live API uses --
schema drop/create and a few thousand inserts are exactly the kind of
DDL-heavy, long-lived-transaction workload that behaves better outside a
transaction-mode connection pooler like Neon's PgBouncer. See README's
"Deploying to Vercel" section for how to obtain this connection string (for
example via `vercel env pull`) when running this against a remote database.
"""
import datetime as dt
import random

from sqlalchemy.orm import sessionmaker

from app.auth import hash_password
from app.database import now_iso, reset_schema, unpooled_engine
from app.ml import model as ml_model
from app.ml.data_generator import DEPARTMENTS, DISPUTE_TYPES, generate_live_projects
from app.models import Alert, Approval, LegalDispute, Project, RiskAssessment, User
from app import services

RNG = random.Random(123)


def seed_users(db):
    users = [
        dict(username="admin", full_name="System Administrator", password="admin123", role="admin"),
        dict(username="official", full_name="District Land Acquisition Officer", password="official123", role="official"),
    ]
    for u in users:
        db.add(
            User(
                username=u["username"],
                full_name=u["full_name"],
                hashed_password=hash_password(u["password"]),
                role=u["role"],
                created_at=now_iso(),
            )
        )
    db.commit()
    print(f"Seeded {len(users)} users (admin/admin123, official/official123)")


def seed_projects(db, n=260):
    raw_projects = generate_live_projects(n=n, seed=7)
    today = dt.date.today()

    project_ids = []
    for raw in raw_projects:
        start_date = today - dt.timedelta(days=RNG.randint(60, 1100))
        planned_duration = RNG.randint(240, 1300)
        deadline = start_date + dt.timedelta(days=planned_duration)
        status = "active" if deadline >= today else "delayed"

        project = Project(
            name=f"{raw['project_type']} - {raw['district']} Phase {RNG.randint(1, 3)}",
            project_type=raw["project_type"],
            state=raw["state"],
            district=raw["district"],
            latitude=raw["latitude"],
            longitude=raw["longitude"],
            land_area_hectares=raw["land_area_hectares"],
            affected_families=raw["affected_families"],
            ownership_complexity=raw["ownership_complexity"],
            compensation_total_inr=raw["compensation_total_inr"],
            compensation_disbursed_inr=raw["compensation_disbursed_inr"],
            departments_involved=raw["departments_involved"],
            start_date=start_date.isoformat(),
            deadline=deadline.isoformat(),
            status=status,
            district_historical_delay_rate=raw["district_historical_delay_rate"],
            created_at=now_iso(),
        )
        db.add(project)
        db.flush()  # populates project.id without committing the whole batch
        project_id = project.id
        project_ids.append(project_id)

        depts = DEPARTMENTS.copy()
        RNG.shuffle(depts)
        pending_bias = 0.25 + raw["district_historical_delay_rate"] * 0.5
        for j in range(raw["num_approvals"]):
            dept = depts[j % len(depts)]
            is_pending = RNG.random() < pending_bias
            if is_pending:
                days_pending = int(max(1, RNG.gauss(60 + raw["district_historical_delay_rate"] * 200, 45)))
                db.add(
                    Approval(
                        project_id=project_id,
                        department=dept,
                        status="pending",
                        days_pending=days_pending,
                        requested_at=(start_date + dt.timedelta(days=RNG.randint(0, 90))).isoformat(),
                    )
                )
            else:
                db.add(
                    Approval(
                        project_id=project_id,
                        department=dept,
                        status="approved",
                        days_pending=int(RNG.uniform(5, 60)),
                        requested_at=(start_date + dt.timedelta(days=RNG.randint(0, 90))).isoformat(),
                        resolved_at=(start_date + dt.timedelta(days=RNG.randint(91, 200))).isoformat(),
                    )
                )

        for _ in range(raw["num_disputes_active"]):
            db.add(
                LegalDispute(
                    project_id=project_id,
                    case_type=RNG.choice(DISPUTE_TYPES),
                    status="active",
                    filed_at=(start_date + dt.timedelta(days=RNG.randint(0, 300))).isoformat(),
                )
            )
        for _ in range(raw["num_disputes_resolved"]):
            db.add(
                LegalDispute(
                    project_id=project_id,
                    case_type=RNG.choice(DISPUTE_TYPES),
                    status="resolved",
                    filed_at=(start_date + dt.timedelta(days=RNG.randint(0, 200))).isoformat(),
                    resolved_at=(start_date + dt.timedelta(days=RNG.randint(201, 400))).isoformat(),
                )
            )

    db.commit()
    print(f"Seeded {len(project_ids)} projects")
    return project_ids


def compute_risk_and_alerts(db, project_ids):
    high = medium = low = 0
    alerts_created = 0

    for project_id in project_ids:
        project = services.get_project_full(db, project_id)
        features = ml_model.project_to_features(project)
        pred = ml_model.predict(features)
        top_factors = ml_model.explain(features)
        recs = ml_model.recommendations_for(top_factors)
        forecast = ml_model.forecast_30_60_90(features)

        db.add(
            RiskAssessment(
                project_id=project_id,
                risk_score=pred["risk_score"],
                risk_tier=pred["risk_tier"],
                predicted_delay_days=pred["predicted_delay_days"],
                top_factors=top_factors,
                recommendations=recs,
                forecast_30_60_90=forecast,
                computed_at=now_iso(),
            )
        )

        if pred["risk_tier"] == "high":
            high += 1
        elif pred["risk_tier"] == "medium":
            medium += 1
        else:
            low += 1

        # Early warning alerts: simulate a plausible "tier just changed" event
        # for a subset of medium/high risk projects, mirroring how the live
        # system fires alerts when a periodic re-score crosses a threshold.
        if pred["risk_tier"] in ("high", "medium") and RNG.random() < 0.35:
            prev_tier = "medium" if pred["risk_tier"] == "high" else "low"
            top_reason = top_factors[0]["factor"] if top_factors else "multiple factors"
            severity = "critical" if pred["risk_tier"] == "high" else "warning"
            db.add(
                Alert(
                    project_id=project_id,
                    severity=severity,
                    title=f"{project['name']} moved from {prev_tier.title()} to {pred['risk_tier'].title()} Risk",
                    message=(
                        f"Reason: {top_reason} is the leading risk driver "
                        f"(longest-pending approval: {project['max_approval_days_pending']} days). "
                        f"Suggested action: {recs[0] if recs else 'Review project status.'}"
                    ),
                    previous_tier=prev_tier,
                    new_tier=pred["risk_tier"],
                    acknowledged=False,
                    created_at=now_iso(),
                )
            )
            alerts_created += 1

    db.commit()
    print(f"Risk distribution -> high: {high}, medium: {medium}, low: {low}")
    print(f"Created {alerts_created} early-warning alerts")


def main():
    engine = unpooled_engine()
    print(f"Resetting schema on {engine.url.render_as_string(hide_password=True)} ...")
    reset_schema(bind=engine)

    session_factory = sessionmaker(bind=engine)
    db = session_factory()
    try:
        seed_users(db)
        project_ids = seed_projects(db, n=260)
        compute_risk_and_alerts(db, project_ids)
    finally:
        db.close()
    print("Seeding complete.")


if __name__ == "__main__":
    main()
