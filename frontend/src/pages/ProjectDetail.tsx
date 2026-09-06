import { useEffect, useState } from "react";
import { useParams, Link } from "react-router-dom";
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell, LineChart, Line, CartesianGrid } from "recharts";
import { api } from "../api/client";
import type { ProjectDetail as ProjectDetailType, RiskAssessment, BottleneckReport } from "../types";
import RiskBadge from "../components/RiskBadge";

function formatInr(value: number): string {
  if (value >= 1e7) return `₹${(value / 1e7).toFixed(2)} Cr`;
  if (value >= 1e5) return `₹${(value / 1e5).toFixed(2)} L`;
  return `₹${value.toLocaleString("en-IN")}`;
}

export default function ProjectDetail() {
  const { id } = useParams();
  const [project, setProject] = useState<ProjectDetailType | null>(null);
  const [risk, setRisk] = useState<RiskAssessment | null>(null);
  const [bottleneck, setBottleneck] = useState<BottleneckReport | null>(null);
  const [recomputing, setRecomputing] = useState(false);

  function load() {
    api.get<ProjectDetailType>(`/api/projects/${id}`).then(setProject);
    api.get<RiskAssessment>(`/api/projects/${id}/risk`).then(setRisk);
    api.get<BottleneckReport>(`/api/bottleneck/project/${id}`).then(setBottleneck);
  }

  useEffect(load, [id]);

  async function recompute() {
    setRecomputing(true);
    try {
      const updated = await api.post<RiskAssessment>(`/api/projects/${id}/recompute`);
      setRisk(updated);
    } finally {
      setRecomputing(false);
    }
  }

  if (!project || !risk) return <div className="text-slate-500">Loading project...</div>;

  const forecastData = Object.entries(risk.forecast_30_60_90).map(([day, score]) => ({
    day: day === "0" ? "Today" : `+${day}d`,
    risk: Math.round(score * 100),
  }));

  return (
    <div className="space-y-6">
      <div>
        <Link to="/projects" className="text-sm text-slate-500 hover:underline">← Back to projects</Link>
        <div className="flex items-start justify-between mt-1">
          <div>
            <h1 className="text-2xl font-bold text-slate-900">{project.name}</h1>
            <p className="text-slate-500 text-sm">
              {project.project_type} · {project.district}, {project.state} · deadline {project.deadline}
            </p>
          </div>
          <div className="flex items-center gap-2">
            <RiskBadge tier={risk.risk_tier} />
            <Link
              to={`/projects/${id}/simulate`}
              className="bg-slate-900 text-white text-sm px-3 py-1.5 rounded-lg hover:bg-slate-700"
            >
              🎮 What-If Simulator
            </Link>
          </div>
        </div>
      </div>

      <div className="grid md:grid-cols-3 gap-4">
        <div className="bg-white rounded-xl border border-slate-200 p-4 shadow-sm md:col-span-1">
          <div className="text-xs uppercase text-slate-500">Risk Score</div>
          <div className="text-4xl font-bold text-slate-900 mt-1">{(risk.risk_score * 100).toFixed(0)}%</div>
          <div className="text-sm text-slate-500 mt-1">
            Predicted delay: <span className="font-medium">{risk.predicted_delay_days.toFixed(0)} days</span>
          </div>
          <button
            onClick={recompute}
            disabled={recomputing}
            className="mt-3 text-xs bg-slate-100 hover:bg-slate-200 px-3 py-1.5 rounded-lg text-slate-600 disabled:opacity-50"
          >
            {recomputing ? "Recomputing..." : "🔄 Recompute risk"}
          </button>
        </div>

        <div className="bg-white rounded-xl border border-slate-200 p-4 shadow-sm md:col-span-2">
          <h2 className="font-semibold text-slate-800 mb-2">🧠 Explainable AI — Why is this project at risk?</h2>
          <div style={{ width: "100%", height: 180 }}>
            <ResponsiveContainer>
              <BarChart data={risk.top_factors} layout="vertical" margin={{ left: 20 }}>
                <XAxis type="number" domain={[0, "dataMax"]} tickFormatter={(v) => `${v}%`} />
                <YAxis type="category" dataKey="factor" width={180} tick={{ fontSize: 11 }} />
                <Tooltip formatter={(v: number) => `${v}%`} />
                <Bar dataKey="contribution_pct">
                  {risk.top_factors.map((f, i) => (
                    <Cell key={i} fill={f.direction === "increases" ? "#dc2626" : "#16a34a"} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>

      <div className="grid md:grid-cols-2 gap-6">
        <div className="bg-white rounded-xl border border-slate-200 p-4 shadow-sm">
          <h2 className="font-semibold text-slate-800 mb-2">🔮 Risk Forecast (30 / 60 / 90 days)</h2>
          <div style={{ width: "100%", height: 200 }}>
            <ResponsiveContainer>
              <LineChart data={forecastData}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="day" />
                <YAxis domain={[0, 100]} tickFormatter={(v) => `${v}%`} />
                <Tooltip formatter={(v: number) => `${v}%`} />
                <Line type="monotone" dataKey="risk" stroke="#dc2626" strokeWidth={2} dot />
              </LineChart>
            </ResponsiveContainer>
          </div>
          <p className="text-xs text-slate-400 mt-1">
            "If we don't take action now, what will happen?" — projected assuming pending approvals keep sitting unresolved.
          </p>
        </div>

        <div className="bg-white rounded-xl border border-slate-200 p-4 shadow-sm">
          <h2 className="font-semibold text-slate-800 mb-2">✅ Recommended Actions</h2>
          <ol className="space-y-2 text-sm">
            {risk.recommendations.map((r, i) => (
              <li key={i} className="flex gap-2">
                <span className="font-semibold text-slate-400">{i + 1}.</span>
                <span className="text-slate-700">{r}</span>
              </li>
            ))}
          </ol>
        </div>
      </div>

      <div className="grid md:grid-cols-2 gap-6">
        <div className="bg-white rounded-xl border border-slate-200 p-4 shadow-sm">
          <h2 className="font-semibold text-slate-800 mb-2">🔗 Coordination Bottleneck</h2>
          {bottleneck && bottleneck.departments.length > 0 ? (
            <>
              <p className="text-sm text-slate-600 mb-2">{bottleneck.narrative}</p>
              <div className="space-y-1">
                {bottleneck.departments.map((d) => (
                  <div key={d.department} className="flex items-center justify-between text-sm">
                    <span className="text-slate-700">{d.department}</span>
                    <span className="text-slate-500">{d.pending_approvals_count} pending · {d.share_of_total_delay_pct}%</span>
                  </div>
                ))}
              </div>
            </>
          ) : (
            <p className="text-sm text-slate-400">No pending approvals for this project.</p>
          )}
        </div>

        <div className="bg-white rounded-xl border border-slate-200 p-4 shadow-sm space-y-3">
          <h2 className="font-semibold text-slate-800">📋 Project Facts</h2>
          <div className="grid grid-cols-2 gap-2 text-sm">
            <div className="text-slate-500">Land area</div>
            <div className="text-slate-800">{project.land_area_hectares} hectares</div>
            <div className="text-slate-500">Affected families</div>
            <div className="text-slate-800">{project.affected_families.toLocaleString("en-IN")}</div>
            <div className="text-slate-500">Ownership complexity</div>
            <div className="text-slate-800">{project.ownership_complexity} / 5</div>
            <div className="text-slate-500">Compensation total</div>
            <div className="text-slate-800">{formatInr(project.compensation_total_inr)}</div>
            <div className="text-slate-500">Compensation disbursed</div>
            <div className="text-slate-800">{(project.compensation_pct_disbursed * 100).toFixed(0)}%</div>
            <div className="text-slate-500">Active legal disputes</div>
            <div className="text-slate-800">{project.active_legal_disputes}</div>
            <div className="text-slate-500">Pending approvals</div>
            <div className="text-slate-800">{project.pending_approvals}</div>
            <div className="text-slate-500">Longest pending approval</div>
            <div className="text-slate-800">{project.max_approval_days_pending} days</div>
          </div>
        </div>
      </div>
    </div>
  );
}
