import { useState, useCallback, useEffect } from 'react';
import { useApi } from '../hooks/useApi';
import { getPersons, toggleFollow, getAllPerformance, createPerson, getAvailablePersons, trackPerson, toggleSubscription, getInsights } from '../api/client';
import SearchBar from '../components/SearchBar';
import CategoryPills from '../components/CategoryPills';
import PersonCard from '../components/PersonCard';
import { Plus, Copy } from 'lucide-react';

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

function getTickerIsin(ticker) {
  const clean = (ticker || '').trim().toUpperCase();
  if (TICKER_INFO[clean]) {
    return TICKER_INFO[clean].isin;
  }
  return clean.endsWith('GERMANY') || clean.length > 5 
    ? `DE000A${clean.slice(0, 3)}1005` 
    : `US0${clean.slice(0, 3)}901002`;
}

export default function PortfoliosTab() {
  const [search, setSearch] = useState('');
  const [category, setCategory] = useState('All');
  const [sortBy, setSortBy] = useState('recent_trade');
  const [showAdd, setShowAdd] = useState(false);
  const [copiedIsin, setCopiedIsin] = useState(null);
  
  const handleCopyIsin = (e, isin) => {
    e.stopPropagation();
    navigator.clipboard.writeText(isin);
    setCopiedIsin(isin);
    setTimeout(() => setCopiedIsin(null), 2000);
  };
  
  const [form, setForm] = useState({ name: '', category: 'Congress', description: '', photo_url: '' });

  const fetchPersons = useCallback(() => {
    const params = {};
    if (search) params.search = search;
    if (category !== 'All') params.category = category;
    if (sortBy !== 'name') params.sort_by = sortBy;
    return getPersons(params);
  }, [search, category, sortBy]);

  const { data: personsData, loading, error, refetch } = useApi(fetchPersons, [search, category, sortBy]);
  const { data: perfData } = useApi(getAllPerformance, []);
  const { data: insights } = useApi(getInsights, []);

  // Build performance lookup
  const perfMap = {};
  if (perfData && Array.isArray(perfData)) {
    perfData.forEach(p => { perfMap[p.ticker] = p; });
  }

  const handleFollow = async (personId) => {
    try {
      await toggleFollow(personId);
      refetch();
    } catch (err) {
      console.error('Follow toggle failed:', err);
    }
  };

  const handleSubscribe = async (personId) => {
    try {
      await toggleSubscription(personId);
      refetch();
    } catch (err) {
      console.error('Subscription toggle failed:', err);
    }
  };

  const handleUntrack = async (personId) => {
    // Optimistic removal: instantly filter out the card from UI
    if (personsData?.persons) {
      personsData.persons = personsData.persons.filter(p => p.id !== personId);
    }
    try {
      await trackPerson(personId, false);
      refetch(); // sync with backend to confirm
    } catch (err) {
      console.error('Untrack failed:', err);
      refetch(); // revert on error
    }
  };

  const handleAddCustomPerson = async () => {
    if (!form.name) return;
    try {
      // Creates a new person with is_tracked=True on backend
      await createPerson({ ...form, is_tracked: true });
      setShowAdd(false);
      setForm({ name: '', category: 'Congress', description: '', photo_url: '' });
      refetch();
    } catch (err) {
      alert(err.message || 'Failed to track custom person');
    }
  };

  return (
    <div className="animate-fade-in space-y-4">
      {/* Insights Row */}
      {/* Insights Row */}
      {insights && (
        <div className="px-5 pt-3 grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-3">
          
          {/* Card 1: Most Active */}
          <div className="bg-surface/50 border border-border/80 rounded-xl p-3 flex flex-col justify-between shadow-md hover:border-border-bright transition-all">
            <span className="text-[10px] text-slate-500 font-medium uppercase tracking-wider">Most active</span>
            <div className="mt-2 space-y-1.5 flex-1 flex flex-col justify-center">
              {(insights.most_active_list || (insights.most_active ? [insights.most_active] : [])).slice(0, 2).map((item, idx) => (
                <div key={idx} className="flex items-center gap-2">
                  <div className="w-5 h-5 rounded-full overflow-hidden border border-border shrink-0 bg-surface-2 flex items-center justify-center text-[9px] font-bold text-slate-400">
                    {item.photo_url ? (
                      <img src={item.photo_url} className="w-full h-full object-cover" alt="" />
                    ) : (
                      item.name?.[0]
                    )}
                  </div>
                  <div className="min-w-0 flex-1 flex justify-between items-center text-[11px]">
                    <span className="font-bold text-slate-200 truncate pr-2" title={item.name}>{item.name}</span>
                    <span className="text-[9px] text-cyan-400 font-semibold shrink-0">{item.trades_count}t</span>
                  </div>
                </div>
              ))}
              {(!insights.most_active_list && !insights.most_active) && (
                <div className="text-[10px] text-slate-500 italic">No trades recorded</div>
              )}
            </div>
          </div>

          {/* Card 2: Biggest Outperformer */}
          <div className="bg-surface/50 border border-border/80 rounded-xl p-3 flex flex-col justify-between shadow-md hover:border-border-bright transition-all">
            <span className="text-[10px] text-slate-500 font-medium uppercase tracking-wider">Biggest outperformer</span>
            <div className="mt-2 space-y-1.5 flex-1 flex flex-col justify-center">
              {(insights.outperf_list || (insights.biggest_outperformer ? [insights.biggest_outperformer] : [])).slice(0, 2).map((item, idx) => (
                <div key={idx} className="flex items-center gap-2">
                  <div className="w-5 h-5 rounded-full overflow-hidden border border-border shrink-0 bg-surface-2 flex items-center justify-center text-[9px] font-bold text-slate-400">
                    {item.photo_url ? (
                      <img src={item.photo_url} className="w-full h-full object-cover" alt="" />
                    ) : (
                      item.name?.[0]
                    )}
                  </div>
                  <div className="min-w-0 flex-1 flex justify-between items-center text-[11px]">
                    <span className="font-bold text-slate-200 truncate pr-2" title={item.name}>{item.name}</span>
                    <span className="text-[9px] text-green-500 font-bold shrink-0">{item.perf_vs_spy?.split(" ")[0]}</span>
                  </div>
                </div>
              ))}
              {(!insights.outperf_list && !insights.biggest_outperformer) && (
                <div className="text-[10px] text-slate-500 italic">No trades recorded</div>
              )}
            </div>
          </div>

          {/* Card 3: Hot Stocks */}
          <div className="bg-surface/50 border border-border/80 rounded-xl p-3 flex flex-col justify-between shadow-md hover:border-border-bright transition-all">
            <span className="text-[10px] text-slate-500 font-medium uppercase tracking-wider">Hot stocks (60d)</span>
            <div className="mt-2 space-y-1.5 flex-1 flex flex-col justify-center">
              {insights.hot_stocks && insights.hot_stocks.slice(0, 3).map((stock, idx) => {
                const isin = getTickerIsin(stock.ticker);
                return (
                  <div key={stock.ticker} className="flex items-center justify-between text-[11px] gap-1">
                    <div className="flex items-center gap-1 min-w-0">
                      <span className="text-[9px] text-slate-500 font-mono">#{idx+1}</span>
                      <span className="font-bold text-slate-200 truncate">{stock.ticker}</span>
                      
                      {/* Copyable ISIN */}
                      <span 
                        onClick={(e) => handleCopyIsin(e, isin)}
                        title="Click to copy ISIN"
                        className="flex items-center gap-0.5 px-1 py-0.2 rounded text-[7px] bg-slate-800 hover:bg-slate-700 text-slate-400 hover:text-slate-200 border border-slate-700/30 cursor-pointer transition-all font-mono select-none"
                      >
                        {copiedIsin === isin ? 'Copied!' : isin}
                        {copiedIsin !== isin && <Copy size={5} />}
                      </span>
                    </div>
                    <div className="flex items-center gap-1 shrink-0 text-right">
                      <span className={`font-semibold text-[10px] ${stock.perf_pct?.startsWith('+') ? 'text-green-500' : stock.perf_pct?.startsWith('-') ? 'text-red-500' : 'text-slate-400'}`}>
                        {stock.perf_pct}
                      </span>
                      <span className="text-[8px] text-slate-500 font-medium">({stock.trades_count}t)</span>
                    </div>
                  </div>
                );
              })}
              {(!insights.hot_stocks || insights.hot_stocks.length === 0) && (
                <div className="text-[10px] text-slate-500 italic">No recent trades</div>
              )}
            </div>
          </div>

          {/* Card 4: Disclosure Lag */}
          <div className="bg-surface/50 border border-border/80 rounded-xl p-3 flex flex-col justify-between items-center text-center shadow-md hover:border-border-bright transition-all">
            <span className="text-[10px] text-slate-500 font-medium uppercase tracking-wider">Disclosure lag</span>
            <div className="mt-2 flex-1 flex flex-col justify-center items-center">
              <div className="text-sm font-extrabold" style={{ color: 'var(--text-bright)' }}>
                {insights.disclosure_lag?.median_days === 'N/A' ? 'N/A' : `${insights.disclosure_lag?.median_days}d`}{' '}
                <span className="text-[10px] text-slate-500 font-normal">median</span>
              </div>
              <div className="text-[10px] text-amber-500 font-semibold mt-1">
                {insights.disclosure_lag?.late_pct === 'N/A' ? 'No late trades' : `${insights.disclosure_lag?.late_pct} late`}
              </div>
            </div>
          </div>

          {/* Card 5: Biggest Trades */}
          <div className="bg-surface/50 border border-border/80 rounded-xl p-3 flex flex-col justify-between shadow-md hover:border-border-bright transition-all">
            <span className="text-[10px] text-slate-500 font-medium uppercase tracking-wider">Biggest Trades</span>
            <div className="mt-2 space-y-1.5 flex-1 flex flex-col justify-center">
              {(insights.biggest_trades_list || (insights.biggest_trade ? [insights.biggest_trade] : [])).slice(0, 2).map((item, idx) => (
                <div key={idx} className="flex justify-between items-center text-[10px] min-w-0">
                  <div className="min-w-0 flex-1 pr-1">
                    <div className="text-[10px] font-bold text-slate-200 truncate">{item.person_name}</div>
                    <div className="text-[8px] text-slate-500 truncate">{item.ticker} · {item.date}</div>
                  </div>
                  <div className="text-[10px] font-extrabold text-cyan-400 shrink-0">{item.amount}</div>
                </div>
              ))}
              {(!insights.biggest_trades_list && !insights.biggest_trade) && (
                <div className="text-[10px] text-slate-500 italic">No trades recorded</div>
              )}
            </div>
          </div>

        </div>
      )}

      {/* Filter and Search Bar */}
      <div className="px-5 mt-3 flex items-start gap-2 relative z-30">
        <div className="flex-1 space-y-3">
          <CategoryPills active={category} onChange={setCategory} />
          <div className="flex gap-2">
            <div className="flex-1">
              <SearchBar onSearch={setSearch} />
            </div>
            <select 
              value={sortBy} 
              onChange={e => setSortBy(e.target.value)}
              className="px-3 py-2 bg-slate-900/50 dark:bg-slate-950/50 border border-slate-700/50 rounded-xl text-xs text-slate-300 outline-none focus:border-cyan-500/50 appearance-none"
            >
              <option value="recent_trade">Most Recent Trade</option>
              <option value="trade_count">Most Trades</option>
              <option value="performance">Best Performance</option>
              <option value="name">Name A–Z</option>
            </select>
          </div>
        </div>
        <button onClick={() => setShowAdd(!showAdd)} title="Track New Person"
          className="p-2.5 bg-slate-800/80 dark:bg-slate-800/80 border border-slate-700/50 hover:bg-slate-700 rounded-xl mt-3 flex items-center justify-center shrink-0 transition-colors">
          <Plus size={16} className="text-cyan-400" />
        </button>
      </div>

      {showAdd && (
        <div className="mx-5 mb-4 glass-card p-4 space-y-3 animate-slide-up relative z-20">
          <div className="flex justify-between items-center pb-1">
            <h3 className="text-xs font-semibold text-slate-200 dark:text-slate-100">Track Custom Portfolio</h3>
            <button 
              onClick={() => setShowAdd(false)}
              className="text-[10px] text-slate-400 hover:text-slate-300 font-semibold"
            >
              Cancel
            </button>
          </div>

          <div className="space-y-3">
            <div className="grid grid-cols-2 gap-2">
              <input placeholder="Name (e.g. Warren Buffett)" value={form.name} 
                onChange={e => setForm(f => ({...f, name: e.target.value}))} 
                className="w-full px-3 py-2 rounded-lg bg-slate-900/80 dark:bg-slate-950 border border-slate-700/50 text-xs text-slate-200 dark:text-slate-300 outline-none focus:border-blue-500/50" />
              <select value={form.category} 
                onChange={e => setForm(f => ({...f, category: e.target.value}))} 
                className="w-full px-3 py-2 rounded-lg bg-slate-900/80 dark:bg-slate-950 border border-slate-700/50 text-xs text-slate-200 dark:text-slate-300 outline-none focus:border-blue-500/50">
                <option value="Congress">Congress</option>
                <option value="Senate">Senate</option>
                <option value="Fund Manager">Fund Manager</option>
                <option value="Corporate Insider">Corporate Insider</option>
              </select>
            </div>
            <input placeholder="Ausrichtung / Beschreibung" value={form.description} 
              onChange={e => setForm(f => ({...f, description: e.target.value}))} 
              className="w-full px-3 py-2 rounded-lg bg-slate-900/80 dark:bg-slate-950 border border-slate-700/50 text-xs text-slate-200 dark:text-slate-300 outline-none focus:border-blue-500/50" />
            <input placeholder="Foto URL (optional)" value={form.photo_url} 
              onChange={e => setForm(f => ({...f, photo_url: e.target.value}))} 
              className="w-full px-3 py-2 rounded-lg bg-slate-900/80 dark:bg-slate-950 border border-slate-700/50 text-xs text-slate-200 dark:text-slate-300 outline-none focus:border-blue-500/50" />
            <button onClick={handleAddCustomPerson} 
              className="w-full py-2 rounded-lg bg-blue-500 text-white text-xs font-semibold hover:bg-blue-600 transition-colors">
              Track Custom Person
            </button>
          </div>
        </div>
      )}

      <div className="px-4 pb-4 grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
        {loading && !personsData ? (
          // Skeleton loaders
          Array.from({ length: 6 }).map((_, i) => (
            <div key={i} className="glass-card p-4 space-y-3" style={{ animationDelay: `${i * 0.1}s` }}>
              <div className="flex items-center gap-3">
                <div className="skeleton h-5 w-32" />
                <div className="skeleton h-4 w-16" />
              </div>
              <div className="rounded-xl p-3" style={{ background: 'rgba(2, 6, 23, 0.5)' }}>
                <div className="flex gap-2">
                  <div className="skeleton h-4 w-12" />
                  <div className="skeleton h-4 w-8" />
                  <div className="skeleton h-4 w-24" />
                </div>
                <div className="flex items-center justify-between mt-2">
                  <div className="skeleton h-5 w-16" />
                  <div className="skeleton h-4 w-20" />
                </div>
              </div>
            </div>
          ))
        ) : error ? (
          <div className="text-center py-12">
            <p className="text-red-400 text-sm mb-2">Failed to load data</p>
            <p className="text-slate-600 text-xs">{error}</p>
            <button onClick={refetch}
              className="mt-3 px-4 py-1.5 rounded-lg text-xs font-medium bg-blue-500/15 text-blue-400 hover:bg-blue-500/25 transition-colors">
              Retry
            </button>
          </div>
        ) : personsData?.persons?.length === 0 ? (
          <div className="text-center py-12">
            <p className="text-slate-500 text-sm">No persons found</p>
            <p className="text-slate-600 text-xs mt-1">Try adjusting your search or filters</p>
          </div>
        ) : (
          [...(personsData?.persons || [])]
            .sort((a, b) => {
              if (a.is_followed && !b.is_followed) return -1;
              if (!a.is_followed && b.is_followed) return 1;
              return a.name.localeCompare(b.name);
            })
            .map((person, i) => (
              <div key={person.id} style={{ animationDelay: `${i * 0.05}s` }}>
                <PersonCard
                  person={person}
                  performance={perfMap}
                  onToggleFollow={handleFollow}
                  onToggleSubscribe={handleSubscribe}
                  onUntrack={handleUntrack}
                  onRefresh={refetch}
                />
              </div>
            ))
        )}
      </div>
    </div>
  );
}
