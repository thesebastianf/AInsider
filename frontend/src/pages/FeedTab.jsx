import { useState, useCallback } from 'react';
import { useApi } from '../hooks/useApi';
import { getTrades } from '../api/client';
import { Activity, RefreshCw, Calendar, ExternalLink } from 'lucide-react';
import AIScoreBadge from '../components/AIScoreBadge';

export default function FeedTab() {
  const [category, setCategory] = useState('All');
  const [tradeType, setTradeType] = useState('All');

  const fetchTradesList = useCallback(() => {
    const params = { limit: 100 };
    if (category !== 'All') params.category = category;
    if (tradeType !== 'All') params.trade_type = tradeType;
    return getTrades(params);
  }, [category, tradeType]);

  const { data: tradesData, loading, error, refetch } = useApi(fetchTradesList, [category, tradeType]);
  const trades = tradesData?.trades || [];

  return (
    <div className="px-5 py-5 space-y-5 animate-fade-in">
      <div className="flex justify-between items-center">
        <div className="flex items-center gap-2">
          <Activity size={16} className="text-cyan-400" />
          <span className="text-sm font-semibold text-slate-200">Live Transaction Feed</span>
        </div>
        <button onClick={refetch} disabled={loading} title="Refresh Feed"
          className="p-1.5 rounded-lg bg-slate-800/80 border border-slate-700/50 text-slate-400 hover:text-white transition-colors disabled:opacity-50">
          <RefreshCw size={14} className={loading ? 'animate-spin' : ''} />
        </button>
      </div>

      {/* Filter Row */}
      <div className="flex flex-wrap gap-2">
        <div className="flex rounded-lg bg-slate-900/60 p-0.5 border border-slate-800/50">
          {['All', 'Congress', 'Senate', 'Corporate Insider', 'Fund Manager'].map(c => (
            <button key={c} onClick={() => setCategory(c)}
              className={`px-3 py-1 rounded-md text-[11px] font-semibold transition-all ${
                category === c ? 'bg-cyan-500/20 text-cyan-400' : 'text-slate-500 hover:text-slate-300'
              }`}>
              {c}
            </button>
          ))}
        </div>

        <div className="flex rounded-lg bg-slate-900/60 p-0.5 border border-slate-800/50">
          {['All', 'BUY', 'SELL'].map(t => (
            <button key={t} onClick={() => setTradeType(t)}
              className={`px-3 py-1 rounded-md text-[11px] font-semibold transition-all ${
                tradeType === t ? 'bg-cyan-500/20 text-cyan-400' : 'text-slate-500 hover:text-slate-300'
              }`}>
              {t}
            </button>
          ))}
        </div>
      </div>

      {/* Feed List */}
      {loading && !tradesData ? (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {Array.from({ length: 6 }).map((_, i) => (
            <div key={i} className="skeleton h-36 w-full" />
          ))}
        </div>
      ) : trades.length === 0 ? (
        <div className="glass-card p-6 text-center text-xs text-slate-500 italic">
          No trades found. Run data pipeline to populate.
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {trades.map(trade => (
            <div key={trade.id} className="glass-card p-4 flex flex-col justify-between space-y-3">
              <div className="flex justify-between items-start">
                <div>
                  <span className="text-[10px] text-cyan-500 dark:text-cyan-400 uppercase font-mono tracking-wider font-semibold">
                    {trade.person_category}
                  </span>
                  <h4 className="text-sm font-bold text-slate-800 dark:text-slate-100 mt-0.5">{trade.person_name}</h4>
                </div>
                <div className={`px-2.5 py-0.5 rounded-full text-[10px] font-bold border ${
                  trade.type === 'BUY' 
                    ? 'bg-green-500/10 text-green-500 dark:text-green-400 border-green-500/20' 
                    : 'bg-red-500/10 text-red-500 dark:text-red-400 border-red-500/20'
                }`}>
                  {trade.type}
                </div>
              </div>

              <div className="flex items-center justify-between p-3 bg-surface-2 rounded-lg border border-border">
                <div>
                  <div className="text-sm font-bold text-slate-800 dark:text-slate-100">{trade.ticker}</div>
                  <div className="text-[10px] text-slate-500 dark:text-slate-400 flex items-center gap-1.5 mt-0.5">
                    <Calendar size={10} />
                    {new Date(trade.trade_date).toLocaleDateString()}
                    {trade.source_url && (
                      <a href={trade.source_url} target="_blank" rel="noopener noreferrer"
                        className="text-cyan-500 hover:text-cyan-400 hover:underline flex items-center gap-0.5">
                        • Link <ExternalLink size={8} />
                      </a>
                    )}
                  </div>
                </div>
                <div className="text-right">
                  <div className="text-xs text-slate-700 dark:text-slate-300 font-semibold">{trade.amount_range}</div>
                  <div className="flex justify-end mt-1">
                    <AIScoreBadge score={trade.ai_score} />
                  </div>
                </div>
              </div>

              {trade.ai_summary && (
                <p className="text-[11px] text-slate-500 dark:text-slate-400 leading-relaxed border-l-2 border-slate-600 dark:border-slate-700 pl-2">
                  "{trade.ai_summary}"
                </p>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
