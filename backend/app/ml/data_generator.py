"""Synthetic data generator for LandGuard AI.

Generates realistic Indian land-acquisition project data (no real government
data is used or required). Produces both:
  - a large historical training set (with known delayed/not-delayed and
    delay_days outcomes) used to train the ML models, and
  - a smaller "live" set of currently active projects (no outcome yet) that
    gets seeded into the running app's database.
"""
import random
import numpy as np

PROJECT_TYPES = [
    "Highway Expansion",
    "Metro Rail",
    "Irrigation Canal",
    "Power Transmission Line",
    "Industrial Corridor",
    "Railway Line Doubling",
    "Airport Expansion",
    "Urban Housing Scheme",
    "Port Connectivity Road",
    "Dam / Reservoir",
]

DEPARTMENTS = [
    "Revenue Department",
    "Legal Department",
    "Environment Department",
    "Forest Department",
    "Finance Department",
    "Urban Planning Department",
    "PWD",
    "Panchayati Raj Department",
]

DISPUTE_TYPES = [
    "Compensation amount dispute",
    "Title ownership dispute",
    "Tribal land rights (FRA) case",
    "Court stay order",
    "Boundary demarcation dispute",
    "Multiple claimants dispute",
]

# state -> (districts -> approx (lat, lng)), a representative (non-exhaustive) set
STATE_DISTRICTS = {
    "Telangana": {
        "Hyderabad": (17.3850, 78.4867),
        "Rangareddy": (17.2100, 78.4747),
        "Medchal": (17.6293, 78.4816),
        "Warangal": (17.9689, 79.5941),
        "Nizamabad": (18.6725, 78.0941),
    },
    "Maharashtra": {
        "Mumbai Suburban": (19.0760, 72.8777),
        "Pune": (18.5204, 73.8567),
        "Nagpur": (21.1458, 79.0882),
        "Thane": (19.2183, 72.9781),
        "Aurangabad": (19.8762, 75.3433),
    },
    "Uttar Pradesh": {
        "Lucknow": (26.8467, 80.9462),
        "Noida (Gautam Buddh Nagar)": (28.5355, 77.3910),
        "Varanasi": (25.3176, 82.9739),
        "Kanpur Nagar": (26.4499, 80.3319),
        "Agra": (27.1767, 78.0081),
    },
    "Tamil Nadu": {
        "Chennai": (13.0827, 80.2707),
        "Coimbatore": (11.0168, 76.9558),
        "Madurai": (9.9252, 78.1198),
        "Tiruchirappalli": (10.7905, 78.7047),
    },
    "Karnataka": {
        "Bengaluru Urban": (12.9716, 77.5946),
        "Mysuru": (12.2958, 76.6394),
        "Belagavi": (15.8497, 74.4977),
        "Mangaluru (Dakshina Kannada)": (12.9141, 74.8560),
    },
    "Gujarat": {
        "Ahmedabad": (23.0225, 72.5714),
        "Surat": (21.1702, 72.8311),
        "Vadodara": (22.3072, 73.1812),
        "Rajkot": (22.3039, 70.8022),
    },
    "West Bengal": {
        "Kolkata": (22.5726, 88.3639),
        "Howrah": (22.5958, 88.2636),
        "North 24 Parganas": (22.6169, 88.4272),
        "Darjeeling": (27.0410, 88.2663),
    },
    "Rajasthan": {
        "Jaipur": (26.9124, 75.7873),
        "Jodhpur": (26.2389, 73.0243),
        "Udaipur": (24.5854, 73.7125),
        "Kota": (25.2138, 75.8648),
    },
    "Madhya Pradesh": {
        "Bhopal": (23.2599, 77.4126),
        "Indore": (22.7196, 75.8577),
        "Jabalpur": (23.1815, 79.9864),
    },
    "Odisha": {
        "Khordha": (20.1809, 85.6206),
        "Cuttack": (20.4625, 85.8828),
        "Sundargarh": (22.1167, 84.0333),
    },
    "Bihar": {
        "Patna": (25.5941, 85.1376),
        "Gaya": (24.7955, 85.0002),
        "Muzaffarpur": (26.1225, 85.3906),
    },
    "Kerala": {
        "Ernakulam": (9.9816, 76.2999),
        "Thiruvananthapuram": (8.5241, 76.9366),
        "Kozhikode": (11.2588, 75.7804),
    },
}


def _rng_jitter(rng: random.Random, val: float, spread: float) -> float:
    return val + rng.uniform(-spread, spread)


def _sigmoid(x: float) -> float:
    return 1.0 / (1.0 + np.exp(-x))


def _district_base_delay_rate(rng: random.Random, state: str, district: str) -> float:
    """A stable-per-district 'historical delay rate' derived from a seeded hash,
    so the same district always gets roughly the same base rate."""
    seed = abs(hash((state, district))) % (10**6)
    local_rng = random.Random(seed)
    return round(local_rng.uniform(0.15, 0.75), 3)


def sample_raw_project(rng: random.Random) -> dict:
    state = rng.choice(list(STATE_DISTRICTS.keys()))
    district = rng.choice(list(STATE_DISTRICTS[state].keys()))
    base_lat, base_lng = STATE_DISTRICTS[state][district]

    project_type = rng.choice(PROJECT_TYPES)
    land_area = round(rng.uniform(2, 450), 1)  # hectares
    affected_families = int(rng.uniform(5, 1200) * (1 + land_area / 300))
    ownership_complexity = rng.choices([1, 2, 3, 4, 5], weights=[15, 25, 30, 20, 10])[0]

    compensation_total = round(affected_families * rng.uniform(150000, 2200000), 2)
    # disbursement pct skewed - many projects genuinely stuck at partial disbursement
    disb_pct = rng.choices(
        population=[rng.uniform(0, 0.2), rng.uniform(0.2, 0.6), rng.uniform(0.6, 0.95), rng.uniform(0.95, 1.0)],
        weights=[20, 30, 30, 20],
    )[0]
    compensation_disbursed = round(compensation_total * disb_pct, 2)

    num_disputes_active = rng.choices([0, 1, 2, 3, 4], weights=[35, 30, 20, 10, 5])[0]
    num_disputes_resolved = rng.choices([0, 1, 2], weights=[60, 30, 10])[0]

    departments_involved = rng.randint(2, len(DEPARTMENTS))
    num_approvals = rng.randint(departments_involved, departments_involved + 3)

    district_delay_rate = _district_base_delay_rate(rng, state, district)

    return dict(
        state=state,
        district=district,
        latitude=round(_rng_jitter(rng, base_lat, 0.35), 5),
        longitude=round(_rng_jitter(rng, base_lng, 0.35), 5),
        project_type=project_type,
        land_area_hectares=land_area,
        affected_families=affected_families,
        ownership_complexity=ownership_complexity,
        compensation_total_inr=compensation_total,
        compensation_disbursed_inr=compensation_disbursed,
        num_disputes_active=num_disputes_active,
        num_disputes_resolved=num_disputes_resolved,
        departments_involved=departments_involved,
        num_approvals=num_approvals,
        district_historical_delay_rate=district_delay_rate,
    )


def compute_latent_features(raw: dict) -> dict:
    """Derive model-ready numeric features from a raw sampled project."""
    comp_pct = (
        raw["compensation_disbursed_inr"] / raw["compensation_total_inr"]
        if raw["compensation_total_inr"]
        else 1.0
    )
    return dict(
        land_area_hectares=raw["land_area_hectares"],
        affected_families=raw["affected_families"],
        ownership_complexity=raw["ownership_complexity"],
        compensation_pct_disbursed=comp_pct,
        num_active_disputes=raw["num_disputes_active"],
        departments_involved=raw["departments_involved"],
        pending_approvals=raw["num_approvals"],
        district_historical_delay_rate=raw["district_historical_delay_rate"],
    )


def latent_risk_probability(features: dict, approval_days_pending: float, rng: random.Random) -> float:
    """Ground-truth generating process (used only to label synthetic training
    data — the ML model is trained to *approximate* this from observed
    features, which is why it can then explain real predictions). Coefficients
    are calibrated so the resulting project population spreads across
    low/medium/high risk in realistic proportions (roughly 55/30/15%),
    rather than saturating almost everything into "high risk"."""
    logit = (
        -3.6
        + 1.8 * (1 - features["compensation_pct_disbursed"])
        + 0.28 * features["num_active_disputes"]
        + 0.15 * features["ownership_complexity"]
        + 0.06 * features["departments_involved"]
        + 1.3 * features["district_historical_delay_rate"]
        + 0.03 * features["pending_approvals"]
        + 0.0035 * approval_days_pending
        + 0.0004 * features["land_area_hectares"]
        + rng.gauss(0, 0.4)
    )
    return float(np.clip(_sigmoid(logit), 0.01, 0.99))


def generate_training_dataset(n: int = 4000, seed: int = 42):
    """Returns a pandas DataFrame of historical projects with labels."""
    import pandas as pd

    rng = random.Random(seed)
    rows = []
    for _ in range(n):
        raw = sample_raw_project(rng)
        features = compute_latent_features(raw)
        approval_days_pending = rng.uniform(0, 420) if raw["num_approvals"] > 0 else 0
        prob = latent_risk_probability(features, approval_days_pending, rng)
        delayed = 1 if rng.random() < prob else 0
        delay_days = max(0, rng.gauss(30 + 480 * prob, 40))

        row = {**features, "max_approval_days_pending": approval_days_pending,
               "project_type": raw["project_type"], "delayed": delayed, "delay_days": round(delay_days, 1)}
        rows.append(row)

    return pd.DataFrame(rows)


def generate_live_projects(n: int = 260, seed: int = 7):
    rng = random.Random(seed)
    projects = []
    for _ in range(n):
        raw = sample_raw_project(rng)
        projects.append(raw)
    return projects
