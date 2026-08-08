import { useState, useEffect } from 'react';
import { X, Flame, Users, Copy, Check } from 'lucide-react';
import { openSymbolOverview } from '../utils/symbolHelper';

export default function HotStocksModal({ hotStocks = [], onClose }) {
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
            <div className="p-2 sm:p-2.5 rounded-xl bg-amber-500/10 border border-amber-500/20 text-amber-400 font-extrabold flex items-center justify-center shrink-0">
              <Flame size={20} className="animate-pulse text-amber-400" />
            </div>
            <div>
              <h3 className="text-base sm:text-lg font-bold text-slate-100 flex items-center gap-2">
                Top 10 Hot Stocks <span className="text-[10px] sm:text-xs px-2 py-0.5 rounded-full bg-amber-500/10 text-amber-400 border border-amber-500/20 font-mono">Last 60 Days</span>
              </h3>
              <p className="text-[11px] sm:text-xs text-slate-400 mt-0.5">
                Overview of trade volume, distinct insider buyers/sellers, and ISINs
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

        {/* Modal Content / Table */}
        <div className="flex-1 overflow-y-auto p-3 sm:p-6 space-y-3">
          {hotStocks.length === 0 ? (
            <div className="py-12 text-center text-xs text-slate-500 italic bg-slate-950/30 border border-slate-800 rounded-xl">
              No hot stock data currently available.
            </div>
          ) : (
            <div className="space-y-2.5">
              {hotStocks.slice(0, 10).map((stock, idx) => {
                const isTopThree = idx < 3;
                const buyCount = stock.buy_count || 0;
                const sellCount = stock.sell_count || 0;
                const total = stock.trades_count || 0;

                const hasRealName = Boolean(stock.company_name && stock.company_name !== stock.ticker && !stock.company_name.endsWith('Stock') && !stock.company_name.endsWith('Corp.'));

                return (
                  <div
                    key={stock.ticker}
                    onClick={() => {
                      onClose();
                      openSymbolOverview(stock.ticker);
                    }}
                    className={`p-3.5 sm:p-4 rounded-xl border flex flex-col sm:flex-row sm:items-center justify-between gap-3 cursor-pointer transition-all ${
                      isTopThree 
                        ? 'bg-slate-950/70 border-amber-500/30 hover:border-amber-400/60 shadow-lg' 
                        : 'bg-slate-950/40 border-slate-800 hover:border-slate-700'
                    }`}
                  >
                    {/* Rank, Ticker & Company Name */}
                    <div className="flex items-start sm:items-center gap-3">
                      <span className={`w-7 h-7 rounded-lg flex items-center justify-center font-mono font-bold text-xs shrink-0 mt-0.5 sm:mt-0 ${
                        idx === 0 ? 'bg-amber-500/20 text-amber-400 border border-amber-500/40' :
                        idx === 1 ? 'bg-slate-400/20 text-slate-200 border border-slate-400/30' :
                        idx === 2 ? 'bg-amber-700/20 text-amber-300 border border-amber-700/30' :
                        'bg-slate-800 text-slate-400 border border-slate-700'
                      }`}>
                        #{idx + 1}
                      </span>

                      <div className="min-w-0 flex-1">
                        <div className="flex flex-wrap items-center gap-1.5 sm:gap-2">
                          <span className="font-extrabold font-mono text-cyan-400 text-sm sm:text-base hover:underline">
                            {stock.ticker}
                          </span>
                          {hasRealName && (
                            <span className="text-xs font-semibold text-slate-300 truncate max-w-[180px] sm:max-w-[240px]" title={stock.company_name}>
                              ({stock.company_name})
                            </span>
                          )}
                          {stock.isin && (
                            <button
                              onClick={(e) => handleCopyIsin(e, stock.isin)}
                              title="Click to copy ISIN"
                              className="flex items-center gap-1 px-1.5 py-0.5 rounded text-[9px] sm:text-[10px] bg-slate-800 hover:bg-slate-700 text-slate-400 hover:text-slate-200 border border-slate-700/40 font-mono transition-colors"
                            >
                              <span>ISIN: {stock.isin}</span>
                              {copiedIsin === stock.isin ? <Check size={10} className="text-green-400" /> : <Copy size={9} />}
                            </button>
                          )}
                        </div>
                      </div>
                    </div>

                    {/* Mobile & Desktop Responsive Stats Grid */}
                    <div className="grid grid-cols-4 sm:flex sm:items-center justify-between sm:justify-end gap-2 sm:gap-4 text-xs pt-2.5 sm:pt-0 border-t border-slate-800/80 sm:border-t-0">
                      {/* Distinct Persons */}
                      <div className="text-center sm:text-right">
                        <span className="text-[9px] sm:text-[10px] text-slate-500 uppercase font-mono block">Insiders</span>
                        <span className="font-bold text-slate-200 font-mono flex items-center justify-center sm:justify-end gap-1">
                          <Users size={11} className="text-cyan-400" />
                          {stock.distinct_persons || 1}
                        </span>
                      </div>

                      {/* Buy / Sell breakdown */}
                      <div className="text-center sm:text-right">
                        <span className="text-[9px] sm:text-[10px] text-slate-500 uppercase font-mono block">Buy / Sell</span>
                        <div className="font-mono text-[10px] sm:text-[11px] font-bold flex items-center justify-center sm:justify-end gap-0.5">
                          <span className="text-green-400">+{buyCount}B</span>
                          <span className="text-slate-600">/</span>
                          <span className="text-red-400">-{sellCount}S</span>
                        </div>
                      </div>

                      {/* Total Trades */}
                      <div className="text-center sm:text-right">
                        <span className="text-[9px] sm:text-[10px] text-slate-500 uppercase font-mono block">Filings</span>
                        <span className="font-black text-slate-100 font-mono">{total}</span>
                      </div>

                      {/* Perf % */}
                      <div className="text-center sm:text-right pl-1 sm:pl-2 border-l border-slate-800">
                        <span className="text-[9px] sm:text-[10px] text-slate-500 uppercase font-mono block">Return</span>
                        <span className={`font-bold font-mono text-[11px] sm:text-xs ${
                          stock.perf_pct?.startsWith('+') ? 'text-green-400' : stock.perf_pct?.startsWith('-') ? 'text-red-400' : 'text-slate-400'
                        }`}>
                          {stock.perf_pct || 'N/A'}
                        </span>
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
