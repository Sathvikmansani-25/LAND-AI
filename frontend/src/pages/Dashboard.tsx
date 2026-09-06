import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { PieChart, Pie, Cell, ResponsiveContainer, Tooltip, Legend } from "recharts";
import { api } from "../api/client";
import type { DashboardSummary, AlertItem } from "../types";
import StatCard from "../components/StatCard";

const COLORS = { high: "#dc2626", medium: "#d97706", low: "#16a34a" };

function formatInr(value: number): string {
  if (value >= 1e7) return `₹${(value / 1e7).toFixed(1)} Cr`;
  if (value >= 1e5) return `₹${(value / 1e5).toFixed(1)} L`;
  return `₹${value.toLocaleString("en-IN")}`;
}

export default function Dashboard() {
  const [summary, setSummary] = useState<DashboardSummary | null>(null);
  const [alerts, setAlerts] = useState<AlertItem[]>([]);

  useEffect(() => {
    api.get<DashboardSummary>("/api/dashboard/summary").then(setSummary);
    api.get<AlertItem[]>("/api/alerts?limit=6").then(setAlerts);
  }, []);

  if (!summary) return <div className="text-slate-500">Loading dashboard...</div>;

  const pieData = [
    { name: "High Risk", value: summary.high_risk, color: COLORS.high },
    { name: "Medium Risk", value: summary.medium_risk, color: COLORS.medium },
    { name: "Low Risk", value: summary.low_risk, color: COLORS.low },
  ];

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-slate-900">LandGuard AI Dashboard</h1>
        <p className="text-slate-500 text-sm">Predict delays before infrastructure projects get stuck.</p>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <StatCard label="Total Projects" value={summary.total_projects} />
        <StatCard label="High Risk" value={summary.high_risk} accent="red" />
        <StatCard label="Medium Risk" value={summary.medium_risk} accent="amber" />
        <StatCard label="Low Risk" value={summary.low_risk} accent="green" />
        <StatCard label="Critical Alerts" value={summary.critical_alerts} accent="red" />
        <StatCard label="Active Legal Cases" value={summary.total_active_legal_cases} accent="amber" />
        <StatCard
          label="Compensation Pending"
          value={formatInr(summary.total_compensation_pending_inr)}
          accent="amber"
        />
      </div>

      <div className="grid md:grid-cols-2 gap-6">
        <div className="bg-white rounded-xl border border-slate-200 p-4 shadow-sm">
          <h2 className="font-semibold text-slate-800 mb-2">Risk Distribution</h2>
          <div style={{ width: "100%", height: 260 }}>
            <ResponsiveContainer>
              <PieChart>
                <Pie data={pieData} dataKey="value" nameKey="name" innerRadius={60} outerRadius={95} paddingAngle={2}>
                  {pieData.map((entry) => (
                    <Cell key={entry.name} fill={entry.color} />
                  ))}
                </Pie>
                <Tooltip />
                <Legend />
              </PieChart>
            </ResponsiveContainer>
          </div>
        </div>

        <div className="bg-white rounded-xl border border-slate-200 p-4 shadow-sm">
          <div className="flex items-center justify-between mb-2">
            <h2 className="font-semibold text-slate-800">🚨 Recent Alerts</h2>
            <Link to="/alerts" className="text-xs text-slate-500 hover:underline">
              View all
            </Link>
          </div>
          <div className="space-y-2 max-h-64 overflow-y-auto">
            {alerts.length === 0 && <p className="text-sm text-slate-400">No alerts yet.</p>}
            {alerts.map((a) => (
              <div key={a.id} className="border-l-4 pl-3 py-1" style={{ borderColor: a.severity === "critical" ? COLORS.high : COLORS.medium }}>
                <div className="text-sm font-medium text-slate-800">{a.title}</div>
                <div className="text-xs text-slate-500">{a.message}</div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
