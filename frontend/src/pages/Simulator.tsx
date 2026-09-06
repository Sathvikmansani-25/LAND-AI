import { useEffect, useState } from "react";
import { useParams, Link } from "react-router-dom";
import { api } from "../api/client";
import type { ProjectDetail, SimulationResult } from "../types";
import RiskBadge from "../components/RiskBadge";

export default function Simulator() {
  const { id } = useParams();
  const [project, setProject] = useState<ProjectDetail | null>(null);
  const [resolveLegal, setResolveLegal] = useState(false);
  const [releaseComp, setReleaseComp] = useState(false);
  const [completeApprovals, setCompleteApprovals] = useState(false);
  const [capDays, setCapDays] = useState<number | "">("");
  const [result, setResult] = useState<SimulationResult | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    api.get<ProjectDetail>(`/api/projects/${id}`).then(setProject);
  }, [id]);

  async function runSimulation() {
    setLoading(true);
    try {
      const res = await api.post<SimulationResult>(`/api/projects/${id}/simulate`, {
        resolve_legal_disputes: resolveLegal,
        release_compensation: releaseComp,
        complete_pending_approvals: completeApprovals,
        reduce_approval_days_to: capDays === "" ? null : capDays,
      });
      setResult(res);
    } finally {
      setLoading(false);
    }
  }

  if (!project) return <div className="text-slate-500">Loading...</div>;

  return (
    <div className="space-y-6 max-w-3xl">
      <div>
        <Link to={`/projects/${id}`} className="text-sm text-slate-500 hover:underline">← Back to project</Link>
        <h1 className="text-2xl font-bold text-slate-900 mt-1">🎮 What-If Simulator</h1>
        <p className="text-slate-500 text-sm">{project.name} — simulate administrative actions and see the predicted effect on risk.</p>
      </div>

      <div className="bg-white rounded-xl border border-slate-200 p-5 shadow-sm space-y-4">
        <h2 className="font-semibold text-slate-800">Select actions to simulate</h2>

        <label className="flex items-center gap-3 text-sm">
          <input type="checkbox" checked={resolveLegal} onChange={(e) => setResolveLegal(e.target.checked)} className="w-4 h-4" />
          ☑️ Resolve all active legal disputes ({project.active_legal_disputes} active)
        </label>
        <label className="flex items-center gap-3 text-sm">
          <input type="checkbox" checked={releaseComp} onChange={(e) => setReleaseComp(e.target.checked)} className="w-4 h-4" />
          ☑️ Release full pending compensation ({(project.compensation_pct_disbursed * 100).toFixed(0)}% currently disbursed)
        </label>
        <label className="flex items-center gap-3 text-sm">
          <input
            type="checkbox"
            checked={completeApprovals}
            onChange={(e) => setCompleteApprovals(e.target.checked)}
            className="w-4 h-4"
          />
          ☑️ Complete all pending approvals ({project.pending_approvals} pending)
        </label>
        <label className="flex items-center gap-3 text-sm">
          <span className="w-72">Cap longest-pending approval at (days):</span>
          <input
            type="number"
            min={0}
            value={capDays}
            onChange={(e) => setCapDays(e.target.value === "" ? "" : Number(e.target.value))}
            placeholder={`currently ${project.max_approval_days_pending}`}
            className="border border-slate-300 rounded-lg px-2 py-1 w-32 text-sm"
          />
        </label>

        <button
          onClick={runSimulation}
          disabled={loading}
          className="bg-slate-900 text-white px-4 py-2 rounded-lg text-sm hover:bg-slate-700 disabled:opacity-50"
        >
          {loading ? "Simulating..." : "Run Simulation"}
        </button>
      </div>

      {result && (
        <div className="bg-white rounded-xl border border-slate-200 p-5 shadow-sm space-y-4">
          <h2 className="font-semibold text-slate-800">Simulation Result</h2>
          <div className="flex items-center gap-6">
            <div className="text-center">
              <div className="text-xs text-slate-500">Current</div>
              <div className="text-3xl font-bold text-slate-900">{(result.baseline_risk_score * 100).toFixed(0)}%</div>
              <RiskBadge tier={result.baseline_tier} />
            </div>
            <div className="text-2xl text-slate-400">→</div>
            <div className="text-center">
              <div className="text-xs text-slate-500">Predicted</div>
              <div className="text-3xl font-bold text-green-600">{(result.new_risk_score * 100).toFixed(0)}%</div>
              <RiskBadge tier={result.new_tier} />
            </div>
          </div>
          <div className="bg-slate-50 rounded-lg p-3 text-sm text-slate-700">{result.explanation}</div>
        </div>
      )}
    </div>
  );
}
