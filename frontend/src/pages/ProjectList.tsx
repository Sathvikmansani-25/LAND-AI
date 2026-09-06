import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api/client";
import type { ProjectListItem, FilterOptions } from "../types";
import RiskBadge from "../components/RiskBadge";

export default function ProjectList() {
  const [projects, setProjects] = useState<ProjectListItem[]>([]);
  const [filters, setFilters] = useState<FilterOptions>({ states: [], districts: [], project_types: [] });
  const [state, setState] = useState("");
  const [district, setDistrict] = useState("");
  const [riskTier, setRiskTier] = useState("");
  const [search, setSearch] = useState("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.get<FilterOptions>("/api/projects/meta/filters").then(setFilters);
  }, []);

  useEffect(() => {
    setLoading(true);
    const params = new URLSearchParams();
    if (state) params.set("state", state);
    if (district) params.set("district", district);
    if (riskTier) params.set("risk_tier", riskTier);
    if (search) params.set("search", search);
    api
      .get<ProjectListItem[]>(`/api/projects?${params.toString()}`)
      .then(setProjects)
      .finally(() => setLoading(false));
  }, [state, district, riskTier, search]);

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-2xl font-bold text-slate-900">🏗️ Projects</h1>
        <p className="text-slate-500 text-sm">{projects.length} project(s) matching filters</p>
      </div>

      <div className="bg-white rounded-xl border border-slate-200 p-4 shadow-sm flex flex-wrap gap-3">
        <input
          placeholder="Search project name..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="border border-slate-300 rounded-lg px-3 py-1.5 text-sm flex-1 min-w-[180px]"
        />
        <select value={state} onChange={(e) => setState(e.target.value)} className="border border-slate-300 rounded-lg px-3 py-1.5 text-sm">
          <option value="">All States</option>
          {filters.states.map((s) => (
            <option key={s} value={s}>{s}</option>
          ))}
        </select>
        <select value={district} onChange={(e) => setDistrict(e.target.value)} className="border border-slate-300 rounded-lg px-3 py-1.5 text-sm">
          <option value="">All Districts</option>
          {filters.districts.map((d) => (
            <option key={d} value={d}>{d}</option>
          ))}
        </select>
        <select value={riskTier} onChange={(e) => setRiskTier(e.target.value)} className="border border-slate-300 rounded-lg px-3 py-1.5 text-sm">
          <option value="">All Risk Tiers</option>
          <option value="high">High</option>
          <option value="medium">Medium</option>
          <option value="low">Low</option>
        </select>
      </div>

      <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="bg-slate-50 text-slate-500 text-left">
              <tr>
                <th className="px-4 py-2">Project</th>
                <th className="px-4 py-2">Type</th>
                <th className="px-4 py-2">Location</th>
                <th className="px-4 py-2">Status</th>
                <th className="px-4 py-2">Risk</th>
              </tr>
            </thead>
            <tbody>
              {loading && (
                <tr><td colSpan={5} className="px-4 py-6 text-center text-slate-400">Loading...</td></tr>
              )}
              {!loading && projects.length === 0 && (
                <tr><td colSpan={5} className="px-4 py-6 text-center text-slate-400">No projects match these filters.</td></tr>
              )}
              {projects.map((p) => (
                <tr key={p.id} className="border-t border-slate-100 hover:bg-slate-50">
                  <td className="px-4 py-2">
                    <Link to={`/projects/${p.id}`} className="font-medium text-slate-900 hover:underline">
                      {p.name}
                    </Link>
                  </td>
                  <td className="px-4 py-2 text-slate-600">{p.project_type}</td>
                  <td className="px-4 py-2 text-slate-600">{p.district}, {p.state}</td>
                  <td className="px-4 py-2 text-slate-600 capitalize">{p.status}</td>
                  <td className="px-4 py-2">
                    <div className="flex items-center gap-2">
                      <RiskBadge tier={p.risk_tier} />
                      {p.risk_score !== null && (
                        <span className="text-xs text-slate-500">{(p.risk_score * 100).toFixed(0)}%</span>
                      )}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
