import { useEffect, useState } from "react";
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid } from "recharts";
import { api } from "../api/client";
import type { BottleneckReport } from "../types";

export default function Bottlenecks() {
  const [report, setReport] = useState<BottleneckReport | null>(null);

  useEffect(() => {
    api.get<BottleneckReport>("/api/bottleneck").then(setReport);
  }, []);

  if (!report) return <div className="text-slate-500">Loading...</div>;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-slate-900">🔗 Coordination Bottleneck Detection</h1>
        <p className="text-slate-500 text-sm">Which department is causing the most delay across all projects, right now.</p>
      </div>

      <div className="bg-slate-900 text-white rounded-xl p-5 shadow-sm">
        <div className="text-sm text-slate-300">Primary Bottleneck</div>
        <div className="text-2xl font-bold mt-1">{report.primary_bottleneck ?? "None detected"}</div>
        <p className="text-slate-300 text-sm mt-2">{report.narrative}</p>
      </div>

      <div className="bg-white rounded-xl border border-slate-200 p-4 shadow-sm">
        <h2 className="font-semibold text-slate-800 mb-2">Share of Total Delay by Department</h2>
        <div style={{ width: "100%", height: 320 }}>
          <ResponsiveContainer>
            <BarChart data={report.departments} layout="vertical" margin={{ left: 40 }}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis type="number" tickFormatter={(v) => `${v}%`} />
              <YAxis type="category" dataKey="department" width={180} tick={{ fontSize: 12 }} />
              <Tooltip formatter={(v: number) => `${v}%`} />
              <Bar dataKey="share_of_total_delay_pct" fill="#0f172a" radius={[0, 4, 4, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>

      <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-slate-50 text-slate-500 text-left">
            <tr>
              <th className="px-4 py-2">Department</th>
              <th className="px-4 py-2">Pending Approvals</th>
              <th className="px-4 py-2">Avg Days Pending</th>
              <th className="px-4 py-2">Total Days Pending</th>
              <th className="px-4 py-2">Share of Delay</th>
            </tr>
          </thead>
          <tbody>
            {report.departments.map((d) => (
              <tr key={d.department} className="border-t border-slate-100">
                <td className="px-4 py-2 font-medium">{d.department}</td>
                <td className="px-4 py-2">{d.pending_approvals_count}</td>
                <td className="px-4 py-2">{d.avg_days_pending.toFixed(0)}</td>
                <td className="px-4 py-2">{d.total_days_pending}</td>
                <td className="px-4 py-2">{d.share_of_total_delay_pct}%</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
