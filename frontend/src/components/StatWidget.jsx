export default function StatWidget({ icon: Icon, label, value, sub, color = '#3b82f6' }) {
  return (
    <div className="glass-card p-3.5 flex flex-col gap-1.5">
      <div className="flex items-center gap-2">
        <div className="p-1.5 rounded-lg" style={{ background: `${color}15` }}>
          <Icon size={14} style={{ color }} />
        </div>
        <span className="text-[10px] text-slate-500 font-medium uppercase tracking-wider">{label}</span>
      </div>
      <span className="text-xl font-bold text-slate-100">{value}</span>
      {sub && <span className="text-[10px] text-slate-500">{sub}</span>}
    </div>
  );
}
