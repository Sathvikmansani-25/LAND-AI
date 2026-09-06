import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api/client";
import type { AlertItem } from "../types";

const SEVERITY_STYLE: Record<string, string> = {
  critical: "border-red-400 bg-red-50",
  warning: "border-amber-400 bg-amber-50",
  info: "border-slate-300 bg-slate-50",
};

export default function Alerts() {
  const [alerts, setAlerts] = useState<AlertItem[]>([]);
  const [filter, setFilter] = useState<string>("");

  function load() {
    const params = filter ? `?severity=${filter}` : "";
    api.get<AlertItem[]>(`/api/alerts${params}`).then(setAlerts);
  }

  useEffect(load, [filter]);

  async function acknowledge(id: number) {
    await api.post(`/api/alerts/${id}/acknowledge`);
    load();
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">🚨 Early Warning Alerts</h1>
          <p className="text-slate-500 text-sm">Projects that crossed a risk threshold and need attention.</p>
        </div>
        <select value={filter} onChange={(e) => setFilter(e.target.value)} className="border border-slate-300 rounded-lg px-3 py-1.5 text-sm">
          <option value="">All severities</option>
          <option value="critical">Critical only</option>
          <option value="warning">Warning only</option>
        </select>
      </div>

      <div className="space-y-3">
        {alerts.length === 0 && <p className="text-slate-400 text-sm">No alerts to show.</p>}
        {alerts.map((a) => (
          <div key={a.id} className={`border-l-4 rounded-r-xl p-4 shadow-sm ${SEVERITY_STYLE[a.severity]} ${a.acknowledged ? "opacity-50" : ""}`}>
            <div className="flex items-start justify-between gap-4">
              <div>
                <div className="font-semibold text-slate-800">
                  {a.severity === "critical" ? "🔴" : "🟡"} {a.title}
                </div>
                <div className="text-sm text-slate-600 mt-1">{a.message}</div>
                <Link to={`/projects/${a.project_id}`} className="text-xs text-blue-600 hover:underline mt-1 inline-block">
                  View project →
                </Link>
              </div>
              {!a.acknowledged && (
                <button
                  onClick={() => acknowledge(a.id)}
                  className="shrink-0 text-xs bg-white border border-slate-300 px-3 py-1.5 rounded-lg hover:bg-slate-100"
                >
                  Acknowledge
                </button>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
