import { NavLink, Outlet } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import ChatWidget from "./ChatWidget";

const NAV_ITEMS = [
  { to: "/", label: "Dashboard", icon: "📊" },
  { to: "/map", label: "Risk Heatmap", icon: "🗺️" },
  { to: "/projects", label: "Projects", icon: "🏗️" },
  { to: "/alerts", label: "Alerts", icon: "🚨" },
  { to: "/bottlenecks", label: "Bottlenecks", icon: "🔗" },
];

export default function Layout() {
  const { user, logout } = useAuth();

  return (
    <div className="min-h-screen flex bg-slate-50">
      <aside className="w-60 shrink-0 bg-slate-900 text-slate-100 flex flex-col">
        <div className="p-4 border-b border-slate-700">
          <div className="text-lg font-bold">🛡️ LandGuard AI</div>
          <div className="text-xs text-slate-400">Early Delay Detection</div>
        </div>
        <nav className="flex-1 p-2 space-y-1">
          {NAV_ITEMS.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.to === "/"}
              className={({ isActive }) =>
                `flex items-center gap-2 px-3 py-2 rounded-lg text-sm transition-colors ${
                  isActive ? "bg-slate-700 text-white" : "text-slate-300 hover:bg-slate-800"
                }`
              }
            >
              <span>{item.icon}</span>
              <span>{item.label}</span>
            </NavLink>
          ))}
        </nav>
        <div className="p-3 border-t border-slate-700 text-sm">
          <div className="text-slate-200 font-medium">{user?.full_name}</div>
          <div className="text-slate-400 text-xs mb-2">{user?.role}</div>
          <button
            onClick={logout}
            className="w-full text-left px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs"
          >
            Log out
          </button>
        </div>
      </aside>
      <main className="flex-1 overflow-auto">
        <div className="p-6 max-w-7xl mx-auto">
          <Outlet />
        </div>
      </main>
      <ChatWidget />
    </div>
  );
}
