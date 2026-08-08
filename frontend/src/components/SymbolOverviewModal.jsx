import { useState, useEffect } from 'react';
import { X, Copy, ExternalLink, Calendar, TrendingUp, TrendingDown, Users, Activity, Check, Loader2, Download, Zap } from 'lucide-react';
import { getAssetDetail } from '../api/client';
import { getInitials, getAvatarColor } from '../utils/avatarUtils';
import { exportToCSV, exportToJSON } from '../utils/exportUtils';
import AIScoreBadge from './AIScoreBadge';
import StockPriceChart from './StockPriceChart';

export default function SymbolOverviewModal({ symbolOrIsin, onClose }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [copiedIsin, setCopiedIsin] = useState(false);
  const [filterType, setFilterType] = useState('ALL');
  const [imageErrors, setImageErrors] = useState({});

  useEffect(() => {
    if (!symbolOrIsin) return;
    let isMounted = true;
    setLoading(true);
    setError(null);

    getAssetDetail(symbolOrIsin)
      .then((res) => {
        if (isMounted) {
          setData(res);
          setLoading(false);
        }
      })
      .catch((err) => {
        if (isMounted) {
          setError(err.message || 'Failed to load symbol details');
          setLoading(false);
        }
      });

    return () => {
      isMounted = false;
    };
  }, [symbolOrIsin]);

  useEffect(() => {
    const handleKeyDown = (e) => {
      if (e.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [onClose]);

  const handleCopyIsin = (e) => {
    e.stopPropagation();
    if (!data?.isin) return;
    navigator.clipboard.writeText(data.isin);
    setCopiedIsin(true);
    setTimeout(() => setCopiedIsin(false), 2000);
  };

  const handleImageError = (personId) => {
    setImageErrors((prev) => ({ ...prev, [personId]: true }));
  };

  const handleExportCSV = () => {
    if (!filteredTrades.length) return;
    const exportRows = filteredTrades.map(t => ({
      Filer: t.person_name,
      Category: t.person_category,
      Ticker: t.ticker,
      Action: t.type,
      AmountRange: t.amount_range,
      TradeDate: t.trade_date,
      FilingDate: t.filing_date || '',
      PriceAtTransaction: t.price_at_transaction || '',
      ReturnSincePurchasePct: t.return_since_purchase_pct || '',
      AIScore: t.ai_score || '',
      AISummary: t.ai_summary || '',
      SourceURL: t.source_url || '',
    }));
    exportToCSV(`${data?.ticker || 'symbol'}_trades`, exportRows);
  };

  const handleExportJSON = () => {
    if (!filteredTrades.length) return;
    exportToJSON(`${data?.ticker || 'symbol'}_trades`, filteredTrades);
  };

  if (!symbolOrIsin) return null;

  const trades = data?.trades || [];
  const filteredTrades = filterType === 'ALL' 
    ? trades 
    : trades.filter(t => t.type === filterType);

  const buyCount = data?.buy_count || 0;
  const sellCount = data?.sell_count || 0;
  const totalTrades = data?.trade_count || 0;
  const buyPct = totalTrades > 0 ? Math.round((buyCount / totalTrades) * 100) : 0;
  const sellPct = totalTrades > 0 ? 100 - buyPct : 0;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 sm:p-6 bg-slate-950/80 backdrop-blur-md animate-fade-in">
      <div 
        className="relative w-full max-w-4xl max-h-[90vh] flex flex-col bg-slate-900 border border-slate-700/60 rounded-2xl shadow-2xl overflow-hidden"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header Bar */}
        <div className="px-6 py-4 border-b border-slate-800 flex justify-between items-center bg-slate-950/40">
          <div className="flex items-center gap-3">
            <div className="p-2.5 rounded-xl bg-cyan-500/10 border border-cyan-500/20 text-cyan-400 font-extrabold font-mono text-xl tracking-wider">
              {data?.ticker || symbolOrIsin.toUpperCase()}
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h3 className="text-lg font-bold text-slate-100">
                  {data?.company_name || `${symbolOrIsin.toUpperCase()} Corp.`}
                </h3>

                {/* ISIN Copy Pill */}
                {data?.isin && (
                  <button
                    onClick={handleCopyIsin}
                    title="Click to copy ISIN"
                    className="flex items-center gap-1 px-2.5 py-0.5 rounded-full bg-slate-800 hover:bg-slate-700 border border-slate-700 text-[11px] font-mono text-cyan-400 transition-colors"
                  >
                    <span>ISIN: {data.isin}</span>
                    {copiedIsin ? <Check size={12} className="text-green-400" /> : <Copy size={11} />}
                  </button>
                )}
              </div>
              <p className="text-xs text-slate-400 mt-0.5">
                Overview of all insider filings, volumes, and returns for this asset
              </p>
            </div>
          </div>

          <button
            onClick={onClose}
            className="p-2 rounded-full text-slate-400 hover:text-white hover:bg-slate-800 transition-colors"
          >
            <X size={20} />
          </button>
        </div>

        {/* Modal Body */}
        <div className="flex-1 overflow-y-auto p-6 space-y-6">
          {loading ? (
            <div className="flex flex-col items-center justify-center py-20 text-slate-400 gap-3">
              <Loader2 className="animate-spin text-cyan-400" size={32} />
              <span className="text-xs font-mono">Fetching asset overview & insider transactions...</span>
            </div>
          ) : error ? (
            <div className="p-6 text-center text-red-400 bg-red-950/20 border border-red-500/20 rounded-xl text-xs">
              {error}
            </div>
          ) : (
            <>
              {/* Co-Buying Cluster Signal Alert Banner */}
              {data?.cluster_signal && (
                <div className="p-3.5 rounded-xl bg-amber-500/10 border border-amber-500/30 flex flex-col sm:flex-row sm:items-center justify-between gap-2 text-xs text-amber-300 shadow-md">
                  <div className="flex items-center gap-2">
                    <Zap size={16} className="text-amber-400 fill-amber-400 animate-pulse shrink-0" />
                    <span className="font-extrabold font-mono uppercase tracking-wider">
                      Co-Buying Cluster Signal ({data.cluster_signal.distinct_buyers_count} Insiders Bought)
                    </span>
                  </div>
                  <span className="text-[11px] text-amber-200/80 font-medium">
                    Buyers: {data.cluster_signal.buyer_names.join(', ')}
                  </span>
                </div>
              )}

              {/* Asset Key Indicators Card */}
              <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
                {/* Current Price / YTD */}
                <div className="p-4 bg-slate-950/60 border border-slate-800 rounded-xl flex flex-col justify-between">
                  <span className="text-[11px] text-slate-400 uppercase tracking-wider font-semibold">Current Price</span>
                  <div className="mt-2 flex items-baseline justify-between">
                    <span className="text-2xl font-black text-slate-100 font-mono">
                      {data?.current_price != null ? `$${data.current_price.toFixed(2)}` : 'N/A'}
                    </span>
                    {data?.ytd_performance_pct != null && (
                      <span className={`inline-flex items-center text-xs font-bold px-2 py-0.5 rounded-full border ${
                        data.ytd_performance_pct >= 0 
                          ? 'bg-green-500/10 text-green-400 border-green-500/20' 
                          : 'bg-red-500/10 text-red-400 border-red-500/20'
                      }`}>
                        {data.ytd_performance_pct >= 0 ? <TrendingUp size={12} className="mr-1" /> : <TrendingDown size={12} className="mr-1" />}
                        {data.ytd_performance_pct >= 0 ? '+' : ''}{data.ytd_performance_pct.toFixed(1)}% YTD
                      </span>
                    )}
                  </div>
                </div>

                {/* Total Insiders */}
                <div className="p-4 bg-slate-950/60 border border-slate-800 rounded-xl flex flex-col justify-between">
                  <span className="text-[11px] text-slate-400 uppercase tracking-wider font-semibold">Distinct Insiders</span>
                  <div className="mt-2 flex items-center gap-2">
                    <Users className="text-cyan-400" size={20} />
                    <span className="text-2xl font-black text-slate-100 font-mono">{data?.distinct_insiders_count || 0}</span>
                  </div>
                </div>

                {/* Total Transactions */}
                <div className="p-4 bg-slate-950/60 border border-slate-800 rounded-xl flex flex-col justify-between">
                  <span className="text-[11px] text-slate-400 uppercase tracking-wider font-semibold font-mono">Total Filings</span>
                  <div className="mt-2 flex items-center gap-2">
                    <Activity className="text-purple-400" size={20} />
                    <span className="text-2xl font-black text-slate-100 font-mono">{data?.trade_count || 0}</span>
                  </div>
                </div>

                {/* Buy / Sell Sentiment Bar */}
                <div className="p-4 bg-slate-950/60 border border-slate-800 rounded-xl flex flex-col justify-between">
                  <div className="flex justify-between items-center text-[11px] font-semibold text-slate-400">
                    <span className="text-green-400">{buyCount} BUY ({buyPct}%)</span>
                    <span className="text-red-400">{sellCount} SELL ({sellPct}%)</span>
                  </div>
                  <div className="mt-3 w-full h-3 bg-slate-800 rounded-full overflow-hidden flex border border-slate-700/50">
                    <div style={{ width: `${buyPct}%` }} className="bg-green-500 transition-all duration-500" />
                    <div style={{ width: `${sellPct}%` }} className="bg-red-500 transition-all duration-500" />
                  </div>
                </div>
              </div>

              {/* Interactive Stock Price Chart with Insider Trade Markers */}
              <StockPriceChart
                ticker={data?.ticker || symbolOrIsin}
                currentPrice={data?.current_price}
                ytdPerf={data?.ytd_performance_pct}
                trades={trades}
              />

              {/* Insiders Summary Cards */}
              {data?.insiders && data.insiders.length > 0 && (
                <div className="space-y-3">
                  <h4 className="text-xs font-bold uppercase tracking-wider text-slate-400">
                    Insiders Trading {data.ticker}
                  </h4>
                  <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-3">
                    {data.insiders.map((insider) => {
                      const hasCustomPhoto = Boolean(insider.photo_url) && !imageErrors[insider.person_id];
                      return (
                        <div 
                          key={insider.person_id}
                          className="p-3 bg-slate-950/40 border border-slate-800 rounded-xl flex items-center justify-between gap-3 hover:border-slate-700 transition-colors"
                        >
                          <div className="flex items-center gap-2.5 min-w-0">
                            <div className="relative w-8 h-8 rounded-full overflow-hidden border border-slate-700 shrink-0 flex items-center justify-center font-bold text-white text-xs"
                              style={{ backgroundColor: getAvatarColor(insider.person_name) }}
                            >
                              {hasCustomPhoto ? (
                                <img
                                  src={insider.photo_url}
                                  alt={insider.person_name}
                                  className="w-full h-full object-cover"
                                  onError={() => handleImageError(insider.person_id)}
                                />
                              ) : (
                                <span>{getInitials(insider.person_name)}</span>
                              )}
                            </div>
                            <div className="min-w-0">
                              <div className="text-xs font-bold text-slate-200 truncate">{insider.person_name}</div>
                              <div className="text-[10px] text-slate-500 uppercase">{insider.person_category}</div>
                            </div>
                          </div>

                          <div className="text-right shrink-0">
                            <span className="text-[11px] font-extrabold text-cyan-400 font-mono">
                              {insider.trade_count} trade{insider.trade_count > 1 ? 's' : ''}
                            </span>
                            <div className="text-[10px] text-slate-400 flex gap-1 justify-end font-mono">
                              {insider.buy_count > 0 && <span className="text-green-400">+{insider.buy_count}B</span>}
                              {insider.sell_count > 0 && <span className="text-red-400">-{insider.sell_count}S</span>}
                            </div>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                </div>
              )}

              {/* Transactions Ledger */}
              <div className="space-y-4 pt-2">
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-slate-800 pb-3">
                  <h4 className="text-xs font-bold uppercase tracking-wider text-slate-400">
                    Transaction History ({filteredTrades.length})
                  </h4>

                  <div className="flex items-center gap-2">
                    {/* Export Buttons */}
                    <div className="flex items-center gap-1.5 mr-2">
                      <button
                        onClick={handleExportCSV}
                        title="Export transactions to CSV"
                        className="flex items-center gap-1 px-2.5 py-1 rounded-lg bg-slate-800 hover:bg-slate-700 border border-slate-700 text-[11px] font-semibold text-slate-300 transition-colors"
                      >
                        <Download size={11} className="text-cyan-400" />
                        <span>CSV</span>
                      </button>
                      <button
                        onClick={handleExportJSON}
                        title="Export transactions to JSON"
                        className="flex items-center gap-1 px-2.5 py-1 rounded-lg bg-slate-800 hover:bg-slate-700 border border-slate-700 text-[11px] font-semibold text-slate-300 transition-colors"
                      >
                        <Download size={11} className="text-purple-400" />
                        <span>JSON</span>
                      </button>
                    </div>

                    {/* Filter Pills */}
                    <div className="flex rounded-lg bg-slate-950 p-1 border border-slate-800">
                      {['ALL', 'BUY', 'SELL'].map((type) => (
                        <button
                          key={type}
                          onClick={() => setFilterType(type)}
                          className={`px-3 py-1 rounded-md text-[11px] font-semibold transition-all ${
                            filterType === type 
                              ? 'bg-cyan-500/20 text-cyan-400 border border-cyan-500/30' 
                              : 'text-slate-500 hover:text-slate-300'
                          }`}
                        >
                          {type}
                        </button>
                      ))}
                    </div>
                  </div>
                </div>

                {filteredTrades.length === 0 ? (
                  <div className="py-12 text-center text-xs text-slate-500 italic bg-slate-950/20 border border-slate-800 rounded-xl">
                    No transactions match the selected filter.
                  </div>
                ) : (
                  <div className="space-y-3">
                    {filteredTrades.map((t) => {
                      const hasPhoto = Boolean(t.person_photo_url) && !imageErrors[`trade-${t.id}`];
                      return (
                        <div 
                          key={t.id} 
                          className="p-4 bg-slate-950/50 border border-slate-800/80 rounded-xl space-y-3 hover:border-slate-700 transition-colors"
                        >
                          <div className="flex items-center justify-between">
                            <div className="flex items-center gap-3">
                              <div 
                                className="w-8 h-8 rounded-full overflow-hidden border border-slate-700 shrink-0 flex items-center justify-center font-bold text-white text-xs"
                                style={{ backgroundColor: getAvatarColor(t.person_name) }}
                              >
                                {hasPhoto ? (
                                  <img
                                    src={t.person_photo_url}
                                    alt={t.person_name}
                                    className="w-full h-full object-cover"
                                    onError={() => handleImageError(`trade-${t.id}`)}
                                  />
                                ) : (
                                  <span>{getInitials(t.person_name)}</span>
                                )}
                              </div>

                              <div>
                                <span className="text-[10px] text-cyan-400 font-mono uppercase font-semibold">
                                  {t.person_category}
                                </span>
                                <h5 className="text-sm font-bold text-slate-100">{t.person_name}</h5>
                              </div>
                            </div>

                            {/* BUY / SELL Badge */}
                            <div className={`px-3 py-1 rounded-full text-xs font-bold border font-mono ${
                              t.type === 'BUY' 
                                ? 'bg-green-500/10 text-green-400 border-green-500/20' 
                                : 'bg-red-500/10 text-red-400 border-red-500/20'
                            }`}>
                              {t.type}
                            </div>
                          </div>

                          {/* Trade Info Row */}
                          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 p-3 bg-slate-900/80 rounded-lg border border-slate-800 text-xs">
                            <div>
                              <span className="text-[10px] text-slate-500 uppercase block font-mono">Volume / Range</span>
                              <span className="font-bold text-slate-200 font-mono">{t.amount_range}</span>
                            </div>

                            <div>
                              <span className="text-[10px] text-slate-500 uppercase block font-mono">Trade Date</span>
                              <span className="font-semibold text-slate-300 flex items-center gap-1">
                                <Calendar size={11} className="text-slate-500" />
                                {new Date(t.trade_date).toLocaleDateString()}
                              </span>
                            </div>

                            <div>
                              <span className="text-[10px] text-slate-500 uppercase block font-mono">Price at Trade</span>
                              <span className="font-semibold text-slate-300 font-mono">
                                {t.price_at_transaction != null ? `$${t.price_at_transaction.toFixed(2)}` : 'N/A'}
                              </span>
                            </div>

                            <div>
                              <span className="text-[10px] text-slate-500 uppercase block font-mono">Return Since Trade</span>
                              {t.return_since_purchase_pct != null ? (
                                <span className={`font-bold font-mono ${t.return_since_purchase_pct >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                                  {t.return_since_purchase_pct >= 0 ? '+' : ''}{t.return_since_purchase_pct}%
                                </span>
                              ) : (
                                <span className="text-slate-500 font-mono">—</span>
                              )}
                            </div>
                          </div>

                          {/* AI Score & Source URL */}
                          <div className="flex justify-between items-center text-xs">
                            <div className="flex items-center gap-2">
                              {t.ai_score != null && <AIScoreBadge score={t.ai_score} />}
                              {t.source_url && (
                                <a 
                                  href={t.source_url} 
                                  target="_blank" 
                                  rel="noopener noreferrer"
                                  className="text-[11px] text-cyan-400 hover:underline flex items-center gap-1"
                                >
                                  View Official Source <ExternalLink size={10} />
                                </a>
                              )}
                            </div>

                            {t.filing_date && (
                              <span className="text-[10px] text-slate-500 font-mono">
                                Filed: {new Date(t.filing_date).toLocaleDateString()}
                              </span>
                            )}
                          </div>

                          {/* AI Evaluation Summary */}
                          {t.ai_summary && (
                            <p className="text-[11px] text-slate-400 leading-relaxed border-l-2 border-cyan-500/40 pl-3 py-1 bg-slate-900/40 rounded-r-md">
                              "{t.ai_summary}"
                            </p>
                          )}
                        </div>
                      );
                    })}
                  </div>
                )}
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
