interface Props {
  label: string;
  value: string | number;
  accent?: "default" | "red" | "amber" | "green";
}

const ACCENTS: Record<string, string> = {
  default: "text-slate-900",
  red: "text-red-600",
  amber: "text-amber-600",
  green: "text-green-600",
};

export default function StatCard({ label, value, accent = "default" }: Props) {
  return (
    <div className="bg-white rounded-xl border border-slate-200 p-4 shadow-sm">
      <div className="text-xs uppercase tracking-wide text-slate-500">{label}</div>
      <div className={`text-2xl font-semibold mt-1 ${ACCENTS[accent]}`}>{value}</div>
    </div>
  );
}
