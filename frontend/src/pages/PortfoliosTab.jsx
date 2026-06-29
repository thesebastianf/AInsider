import { useState, useCallback, useEffect } from 'react';
import { useApi } from '../hooks/useApi';
import { getPersons, toggleFollow, getAllPerformance, createPerson, getAvailablePersons, trackPerson, toggleSubscription, getInsights } from '../api/client';
import SearchBar from '../components/SearchBar';
import CategoryPills from '../components/CategoryPills';
import PersonCard from '../components/PersonCard';
import { Plus } from 'lucide-react';

export default function PortfoliosTab() {
  const [search, setSearch] = useState('');
  const [category, setCategory] = useState('All');
  const [sortBy, setSortBy] = useState('recent_trade');
  const [showAdd, setShowAdd] = useState(false);
  
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
      {insights && (
        <div className="px-5 pt-3 grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-3">
          
          {/* Card 1: Most Active */}
          <div className="bg-surface/50 border border-border/80 rounded-xl p-3 flex flex-col justify-between shadow-md hover:border-border-bright transition-all">
            <span className="text-[10px] text-slate-500 font-medium uppercase tracking-wider">Most active</span>
            <div className="flex items-center gap-2 mt-2">
              <div className="w-8 h-8 rounded-full overflow-hidden border border-border shrink-0 bg-surface-2 flex items-center justify-center">
                {insights.most_active?.photo_url ? (
                  <img src={insights.most_active.photo_url} className="w-full h-full object-cover" alt="" />
                ) : (
                  <div className="text-[10px] text-slate-500 font-bold uppercase">{insights.most_active?.name?.[0]}</div>
                )}
              </div>
              <div className="min-w-0">
                <div className="text-xs font-bold truncate" style={{ color: 'var(--text-bright)' }}>{insights.most_active?.name}</div>
                <div className="text-[10px] text-cyan-400 font-semibold">{insights.most_active?.trades_count} trades</div>
              </div>
            </div>
          </div>

          {/* Card 2: Biggest Outperformer */}
          <div className="bg-surface/50 border border-border/80 rounded-xl p-3 flex flex-col justify-between shadow-md hover:border-border-bright transition-all">
            <span className="text-[10px] text-slate-500 font-medium uppercase tracking-wider">Biggest outperformer</span>
            <div className="flex items-center gap-2 mt-2">
              <div className="w-8 h-8 rounded-full overflow-hidden border border-border shrink-0 bg-surface-2 flex items-center justify-center">
                {insights.biggest_outperformer?.photo_url ? (
                  <img src={insights.biggest_outperformer.photo_url} className="w-full h-full object-cover" alt="" />
                ) : (
                  <div className="text-[10px] text-slate-500 font-bold uppercase">{insights.biggest_outperformer?.name?.[0]}</div>
                )}
              </div>
              <div className="min-w-0">
                <div className="text-xs font-bold truncate" style={{ color: 'var(--text-bright)' }}>{insights.biggest_outperformer?.name}</div>
                <div className="text-[10px] text-green-500 font-bold">{insights.biggest_outperformer?.perf_vs_spy}</div>
              </div>
            </div>
          </div>

          {/* Card 3: Hot Stock */}
          <div className="bg-surface/50 border border-border/80 rounded-xl p-3 flex flex-col justify-between shadow-md hover:border-border-bright transition-all">
            <span className="text-[10px] text-slate-500 font-medium uppercase tracking-wider">Hot stock (60d)</span>
            <div className="flex items-center gap-2 mt-2">
              <div className={`px-1.5 py-0.5 rounded text-[10px] font-bold ${insights.hot_stock?.perf_pct?.startsWith('+') ? 'bg-green-500/15 text-green-500' : 'bg-red-500/15 text-red-500'} border border-transparent`}>
                {insights.hot_stock?.ticker}
              </div>
              <div className="min-w-0">
                <div className={`text-xs font-bold ${insights.hot_stock?.perf_pct?.startsWith('+') ? 'text-green-500' : 'text-red-500'}`}>{insights.hot_stock?.perf_pct}</div>
                <div className="text-[10px] text-slate-500">{insights.hot_stock?.trades_count} trades · 60d</div>
              </div>
            </div>
          </div>

          {/* Card 4: Disclosure Lag */}
          <div className="bg-surface/50 border border-border/80 rounded-xl p-3 flex flex-col justify-between shadow-md hover:border-border-bright transition-all">
            <span className="text-[10px] text-slate-500 font-medium uppercase tracking-wider">Disclosure lag</span>
            <div className="mt-1">
              <div className="text-xs font-bold" style={{ color: 'var(--text-bright)' }}>
                {insights.disclosure_lag?.median_days === 'N/A' ? 'N/A' : `${insights.disclosure_lag?.median_days}d`} <span className="text-[10px] text-slate-500 font-normal">median</span>
              </div>
              <div className="text-[10px] text-amber-500 font-semibold mt-0.5">
                {insights.disclosure_lag?.late_pct === 'N/A' ? 'No late trades' : `${insights.disclosure_lag?.late_pct} late`}
              </div>
            </div>
          </div>

          {/* Card 5: Biggest Single Trade */}
          <div className="bg-surface/50 border border-border/80 rounded-xl p-3 flex flex-col justify-between shadow-md hover:border-border-bright transition-all">
            <span className="text-[10px] text-slate-500 font-medium uppercase tracking-wider">Biggest single trade</span>
            <div className="mt-1">
              <div className="text-xs font-bold text-cyan-400">{insights.biggest_trade?.amount}</div>
              <div className="text-[9px] text-slate-500 truncate">
                {insights.biggest_trade?.person_name} · {insights.biggest_trade?.date}
              </div>
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
