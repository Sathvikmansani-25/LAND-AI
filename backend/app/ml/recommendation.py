"""Rule-based recommendation engine: maps top risk-driving factors to
concrete, prescriptive administrative actions."""

FACTOR_ACTIONS = {
    "Active legal disputes": "Prioritize and fast-track resolution of active legal case(s); assign dedicated legal counsel.",
    "Compensation NOT yet disbursed": "Release pending compensation to affected families without further delay.",
    "Longest-pending approval (days)": "Escalate the longest-pending departmental approval to the District Collector / nodal officer.",
    "Pending approvals": "Convene an inter-departmental coordination meeting to jointly clear pending approvals.",
    "Land ownership complexity": "Conduct title verification and land-record settlement camps to resolve ownership ambiguity.",
    "District's historical delay pattern": "Assign a dedicated nodal officer; apply mitigation lessons from similar past projects in this district.",
    "Departments involved": "Set up a single-window inter-departmental coordination cell for this project.",
    "Number of affected families": "Conduct large-scale stakeholder consultations and grievance-redressal camps.",
    "Land area required": "Consider phased land acquisition to reduce the number of simultaneous disputes.",
}

DEFAULT_ACTION = "Conduct a project review meeting to reassess timelines and risk mitigation steps."


def get_recommendations(top_factors: list[dict], n: int = 4) -> list[str]:
    actions: list[str] = []
    for f in top_factors:
        if f.get("direction") != "increases":
            continue
        action = FACTOR_ACTIONS.get(f["factor"])
        if action and action not in actions:
            actions.append(action)
        if len(actions) >= n:
            break
    if not actions:
        actions.append(DEFAULT_ACTION)
    return actions
