import type { RiskTier } from "../types";

const STYLES: Record<RiskTier, string> = {
  high: "bg-red-100 text-red-700 border-red-300",
  medium: "bg-amber-100 text-amber-700 border-amber-300",
  low: "bg-green-100 text-green-700 border-green-300",
};

const LABELS: Record<RiskTier, string> = {
  high: "🔴 High Risk",
  medium: "🟡 Medium Risk",
  low: "🟢 Low Risk",
};

export default function RiskBadge({ tier }: { tier: RiskTier | null | undefined }) {
  if (!tier) {
    return <span className="px-2 py-1 rounded-full text-xs border bg-slate-100 text-slate-500">Unscored</span>;
  }
  return (
    <span className={`px-2 py-1 rounded-full text-xs font-medium border ${STYLES[tier]}`}>{LABELS[tier]}</span>
  );
}
