import { useEffect, useState } from "react";
import { MapContainer, TileLayer, CircleMarker, Popup } from "react-leaflet";
import { useNavigate } from "react-router-dom";
import "leaflet/dist/leaflet.css";
import { api } from "../api/client";
import type { ProjectListItem, DistrictSummary, RiskTier } from "../types";

const RISK_COLOR: Record<RiskTier, string> = { high: "#dc2626", medium: "#d97706", low: "#16a34a" };

export default function MapView() {
  const [projects, setProjects] = useState<ProjectListItem[]>([]);
  const [districts, setDistricts] = useState<DistrictSummary[]>([]);
  const navigate = useNavigate();

  useEffect(() => {
    api.get<ProjectListItem[]>("/api/projects").then(setProjects);
    api.get<DistrictSummary[]>("/api/heatmap/districts").then(setDistricts);
  }, []);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-slate-900">🗺️ India Risk Heatmap</h1>
        <p className="text-slate-500 text-sm">
          Drill down from projects across states and districts. Marker color = risk tier.
        </p>
      </div>

      <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden" style={{ height: 480 }}>
        <MapContainer center={[22.5, 80]} zoom={5} scrollWheelZoom={true}>
          <TileLayer
            attribution='&copy; OpenStreetMap contributors'
            url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
          />
          {projects.map((p) => (
            <CircleMarker
              key={p.id}
              center={[p.latitude, p.longitude]}
              radius={7}
              pathOptions={{
                color: p.risk_tier ? RISK_COLOR[p.risk_tier] : "#94a3b8",
                fillColor: p.risk_tier ? RISK_COLOR[p.risk_tier] : "#94a3b8",
                fillOpacity: 0.7,
              }}
              eventHandlers={{ click: () => navigate(`/projects/${p.id}`) }}
            >
              <Popup>
                <div className="text-sm">
                  <div className="font-semibold">{p.name}</div>
                  <div>{p.district}, {p.state}</div>
                  {p.risk_score !== null && (
                    <div>Risk: {(p.risk_score * 100).toFixed(0)}% ({p.risk_tier})</div>
                  )}
                  <button
                    className="text-blue-600 underline text-xs mt-1"
                    onClick={() => navigate(`/projects/${p.id}`)}
                  >
                    View project →
                  </button>
                </div>
              </Popup>
            </CircleMarker>
          ))}
        </MapContainer>
      </div>

      <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
        <div className="px-4 py-3 border-b border-slate-200 font-semibold text-slate-800">District Risk Summary</div>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="bg-slate-50 text-slate-500 text-left">
              <tr>
                <th className="px-4 py-2">State</th>
                <th className="px-4 py-2">District</th>
                <th className="px-4 py-2">Projects</th>
                <th className="px-4 py-2">🔴 High</th>
                <th className="px-4 py-2">🟡 Medium</th>
                <th className="px-4 py-2">🟢 Low</th>
                <th className="px-4 py-2">Avg Risk</th>
              </tr>
            </thead>
            <tbody>
              {districts.map((d) => (
                <tr key={`${d.state}-${d.district}`} className="border-t border-slate-100 hover:bg-slate-50">
                  <td className="px-4 py-2">{d.state}</td>
                  <td className="px-4 py-2 font-medium">{d.district}</td>
                  <td className="px-4 py-2">{d.total_projects}</td>
                  <td className="px-4 py-2 text-red-600">{d.high_risk}</td>
                  <td className="px-4 py-2 text-amber-600">{d.medium_risk}</td>
                  <td className="px-4 py-2 text-green-600">{d.low_risk}</td>
                  <td className="px-4 py-2">{(d.avg_risk_score * 100).toFixed(0)}%</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
