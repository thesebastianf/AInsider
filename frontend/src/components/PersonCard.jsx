import { Star, TrendingUp, TrendingDown, User } from 'lucide-react';
import AIScoreBadge from './AIScoreBadge';

export default function PersonCard({ person, performance, onToggleFollow }) {
  const trade = person.latest_trade;
  const perf = trade ? performance?.[trade.ticker] : null;

  return (
    <div className="bg-surface rounded-xl p-4 border border-border shadow-lg relative overflow-hidden backdrop-blur-sm animate-fade-in transition-all hover:border-border-bright">
      
      {/* Subtle Gradient Background for active follows */}
      {person.is_followed && (
        <div className="absolute top-0 right-0 w-32 h-32 bg-cyan-500/10 rounded-bl-[100px] pointer-events-none transition-opacity duration-500" />
      )}
      
      <div className="flex justify-between items-start mb-4 relative z-10">
        <div className="flex gap-4">
          {/* Avatar Photo */}
          <div className="w-14 h-14 rounded-full overflow-hidden bg-surface-2 border-2 border-border shrink-0 flex items-center justify-center">
            {person.photo_url ? (
              <img src={person.photo_url} alt={person.name} className="w-full h-full object-cover" />
            ) : (
              <User className="h-6 w-6 text-slate-400 dark:text-slate-500" />
            )}
          </div>
          
          <div>
            <h3 className="text-lg font-bold text-slate-900 dark:text-white leading-tight flex flex-wrap items-center gap-1.5">
              {person.name}
              {!person.is_active && (
                <span className="px-1.5 py-0.5 rounded text-[8px] font-bold bg-red-500/15 text-red-500 border border-red-500/20 uppercase tracking-wider shrink-0">
                  Retired
                </span>
              )}
            </h3>
            <span className="text-[10px] text-cyan-500 dark:text-cyan-400 font-semibold uppercase tracking-wider font-mono">{person.category}</span>
            {person.description && (
              <p className="text-[11px] text-slate-500 dark:text-slate-400 mt-1.5 italic leading-snug line-clamp-2 max-w-[240px]">
                "{person.description}"
              </p>
            )}
          </div>
        </div>
        <button 
          onClick={() => onToggleFollow(person.id)} 
          className="p-2 bg-surface-2 rounded-full hover:bg-surface-3 transition-colors z-20 shrink-0 border border-border"
        >
          <Star className={`h-4 w-4 transition-all ${
            person.is_followed 
              ? 'text-yellow-500 fill-yellow-500 drop-shadow-[0_0_8px_rgba(250,204,21,0.5)]' 
              : 'text-slate-400 dark:text-slate-500'
          }`} />
        </button>
      </div>
      
      {trade ? (
        <>
          <div className="flex items-center justify-between p-3 bg-surface-2 rounded-lg mb-3 relative z-10 border border-border">
            <div className="flex items-center gap-3">
              <div className={`p-2 rounded-full border ${
                trade.type === 'BUY' 
                  ? 'bg-green-500/10 text-green-500 border-green-500/20' 
                  : 'bg-red-500/10 text-red-500 border-red-500/20'
              }`}>
                {trade.type === 'BUY' ? <TrendingUp className="h-4 w-4" /> : <TrendingDown className="h-4 w-4" />}
              </div>
              <div>
                <div className="text-sm font-bold text-slate-800 dark:text-slate-100 flex items-center gap-1">
                  {trade.ticker}
                </div>
                <div className="text-xs text-slate-500 dark:text-slate-400">
                  {new Date(trade.trade_date).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })}
                </div>
              </div>
            </div>
            
            <div className="text-right">
              <div className="text-sm text-slate-700 dark:text-slate-300 font-medium">{trade.amount_range}</div>
              <div className="flex items-center justify-end mt-1">
                <AIScoreBadge score={trade.ai_score} />
              </div>
            </div>
          </div>
          
          {trade.ai_summary && (
            <p className="mb-3 text-[11px] text-slate-500 dark:text-slate-400 leading-relaxed line-clamp-2 relative z-10 pl-1">
              {trade.ai_summary}
            </p>
          )}

          <div className="flex justify-between items-center text-xs border-t border-border pt-3 mt-2 relative z-10">
            <span className="text-slate-500 dark:text-slate-400">YTD Performance</span>
            {perf && perf.ytd_performance_pct !== null ? (
              <span className={`font-bold flex items-center gap-1 ${
                perf.ytd_performance_pct >= 0 ? 'text-green-500 dark:text-green-400' : 'text-red-500 dark:text-red-400'
              }`}>
                {perf.ytd_performance_pct >= 0 ? '+' : ''}{perf.ytd_performance_pct}%
              </span>
            ) : (
              <span className="text-slate-600 dark:text-slate-500">Pending</span>
            )}
          </div>
        </>
      ) : (
        <div className="p-3 bg-surface-2 rounded-lg text-xs text-slate-500 italic text-center border border-border">
          No trades recorded
        </div>
      )}
    </div>
  );
}
