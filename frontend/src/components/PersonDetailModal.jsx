import { useState, useEffect } from 'react';
import { X, Calendar, ExternalLink, Loader2, User, Plus, Check, Download } from 'lucide-react';
import { getTrades, trackPerson } from '../api/client';
import { getInitials, getAvatarColor } from '../utils/avatarUtils';
import { openSymbolOverview } from '../utils/symbolHelper';
import { exportToCSV, exportToJSON } from '../utils/exportUtils';
import AIScoreBadge from './AIScoreBadge';

export default function PersonDetailModal({ person, onClose, onRefresh }) {
  const [trades, setTrades] = useState([]);
  const [loading, setLoading] = useState(true);
  const [isTracked, setIsTracked] = useState(person?.is_tracked || false);
  const [trackingLoading, setTrackingLoading] = useState(false);
  const [imgError, setImgError] = useState(false);

  useEffect(() => {
    if (!person?.id) return;
    let isMounted = true;
    setLoading(true);

    getTrades({ person_id: person.id, limit: 100 })
      .then((res) => {
        if (isMounted) {
          setTrades(res.trades || []);
          setLoading(false);
        }
      })
      .catch((err) => {
        if (isMounted) {
          setLoading(false);
        }
      });

    return () => {
      isMounted = false;
    };
  }, [person?.id]);

  useEffect(() => {
    const handleKeyDown = (e) => {
      if (e.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [onClose]);

  const handleToggleTrack = async () => {
    if (!person?.id) return;
    setTrackingLoading(true);
    const newTrackState = !isTracked;
    try {
      await trackPerson(person.id, newTrackState);
      setIsTracked(newTrackState);
      if (onRefresh) onRefresh();
    } catch (err) {
      console.error('Failed to toggle track status:', err);
    } finally {
      setTrackingLoading(false);
    }
  };

  const handleExportCSV = () => {
    if (!trades.length) return;
    const exportRows = trades.map(t => ({
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
    exportToCSV(`${person?.name || 'person'}_trades`, exportRows);
  };

  const handleExportJSON = () => {
    if (!trades.length) return;
    exportToJSON(`${person?.name || 'person'}_trades`, trades);
  };

  if (!person) return null;

  const photo = person.custom_photo_url || person.photo_url;
  const name = person.display_name || person.name;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 sm:p-6 bg-slate-950/80 backdrop-blur-md animate-fade-in">
      <div 
        className="relative w-full max-w-3xl max-h-[85vh] flex flex-col bg-slate-900 border border-slate-700/60 rounded-2xl shadow-2xl overflow-hidden"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header Bar */}
        <div className="px-6 py-4 border-b border-slate-800 flex justify-between items-center bg-slate-950/40">
          <div className="flex items-center gap-3">
            <div 
              className="relative w-12 h-12 rounded-full overflow-hidden border-2 border-slate-700 shrink-0 flex items-center justify-center font-bold text-white text-base shadow-md"
              style={{ backgroundColor: getAvatarColor(person.name) }}
            >
              {photo && !imgError ? (
                <img
                  src={photo}
                  alt={name}
                  className="w-full h-full object-cover"
                  onError={() => setImgError(true)}
                />
              ) : (
                <span>{getInitials(name)}</span>
              )}
            </div>

            <div>
              <div className="flex items-center gap-2">
                <h3 className="text-lg font-bold text-slate-100">{name}</h3>
                <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-cyan-500/10 text-cyan-400 border border-cyan-500/20 uppercase font-mono">
                  {person.category}
                </span>
              </div>
              <p className="text-xs text-slate-400 mt-0.5">
                Detailed filing profile & transaction history
              </p>
            </div>
          </div>

          <div className="flex items-center gap-2">
            <button
              onClick={handleToggleTrack}
              disabled={trackingLoading}
              className={`px-3 py-1.5 rounded-xl text-xs font-bold transition-all flex items-center gap-1.5 ${
                isTracked 
                  ? 'bg-slate-800 text-slate-300 border border-slate-700 hover:bg-slate-700' 
                  : 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/30 hover:bg-emerald-500/30'
              }`}
            >
              {trackingLoading ? (
                <Loader2 size={12} className="animate-spin" />
              ) : isTracked ? (
                <>
                  <Check size={12} className="text-emerald-400" />
                  <span>Tracking</span>
                </>
              ) : (
                <>
                  <Plus size={12} />
                  <span>Track Filer</span>
                </>
              )}
            </button>

            <button
              onClick={onClose}
              className="p-2 rounded-full text-slate-400 hover:text-white hover:bg-slate-800 transition-colors"
            >
              <X size={20} />
            </button>
          </div>
        </div>

        {/* Modal Content */}
        <div className="flex-1 overflow-y-auto p-6 space-y-4">
          <div className="flex justify-between items-center border-b border-slate-800 pb-3">
            <h4 className="text-xs font-bold uppercase tracking-wider text-slate-400">
              Recorded Filings ({trades.length})
            </h4>

            {/* Export CSV / JSON */}
            <div className="flex items-center gap-1.5">
              <button
                onClick={handleExportCSV}
                disabled={!trades.length}
                title="Export person trades to CSV"
                className="flex items-center gap-1 px-2.5 py-1 rounded-lg bg-slate-800 hover:bg-slate-700 border border-slate-700 text-[11px] font-semibold text-slate-300 transition-colors disabled:opacity-40"
              >
                <Download size={11} className="text-cyan-400" />
                <span>CSV</span>
              </button>
              <button
                onClick={handleExportJSON}
                disabled={!trades.length}
                title="Export person trades to JSON"
                className="flex items-center gap-1 px-2.5 py-1 rounded-lg bg-slate-800 hover:bg-slate-700 border border-slate-700 text-[11px] font-semibold text-slate-300 transition-colors disabled:opacity-40"
              >
                <Download size={11} className="text-purple-400" />
                <span>JSON</span>
              </button>
            </div>
          </div>

          {loading ? (
            <div className="flex flex-col items-center justify-center py-16 text-slate-400 gap-2">
              <Loader2 className="animate-spin text-cyan-400" size={28} />
              <span className="text-xs font-mono">Loading trade filings...</span>
            </div>
          ) : trades.length === 0 ? (
            <div className="py-12 text-center text-xs text-slate-500 italic bg-slate-950/20 border border-slate-800 rounded-xl">
              No transactions recorded for this filer yet.
            </div>
          ) : (
            <div className="space-y-3">
              {trades.map((t) => (
                <div 
                  key={t.id}
                  className="p-4 bg-slate-950/50 border border-slate-800/80 rounded-xl space-y-3 hover:border-slate-700 transition-colors"
                >
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <button
                        onClick={() => {
                          onClose();
                          openSymbolOverview(t.ticker);
                        }}
                        className="text-base font-extrabold text-cyan-400 hover:text-cyan-300 hover:underline font-mono transition-colors"
                        title="View symbol overview"
                      >
                        {t.ticker}
                      </button>
                    </div>

                    <div className={`px-2.5 py-0.5 rounded-full text-xs font-bold border font-mono ${
                      t.type === 'BUY' 
                        ? 'bg-green-500/10 text-green-400 border-green-500/20' 
                        : 'bg-red-500/10 text-red-400 border-red-500/20'
                    }`}>
                      {t.type}
                    </div>
                  </div>

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
                      <span className="text-[10px] text-slate-500 uppercase block font-mono">Return Since Purchase</span>
                      {t.return_since_purchase_pct != null ? (
                        <span className={`font-bold font-mono ${t.return_since_purchase_pct >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                          {t.return_since_purchase_pct >= 0 ? '+' : ''}{t.return_since_purchase_pct}%
                        </span>
                      ) : (
                        <span className="text-slate-500 font-mono">—</span>
                      )}
                    </div>
                  </div>

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
                          Source Filing <ExternalLink size={10} />
                        </a>
                      )}
                    </div>

                    {t.filing_date && (
                      <span className="text-[10px] text-slate-500 font-mono">
                        Filed: {new Date(t.filing_date).toLocaleDateString()}
                      </span>
                    )}
                  </div>

                  {t.ai_summary && (
                    <p className="text-[11px] text-slate-400 leading-relaxed border-l-2 border-cyan-500/40 pl-3 py-1 bg-slate-900/40 rounded-r-md">
                      "{t.ai_summary}"
                    </p>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
