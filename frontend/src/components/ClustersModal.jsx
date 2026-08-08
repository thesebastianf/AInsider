import { useState, useEffect } from 'react';
import { X, Zap, Users, Calendar, Copy, Check, TrendingUp, TrendingDown } from 'lucide-react';
import { openSymbolOverview } from '../utils/symbolHelper';

export default function ClustersModal({ clusters = [], onClose }) {
  const [copiedIsin, setCopiedIsin] = useState(null);

  useEffect(() => {
    const handleKeyDown = (e) => {
      if (e.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [onClose]);

  const handleCopyIsin = (e, isin) => {
    e.stopPropagation();
    if (!isin) return;
    navigator.clipboard.writeText(isin);
    setCopiedIsin(isin);
    setTimeout(() => setCopiedIsin(null), 2000);
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-2 sm:p-6 bg-slate-950/80 backdrop-blur-md animate-fade-in">
      <div 
        className="relative w-full max-w-3xl max-h-[92vh] sm:max-h-[85vh] flex flex-col bg-slate-900 border border-slate-700/60 rounded-2xl shadow-2xl overflow-hidden"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header Bar */}
        <div className="px-4 sm:px-6 py-3.5 sm:py-4 border-b border-slate-800 flex justify-between items-center bg-slate-950/50">
          <div className="flex items-center gap-2.5 sm:gap-3">
            <div className="p-2 sm:p-2.5 rounded-xl bg-cyan-500/10 border border-cyan-500/20 text-cyan-400 font-extrabold flex items-center justify-center shrink-0">
              <Zap size={20} className="animate-pulse text-cyan-400 fill-cyan-400" />
            </div>
            <div>
              <h3 className="text-base sm:text-lg font-bold text-slate-100 flex items-center gap-2">
                Top Co-Buying Cluster Signals <span className="text-[10px] sm:text-xs px-2 py-0.5 rounded-full bg-cyan-500/10 text-cyan-400 border border-cyan-500/20 font-mono">2+ Buyers</span>
              </h3>
              <p className="text-[11px] sm:text-xs text-slate-400 mt-0.5">
                Assets where multiple distinct insiders executed BUY trades in the last 60 days
              </p>
            </div>
          </div>

          <button
            onClick={onClose}
            className="p-1.5 sm:p-2 rounded-full text-slate-400 hover:text-white hover:bg-slate-800 transition-colors"
          >
            <X size={18} />
          </button>
        </div>

        {/* Modal Content / Cluster List */}
        <div className="flex-1 overflow-y-auto p-3 sm:p-6 space-y-3">
          {clusters.length === 0 ? (
            <div className="py-12 text-center text-xs text-slate-500 italic bg-slate-950/30 border border-slate-800 rounded-xl">
              No co-buying cluster signals currently detected.
            </div>
          ) : (
            <div className="space-y-3">
              {clusters.slice(0, 10).map((item, idx) => {
                const isTopThree = idx < 3;
                const dateRange = item.first_buy_date && item.latest_buy_date 
                  ? item.first_buy_date === item.latest_buy_date 
                    ? new Date(item.first_buy_date).toLocaleDateString()
                    : `${new Date(item.first_buy_date).toLocaleDateString()} – ${new Date(item.latest_buy_date).toLocaleDateString()}`
                  : 'Recent';

                const hasRealName = Boolean(item.company_name && item.company_name !== item.ticker && !item.company_name.endsWith('Stock') && !item.company_name.endsWith('Corp.'));

                return (
                  <div
                    key={item.ticker}
                    onClick={() => {
                      onClose();
                      openSymbolOverview(item.ticker);
                    }}
                    className={`p-4 rounded-xl border flex flex-col justify-between gap-3 cursor-pointer transition-all ${
                      isTopThree 
                        ? 'bg-slate-950/70 border-cyan-500/40 hover:border-cyan-400 shadow-lg' 
                        : 'bg-slate-950/40 border-slate-800 hover:border-slate-700'
                    }`}
                  >
                    {/* Header Row: Rank, Ticker, Company, ISIN, Buyers Badge */}
                    <div className="flex flex-wrap items-center justify-between gap-2 border-b border-slate-800/60 pb-2.5">
                      <div className="flex items-center gap-2.5">
                        <span className={`w-7 h-7 rounded-lg flex items-center justify-center font-mono font-bold text-xs shrink-0 ${
                          idx === 0 ? 'bg-cyan-500/20 text-cyan-400 border border-cyan-500/40' :
                          idx === 1 ? 'bg-slate-400/20 text-slate-200 border border-slate-400/30' :
                          idx === 2 ? 'bg-purple-500/20 text-purple-300 border border-purple-500/30' :
                          'bg-slate-800 text-slate-400 border border-slate-700'
                        }`}>
                          #{idx + 1}
                        </span>

                        <div>
                          <div className="flex flex-wrap items-center gap-2">
                            <span className="font-extrabold font-mono text-cyan-400 text-base hover:underline">
                              {item.ticker}
                            </span>
                            {hasRealName && (
                              <span className="text-xs font-semibold text-slate-300">
                                ({item.company_name})
                              </span>
                            )}
                            {item.isin && (
                              <button
                                onClick={(e) => handleCopyIsin(e, item.isin)}
                                title="Click to copy ISIN"
                                className="flex items-center gap-1 px-1.5 py-0.5 rounded text-[9px] bg-slate-800 hover:bg-slate-700 text-slate-400 hover:text-slate-200 border border-slate-700/40 font-mono transition-colors"
                              >
                                <span>ISIN: {item.isin}</span>
                                {copiedIsin === item.isin ? <Check size={10} className="text-green-400" /> : <Copy size={9} />}
                              </button>
                            )}
                          </div>
                        </div>
                      </div>

                      {/* Cluster Signal Badge */}
                      <span className="px-2.5 py-1 rounded-full text-xs font-extrabold bg-amber-500/10 text-amber-400 border border-amber-500/30 font-mono flex items-center gap-1">
                        <Zap size={13} className="fill-amber-400" />
                        {item.distinct_buyers_count} Distinct Buyers
                      </span>
                    </div>

                    {/* Buyer Names & Insights Grid */}
                    <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 text-xs pt-1">
                      {/* Buyers List */}
                      <div className="sm:col-span-2 space-y-1">
                        <span className="text-[10px] text-slate-500 font-mono uppercase tracking-wider block">Insiders Buying This Stock</span>
                        <div className="flex flex-wrap gap-1.5">
                          {item.buyer_names.map((bName, bIdx) => (
                            <span 
                              key={bIdx}
                              className="px-2 py-0.5 rounded bg-slate-800/80 border border-slate-700/60 text-slate-200 font-bold text-[11px]"
                            >
                              {bName}
                            </span>
                          ))}
                        </div>
                      </div>

                      {/* Metrics: Time Window & Volume */}
                      <div className="flex sm:flex-col justify-between sm:justify-center sm:items-end text-right gap-1 pt-2 sm:pt-0 border-t sm:border-t-0 border-slate-800">
                        <div>
                          <span className="text-[10px] text-slate-500 font-mono uppercase block">Buying Window</span>
                          <span className="text-[11px] font-semibold text-slate-300 font-mono flex items-center justify-end gap-1">
                            <Calendar size={11} className="text-cyan-400" />
                            {dateRange}
                          </span>
                        </div>

                        <div>
                          <span className="text-[10px] text-slate-500 font-mono uppercase block">Total Filings</span>
                          <span className="text-[11px] font-extrabold text-cyan-400 font-mono">
                            {item.trade_count} BUY trade{item.trade_count !== 1 ? 's' : ''}
                          </span>
                        </div>
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
