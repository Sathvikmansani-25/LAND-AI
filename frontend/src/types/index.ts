export type RiskTier = "low" | "medium" | "high";

export interface AuthUser {
  username: string;
  full_name: string;
  role: string;
}

export interface ProjectListItem {
  id: number;
  name: string;
  project_type: string;
  state: string;
  district: string;
  latitude: number;
  longitude: number;
  status: string;
  risk_score: number | null;
  risk_tier: RiskTier | null;
}

export interface Approval {
  id: number;
  project_id: number;
  department: string;
  status: "pending" | "approved" | "rejected";
  days_pending: number;
  requested_at: string | null;
  resolved_at: string | null;
}

export interface Dispute {
  id: number;
  project_id: number;
  case_type: string;
  status: "active" | "resolved";
  filed_at: string | null;
  resolved_at: string | null;
}

export interface ProjectDetail {
  id: number;
  name: string;
  project_type: string;
  state: string;
  district: string;
  latitude: number;
  longitude: number;
  land_area_hectares: number;
  affected_families: number;
  ownership_complexity: number;
  compensation_total_inr: number;
  compensation_disbursed_inr: number;
  compensation_pct_disbursed: number;
  departments_involved: number;
  start_date: string;
  deadline: string;
  status: string;
  district_historical_delay_rate: number;
  active_legal_disputes: number;
  pending_approvals: number;
  max_approval_days_pending: number;
  approvals: Approval[];
  disputes: Dispute[];
}

export interface RiskFactor {
  factor: string;
  contribution_pct: number;
  direction: "increases" | "decreases";
}

export interface RiskAssessment {
  project_id: number;
  risk_score: number;
  risk_tier: RiskTier;
  predicted_delay_days: number;
  top_factors: RiskFactor[];
  recommendations: string[];
  forecast_30_60_90: Record<string, number>;
  computed_at: string;
}

export interface SimulationResult {
  baseline_risk_score: number;
  new_risk_score: number;
  risk_reduction_pct: number;
  baseline_tier: RiskTier;
  new_tier: RiskTier;
  explanation: string;
}

export interface DepartmentBottleneck {
  department: string;
  pending_approvals_count: number;
  avg_days_pending: number;
  total_days_pending: number;
  share_of_total_delay_pct: number;
}

export interface BottleneckReport {
  project_id: number | null;
  departments: DepartmentBottleneck[];
  primary_bottleneck: string | null;
  narrative: string;
}

export interface AlertItem {
  id: number;
  project_id: number;
  severity: "info" | "warning" | "critical";
  title: string;
  message: string;
  previous_tier: RiskTier | null;
  new_tier: RiskTier | null;
  acknowledged: boolean;
  created_at: string;
}

export interface DistrictSummary {
  state: string;
  district: string;
  total_projects: number;
  high_risk: number;
  medium_risk: number;
  low_risk: number;
  avg_risk_score: number;
  lat: number;
  lng: number;
}

export interface DashboardSummary {
  total_projects: number;
  high_risk: number;
  medium_risk: number;
  low_risk: number;
  critical_alerts: number;
  total_compensation_pending_inr: number;
  total_active_legal_cases: number;
}

export interface ChatResponse {
  response: string;
  data: unknown;
  engine?: "llm" | "rule_based";
}

export interface FilterOptions {
  states: string[];
  districts: string[];
  project_types: string[];
}
