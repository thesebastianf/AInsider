import { useState, useRef } from 'react';
import { Star, Bell, Trash2, User, Copy, X, Loader2, Plus, Pencil, RotateCcw } from 'lucide-react';
import { updateDisplayName, uploadPersonPhoto, deletePersonPhoto } from '../api/client';

const TICKER_INFO = {
  AAPL: { name: 'Apple Inc.', isin: 'US0378331005' },
  MSFT: { name: 'Microsoft Corporation', isin: 'US5949181045' },
  TSLA: { name: 'Tesla, Inc.', isin: 'US88160R1014' },
  NVDA: { name: 'NVIDIA Corporation', isin: 'US67066G1040' },
  TT: { name: 'Trane Technologies plc', isin: 'IE00B6S95B28' },
  SAP: { name: 'SAP SE', isin: 'DE0007164600' },
  BMW: { name: 'Bayerische Motoren Werke AG', isin: 'DE0005190003' },
  AMZN: { name: 'Amazon.com, Inc.', isin: 'US0231351067' },
  GOOGL: { name: 'Alphabet Inc.', isin: 'US02079K3059' },
  GOOG: { name: 'Alphabet Inc.', isin: 'US02079K1079' },
  META: { name: 'Meta Platforms, Inc.', isin: 'US30303M1027' },
  NFLX: { name: 'Netflix, Inc.', isin: 'US64110L1061' },
  RHEINMETALL: { name: 'Rheinmetall AG', isin: 'DE0007030009' },
  SIEMENS: { name: 'Siemens AG', isin: 'DE0007236101' },
};

function getTickerDetails(ticker) {
  const clean = (ticker || '').trim().toUpperCase();
  if (TICKER_INFO[clean]) {
    return TICKER_INFO[clean];
  }
  // Dynamic generation for others
  const isin = clean.endsWith('GERMANY') || clean.length > 5 
    ? `DE000A${clean.slice(0, 3)}1005` 
    : `US0${clean.slice(0, 3)}901002`;
  return {
    name: `${clean} Corp.`,
    isin: isin
  };
}

const getInitials = (name) => {
  const parts = (name || '').trim().split(' ');
  if (parts.length >= 2) {
    return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase();
  }
  return (name || 'U').slice(0, 2).toUpperCase();
};

const getAvatarColor = (name) => {
  let hash = 0;
  const str = name || '';
  for (let i = 0; i < str.length; i++) {
    hash = str.charCodeAt(i) + ((hash << 5) - hash);
  }
  const hue = Math.abs(hash % 360);
  return `hsl(${hue}, 60%, 35%)`;
};

export default function PersonCard({ person, performance, onToggleFollow, onToggleSubscribe, onUntrack, onTrack, onRefresh }) {
  const [showHistory, setShowHistory] = useState(false);
  const [trades, setTrades] = useState([]);
  const [loading, setLoading] = useState(false);
  const [copiedIsin, setCopiedIsin] = useState(null);
  const [imgError, setImgError] = useState(false);
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);
  const [showEdit, setShowEdit] = useState(false);
  const [editName, setEditName] = useState('');
  const [editSaving, setEditSaving] = useState(false);
  const [uploadingPhoto, setUploadingPhoto] = useState(false);
  const [ytdMode, setYtdMode] = useState(false);
  const fileInputRef = useRef(null);

  // Effective values: custom overrides auto
  const effectiveName = person.display_name || person.name;
  const effectivePhoto = person.custom_photo_url || person.photo_url;

  const trade = person.latest_trade;
  const perf = trade ? performance?.[trade.ticker] : null;

  const handleOpenHistory = async (e) => {
    if (showEdit) return; // don't open history when editing
    setShowHistory(true);
    setLoading(true);
    try {
      const res = await fetch(`/api/trades?person_id=${person.id}`);
      const data = await res.json();
      setTrades(data.trades || []);
    } catch (e) {
      console.error(e);
    }
    setLoading(false);
  };

  const handleOpenEdit = (e) => {
    e.stopPropagation();
    setEditName(person.display_name || '');
    setShowEdit(true);
  };

  const handleSaveName = async () => {
    setEditSaving(true);
    try {
      await updateDisplayName(person.id, editName);
      onRefresh?.();
    } catch (e) { console.error(e); }
    setEditSaving(false);
    setShowEdit(false);
  };

  const handleRevertName = async () => {
    setEditSaving(true);
    try {
      await updateDisplayName(person.id, null);
      onRefresh?.();
    } catch (e) { console.error(e); }
    setEditSaving(false);
    setShowEdit(false);
  };

  const handlePhotoUpload = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setUploadingPhoto(true);
    try {
      await uploadPersonPhoto(person.id, file);
      onRefresh?.();
    } catch (err) { console.error(err); }
    setUploadingPhoto(false);
  };

  const handleDeletePhoto = async () => {
    setUploadingPhoto(true);
    try {
      await deletePersonPhoto(person.id);
      onRefresh?.();
    } catch (err) { console.error(err); }
    setUploadingPhoto(false);
  };

  const handleCopyIsin = (e, isin) => {
    e.stopPropagation();
    navigator.clipboard.writeText(isin);
    setCopiedIsin(isin);
    setTimeout(() => setCopiedIsin(null), 2000);
  };

  return (
    <>
      <div 
        onClick={handleOpenHistory}
        className="bg-surface rounded-xl p-4 border border-border shadow-lg relative overflow-hidden backdrop-blur-sm animate-fade-in transition-all hover:border-border-bright cursor-pointer hover:shadow-cyan-950/10 hover:shadow-2xl"
      >
        {/* Subtle Gradient Background for active subscribers */}
        {person.is_subscribed && (
          <div className="absolute top-0 right-0 w-32 h-32 bg-cyan-500/10 rounded-bl-[100px] pointer-events-none transition-opacity duration-500" />
        )}
        
        <div className="flex justify-between items-start mb-3 relative z-10 gap-2">
          <div className="flex gap-4 min-w-0 flex-1">
            {/* Avatar with edit overlay */}
            <div className="w-14 h-14 rounded-full overflow-hidden bg-surface-2 border-2 border-border shrink-0 flex items-center justify-center relative group">
              {effectivePhoto && !imgError ? (
                <img 
                  src={effectivePhoto} 
                  alt={effectiveName} 
                  onError={() => setImgError(true)}
                  className="w-full h-full object-cover" 
                />
              ) : (
                <div 
                  className="w-full h-full flex items-center justify-center text-sm font-extrabold text-slate-100 select-none"
                  style={{ backgroundColor: getAvatarColor(person.name) }}
                >
                  {getInitials(effectiveName)}
                </div>
              )}
              {/* Edit overlay on hover (tracked persons) */}
              {person.is_tracked && (
                <button
                  onClick={handleOpenEdit}
                  className="absolute inset-0 bg-black/50 flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity rounded-full"
                  title="Edit person"
                >
                  {uploadingPhoto ? <Loader2 size={14} className="animate-spin text-white" /> : <Pencil size={14} className="text-white" />}
                </button>
              )}
              <input ref={fileInputRef} type="file" accept="image/*" className="hidden" onChange={handlePhotoUpload} />
            </div>
            
            <div className="min-w-0 flex-1">
              <h3 className="text-sm md:text-base xl:text-sm font-bold leading-tight flex items-center gap-1.5 min-w-0"
                style={{ color: 'var(--text-bright)' }}
                title={person.name}
              >
                <span className="truncate">{effectiveName}</span>
                {person.display_name && (
                  <span className="text-[9px] text-slate-500 font-normal shrink-0" title={`Original: ${person.name}`}>alias</span>
                )}
                {!person.is_active && (
                  <span className="px-1.5 py-0.5 rounded text-[8px] font-bold bg-red-500/15 text-red-500 border border-red-500/20 uppercase tracking-wider shrink-0">
                    Retired
                  </span>
                )}
              </h3>
              <span className="text-[10px] text-cyan-500 dark:text-cyan-400 font-semibold uppercase tracking-wider font-mono">{person.category}</span>
            </div>
          </div>
          
          <div className="flex items-center gap-1 z-20 shrink-0">
            {person.is_tracked ? (
              <>
                {/* Subscribe Button */}
                <button 
                  onClick={(e) => { e.stopPropagation(); onToggleSubscribe(person.id); }} 
                  className="p-1.5 bg-surface-2 rounded-full hover:bg-surface-3 transition-colors border border-border"
                  title={person.is_subscribed ? "Unsubscribe from alerts" : "Subscribe to alerts"}
                >
                  <Bell className={`h-3.5 w-3.5 transition-all ${
                    person.is_subscribed 
                      ? 'text-yellow-500 fill-yellow-500 drop-shadow-[0_0_8px_rgba(250,204,21,0.5)]' 
                      : 'text-slate-400 dark:text-slate-500'
                  }`} />
                </button>


                {/* Untrack Button */}
                <button 
                  onClick={(e) => { 
                    e.stopPropagation(); 
                    setShowDeleteConfirm(true);
                  }} 
                  className="p-1.5 bg-surface-2 rounded-full hover:bg-red-500/10 hover:border-red-500/30 text-slate-400 hover:text-red-500 transition-colors border border-border"
                  title="Remove from Dashboard"
                >
                  <Trash2 className="h-3.5 w-3.5" />
                </button>
              </>
            ) : (
              /* Track Button */
              <button 
                onClick={(e) => { e.stopPropagation(); onTrack && onTrack(person.id); }} 
                className="px-2.5 py-1 bg-emerald-500/25 text-emerald-400 hover:bg-emerald-500/35 border border-emerald-500/35 rounded-lg text-[10px] font-bold transition-all flex items-center gap-1 hover:scale-105 active:scale-95 duration-200"
                title="Add to Portfolios"
              >
                <Plus size={10} /> Track
              </button>
            )}
          </div>
        </div>

        {/* Stats Header with YTD Toggle */}
        <div className="flex items-center justify-between mb-2 mt-1 relative z-10">
          <div className="flex gap-1">
            <button
              onClick={(e) => { e.stopPropagation(); setYtdMode(false); }}
              className={`px-2 py-0.5 rounded-full text-[9px] font-bold border transition-all ${!ytdMode ? 'bg-cyan-600/20 text-cyan-400 border-cyan-500/40' : 'bg-slate-800 text-slate-500 border-slate-700'}`}
            >
              All-Time
            </button>
            <button
              onClick={(e) => { e.stopPropagation(); setYtdMode(true); }}
              className={`px-2 py-0.5 rounded-full text-[9px] font-bold border transition-all ${ytdMode ? 'bg-amber-500/20 text-amber-400 border-amber-500/40' : 'bg-slate-800 text-slate-500 border-slate-700'}`}
            >
              YTD
            </button>
          </div>
          {/* Date range */}
          {person.first_trade_date && person.last_trade_date && (
            <span className="text-[9px] text-slate-600 font-mono">
              {new Date(person.first_trade_date).getFullYear()} – {new Date(person.last_trade_date + 'T00:00:00').toLocaleDateString('en-US', { month: 'short', year: '2-digit' })}
            </span>
          )}
        </div>

        {/* Condensed Aggregated Statistics */}
        <div className="grid grid-cols-2 gap-2 mb-3 relative z-10">
          <div className="bg-surface-2 p-2 rounded-lg border border-border/80 text-center">
            <span className="text-[9px] text-slate-500 uppercase tracking-wider block">
              {ytdMode ? 'YTD Trades' : 'Total Trades'}
            </span>
            <span className="text-xs font-extrabold text-slate-200">
              {ytdMode ? (person.ytd_trade_count ?? 0) : person.trade_count}
            </span>
          </div>
          <div className="bg-surface-2 p-2 rounded-lg border border-border/80 text-center">
            <span className="text-[9px] text-slate-500 uppercase tracking-wider block">Last 30 Days</span>
            <span className="text-xs font-extrabold text-slate-200">{person.trade_count_30d}</span>
          </div>
        </div>

        <div className="flex justify-between items-center text-[11px] py-1 mt-1 border-b border-border/40 relative z-10">
          <span className="text-slate-500 dark:text-slate-400">
            Tendency{ytdMode ? <span className="text-amber-500 ml-1">(YTD)</span> : ''}
          </span>
          <span className="font-semibold text-slate-300">
            <span className="text-green-500 font-bold">
              {ytdMode ? (person.ytd_buy_count ?? 0) : person.buy_count} BUY
            </span>
            <span className="text-slate-600 px-1">/</span>
            <span className="text-red-500 font-bold">
              {ytdMode ? (person.ytd_sell_count ?? 0) : person.sell_count} SELL
            </span>
          </span>
        </div>

        <div className="flex justify-between items-center text-[11px] py-1 border-b border-border/40 relative z-10">
          <span className="text-slate-500 dark:text-slate-400">Avg. Trade Return</span>
          {person.avg_trade_return_pct !== null && person.avg_trade_return_pct !== undefined ? (
            <span className={`font-bold flex items-center gap-1 ${
              person.avg_trade_return_pct >= 0 ? 'text-green-500 dark:text-green-400' : 'text-red-500 dark:text-red-400'
            }`}>
              {person.avg_trade_return_pct >= 0 ? '+' : ''}{person.avg_trade_return_pct}%
            </span>
          ) : (
            <span className="text-slate-600 dark:text-slate-500">Pending</span>
          )}
        </div>

        {/* Latest Trade Quick Preview */}
        {trade ? (
          <div className="mt-2.5 p-1.5 bg-surface-2/60 rounded border border-border/40 text-[10px] text-slate-300 flex justify-between items-center relative z-10">
            <span className="truncate max-w-[150px]">
              Latest: <span className={trade.type === 'BUY' ? 'text-green-500 font-bold' : 'text-red-500 font-bold'}>{trade.type}</span> {trade.ticker}
            </span>
            <span className="font-mono text-slate-400 text-[9px]">{new Date(trade.trade_date).toLocaleDateString()}</span>
          </div>
        ) : (
          <div className="mt-2.5 p-1.5 bg-surface-2/30 rounded border border-border/30 text-[10px] text-slate-400 italic text-center relative z-10">
            No trades recorded
          </div>
        )}
      </div>


      {/* Trade History Modal */}
      {showHistory && (
        <div 
          onClick={() => setShowHistory(false)}
          className="fixed inset-0 bg-slate-950/80 backdrop-blur-sm z-[9999] flex items-center justify-center p-4"
        >
          <div 
            onClick={(e) => e.stopPropagation()}
            className="bg-slate-900 border border-slate-800 rounded-2xl w-full max-w-lg max-h-[80vh] flex flex-col shadow-2xl overflow-hidden animate-slide-up"
          >
            {/* Modal Header */}
            <div className="flex items-center justify-between p-4 border-b border-slate-800 bg-slate-950/50">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-full overflow-hidden bg-slate-800 shrink-0 flex items-center justify-center">
                  {person.photo_url && !imgError ? (
                    <img 
                      src={person.photo_url} 
                      alt={person.name} 
                      onError={() => setImgError(true)}
                      className="w-full h-full object-cover" 
                    />
                  ) : (
                    <div 
                      className="w-full h-full flex items-center justify-center text-xs font-bold text-slate-100 select-none"
                      style={{ backgroundColor: getAvatarColor(person.name) }}
                    >
                      {getInitials(person.name)}
                    </div>
                  )}
                </div>
                <div>
                  <h4 className="font-bold text-slate-100 text-sm leading-snug">{person.name}</h4>
                  <span className="text-[10px] text-cyan-400 font-semibold tracking-wider uppercase font-mono">{person.category}</span>
                </div>
              </div>
              <button 
                onClick={() => setShowHistory(false)}
                className="p-1.5 rounded-lg hover:bg-slate-800 text-slate-400 hover:text-slate-200 transition-colors"
              >
                <X size={16} />
              </button>
            </div>

            {/* Modal Body */}
            <div className="flex-1 overflow-y-auto p-4 space-y-3 min-h-0">
              {loading ? (
                <div className="flex flex-col items-center justify-center py-12 gap-2 text-slate-500">
                  <Loader2 className="animate-spin" size={24} />
                  <span className="text-xs">Loading trade history...</span>
                </div>
              ) : trades.length === 0 ? (
                <div className="text-center py-12 text-slate-500 italic text-xs">
                  No trade history recorded for this person.
                </div>
              ) : (
                trades.map((t) => {
                  const details = getTickerDetails(t.ticker);
                  return (
                    <div key={t.id} className="p-3 bg-slate-950/50 border border-slate-800/60 rounded-xl space-y-2.5 hover:border-slate-700 transition-colors">
                      <div className="flex items-center justify-between">
                        <div className="flex flex-wrap items-center gap-2">
                          <span className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                            t.type === 'BUY' ? 'bg-green-500/10 text-green-400 border border-green-500/10' : 'bg-red-500/10 text-red-400 border border-red-500/10'
                          }`}>
                            {t.type}
                          </span>
                          <span className="text-xs font-bold text-slate-200">{t.ticker}</span>
                          <span className="text-[10px] text-slate-500 font-medium truncate max-w-[150px]">{details.name}</span>
                          
                          {/* Copyable ISIN */}
                          <span 
                            onClick={(e) => handleCopyIsin(e, details.isin)}
                            title="Click to copy ISIN"
                            className="flex items-center gap-1 px-1.5 py-0.5 rounded text-[8px] bg-slate-800 hover:bg-slate-700 text-slate-400 hover:text-slate-200 border border-slate-700/30 cursor-pointer transition-all font-mono select-none"
                          >
                            {copiedIsin === details.isin ? 'Copied!' : details.isin}
                            {copiedIsin !== details.isin && <Copy size={8} />}
                          </span>
                        </div>
                        <div className="flex items-center gap-1.5 shrink-0">
                          <span className="text-[9px] text-slate-500 font-mono">
                            {new Date(t.trade_date).toLocaleDateString()}
                          </span>
                          {t.source_url && (
                            <a href={t.source_url} target="_blank" rel="noopener noreferrer" 
                              className="text-cyan-500 hover:text-cyan-400 text-[10px] font-semibold flex items-center hover:underline"
                            >
                              Link ↗
                            </a>
                          )}
                        </div>
                      </div>
                      
                      <div className="flex justify-between items-center text-xs">
                        <span className="text-slate-400 font-medium">{t.amount_range}</span>
                        <div className="flex items-center gap-2">
                          {t.price_at_transaction && (
                            <span className="text-[10px] text-slate-500 font-mono">
                              {t.type === 'BUY' ? 'Bought' : 'Sold'} at ${t.price_at_transaction.toFixed(2)}
                            </span>
                          )}
                          {t.return_since_purchase_pct !== null && t.return_since_purchase_pct !== undefined && (
                            <span className={`px-1.5 py-0.5 rounded text-[9px] font-bold ${
                              t.return_since_purchase_pct >= 0 ? 'bg-green-500/10 text-green-400 border border-green-500/10' : 'bg-red-500/10 text-red-400 border border-red-500/10'
                            } border`}>
                              {t.return_since_purchase_pct >= 0 ? '+' : ''}{t.return_since_purchase_pct}%
                            </span>
                          )}
                          {t.ai_score && (
                            <span className={`px-1.5 py-0.5 rounded text-[9px] font-bold ${
                              t.ai_score >= 7 ? 'bg-cyan-500/10 text-cyan-400 border border-cyan-500/10' : 'bg-slate-800 text-slate-400'
                            }`}>
                              AI: {t.ai_score}/10
                            </span>
                          )}
                        </div>
                      </div>
                      
                      {t.ai_summary && (
                        <p className="text-[10px] text-slate-400 leading-relaxed bg-slate-900/60 p-2 rounded-lg border border-slate-800/40">
                          {t.ai_summary}
                        </p>
                      )}
                    </div>
                  );
                })
              )}
            </div>
          </div>
        </div>
      )}

      {/* ── Delete Confirmation Modal ─────────────────────────── */}
      {showDeleteConfirm && (
        <div
          onClick={() => setShowDeleteConfirm(false)}
          className="fixed inset-0 bg-slate-950/80 backdrop-blur-sm z-[99999] flex items-center justify-center p-4 animate-fade-in"
        >
          <div
            onClick={(e) => e.stopPropagation()}
            className="bg-slate-900 border border-red-500/20 rounded-2xl w-full max-w-sm shadow-2xl shadow-red-950/30 overflow-hidden animate-fade-in"
          >
            {/* Header */}
            <div className="p-5 border-b border-slate-800">
              <div className="flex items-center gap-3 mb-1">
                <div
                  className="w-9 h-9 rounded-full flex items-center justify-center text-xs font-extrabold text-white shrink-0"
                  style={{ backgroundColor: getAvatarColor(person.name) }}
                >
                  {getInitials(person.name)}
                </div>
                <div>
                  <p className="text-sm font-bold text-slate-100 leading-snug">{person.name}</p>
                  <p className="text-[10px] text-slate-500 font-mono uppercase tracking-wider">{person.category}</p>
                </div>
              </div>
            </div>

            {/* Body */}
            <div className="p-5">
              <div className="flex items-start gap-3">
                <div className="w-8 h-8 rounded-full bg-red-500/10 flex items-center justify-center shrink-0 mt-0.5">
                  <Trash2 className="h-4 w-4 text-red-400" />
                </div>
                <div>
                  <h3 className="text-sm font-semibold text-slate-100 mb-1">Remove from Dashboard?</h3>
                  <p className="text-xs text-slate-400 leading-relaxed">
                    This person will be moved back to <span className="text-cyan-400 font-medium">Discover</span>.
                    Their trade history is preserved and you can re-add them anytime.
                  </p>
                </div>
              </div>
            </div>

            {/* Actions */}
            <div className="flex gap-2 px-5 pb-5">
              <button
                onClick={() => setShowDeleteConfirm(false)}
                className="flex-1 py-2 px-4 rounded-lg text-xs font-semibold bg-slate-800 hover:bg-slate-700 text-slate-300 border border-slate-700 transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={() => {
                  setShowDeleteConfirm(false);
                  onUntrack(person.id);
                }}
                className="flex-1 py-2 px-4 rounded-lg text-xs font-semibold bg-red-500/15 hover:bg-red-500/25 text-red-400 border border-red-500/20 transition-colors"
              >
                Remove
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ── Edit Modal ────────────────────────────────────────── */}
      {showEdit && (
        <div
          className="fixed inset-0 z-[60] flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm"
          onClick={() => setShowEdit(false)}
        >
          <div
            className="bg-slate-900 border border-slate-700 rounded-2xl w-full max-w-sm shadow-2xl"
            onClick={e => e.stopPropagation()}
          >
            <div className="flex items-center justify-between p-5 border-b border-slate-800">
              <h3 className="text-sm font-semibold text-slate-100">Edit Person</h3>
              <button onClick={() => setShowEdit(false)} className="text-slate-500 hover:text-slate-300">
                <X size={16} />
              </button>
            </div>

            <div className="p-5 space-y-5">
              {/* Photo Upload */}
              <div>
                <label className="block text-[10px] font-bold text-slate-500 uppercase tracking-wider mb-2">Profile Photo</label>
                <div className="flex items-center gap-3">
                  <div className="w-14 h-14 rounded-full overflow-hidden border-2 border-slate-700 shrink-0 flex items-center justify-center bg-surface-2">
                    {(person.custom_photo_url || person.photo_url) && !imgError ? (
                      <img src={person.custom_photo_url || person.photo_url} alt={effectiveName} className="w-full h-full object-cover" onError={() => setImgError(true)} />
                    ) : (
                      <div className="w-full h-full flex items-center justify-center text-sm font-extrabold text-slate-100" style={{ backgroundColor: getAvatarColor(person.name) }}>
                        {getInitials(effectiveName)}
                      </div>
                    )}
                  </div>
                  <div className="flex flex-col gap-2 flex-1">
                    <button
                      onClick={() => fileInputRef.current?.click()}
                      disabled={uploadingPhoto}
                      className="text-xs py-1.5 px-3 rounded-lg bg-blue-600/20 hover:bg-blue-600/30 text-blue-400 border border-blue-500/30 transition-colors font-semibold"
                    >
                      {uploadingPhoto ? 'Uploading…' : 'Upload Photo'}
                    </button>
                    {person.custom_photo_url && (
                      <button
                        onClick={handleDeletePhoto}
                        disabled={uploadingPhoto}
                        className="text-xs py-1.5 px-3 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-400 border border-slate-700 transition-colors"
                      >
                        Remove Custom Photo
                      </button>
                    )}
                  </div>
                </div>
              </div>

              {/* Display Name */}
              <div>
                <label className="block text-[10px] font-bold text-slate-500 uppercase tracking-wider mb-2">
                  Display Name <span className="text-slate-600 normal-case font-normal">(original: {person.name})</span>
                </label>
                <input
                  type="text"
                  value={editName}
                  onChange={e => setEditName(e.target.value)}
                  placeholder={person.name}
                  className="w-full px-3 py-2 bg-slate-800 border border-slate-700 rounded-lg text-sm text-slate-200 placeholder-slate-600 outline-none focus:border-cyan-500/60"
                />
                <p className="text-[10px] text-slate-600 mt-1">The original name is kept as the unique ID. Deduplication always uses the original.</p>
              </div>
            </div>

            <div className="flex gap-2 px-5 pb-5">
              {person.display_name && (
                <button
                  onClick={handleRevertName}
                  disabled={editSaving}
                  className="flex items-center gap-1.5 py-2 px-3 rounded-lg text-xs font-semibold bg-slate-800 hover:bg-slate-700 text-slate-400 border border-slate-700 transition-colors"
                  title="Revert to original name"
                >
                  <RotateCcw size={12} /> Revert
                </button>
              )}
              <button
                onClick={() => setShowEdit(false)}
                className="flex-1 py-2 px-4 rounded-lg text-xs font-semibold bg-slate-800 hover:bg-slate-700 text-slate-300 border border-slate-700 transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={handleSaveName}
                disabled={editSaving}
                className="flex-1 py-2 px-4 rounded-lg text-xs font-semibold bg-cyan-600/20 hover:bg-cyan-600/30 text-cyan-400 border border-cyan-500/30 transition-colors"
              >
                {editSaving ? 'Saving…' : 'Save'}
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
