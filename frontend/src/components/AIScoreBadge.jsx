import { Cpu } from 'lucide-react';

export default function AIScoreBadge({ score }) {
  if (score === null || score === undefined || score === 0) {
    return (
      <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-mono uppercase tracking-wider bg-slate-800 text-slate-400 border border-slate-700">
        <Cpu size={12} />
        Score: N/A
      </span>
    );
  }

  let styles = '';
  if (score >= 8) {
    styles = 'bg-green-900/30 text-green-400 border-green-800 shadow-[0_0_8px_rgba(74,222,128,0.2)]';
  } else if (score >= 5) {
    styles = 'bg-yellow-900/30 text-yellow-400 border-yellow-800 shadow-[0_0_8px_rgba(250,204,21,0.2)]';
  } else {
    styles = 'bg-slate-800 text-slate-400 border-slate-700';
  }

  return (
    <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-mono uppercase tracking-wider border ${styles}`}>
      <Cpu size={12} className={score >= 8 ? 'animate-pulse' : ''} />
      Score: {score}/10
    </span>
  );
}
