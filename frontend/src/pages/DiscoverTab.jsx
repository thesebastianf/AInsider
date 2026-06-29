import { useState, useEffect, useCallback } from 'react';
import { useApi } from '../hooks/useApi';
import { getAvailablePersons } from '../api/client';
import SearchBar from '../components/SearchBar';
import CategoryPills from '../components/CategoryPills';
import PersonCard from '../components/PersonCard';
import { Compass, Loader2, ChevronLeft, ChevronRight } from 'lucide-react';

export default function DiscoverTab() {
  const [search, setSearch] = useState('');
  const [category, setCategory] = useState('All');
  const [sortBy, setSortBy] = useState('recent_trade');
  const [trackingId, setTrackingId] = useState(null);
  const [page, setPage] = useState(1);
  const limit = 48; // Standard grid count

  // Reset page when filters change
  useEffect(() => {
    setPage(1);
  }, [search, category, sortBy]);

  const fetchAvailable = useCallback(() => {
    const params = {
      limit,
      offset: (page - 1) * limit
    };
    if (search) params.search = search;
    if (category !== 'All') params.category = category;
    if (sortBy !== 'name') params.sort_by = sortBy;
    return getAvailablePersons(params);
  }, [search, category, sortBy, page]);

  const { data, loading, error, refetch } = useApi(fetchAvailable, [search, category, sortBy, page]);
  const rawPersons = data?.persons || [];
  const total = data?.total || 0;

  // Optimistic UI state: filter out target instantly when tracking starts
  const [hiddenIds, setHiddenIds] = useState([]);
  const persons = rawPersons.filter(p => !hiddenIds.includes(p.id));

  // Reset hidden list on page or filter changes
  useEffect(() => {
    setHiddenIds([]);
  }, [page, search, category, sortBy]);

  const handleTrack = async (personId) => {
    // Hide item instantly from UI
    setHiddenIds(prev => [...prev, personId]);
    setTrackingId(personId);
    try {
      await fetch(`/api/persons/${personId}/track?is_tracked=true`, {
        method: 'PUT',
      });
      // Soft background refetch to keep data in sync, no layout shifts
      refetch();
    } catch (err) {
      console.error('Failed to start tracking person:', err);
      // Re-show item on failure
      setHiddenIds(prev => prev.filter(id => id !== personId));
    } finally {
      setTrackingId(null);
    }
  };

  const totalPages = Math.ceil(total / limit) || 1;

  return (
    <div className="flex-1 overflow-y-auto pb-[calc(env(safe-area-inset-bottom)+80px)]">
      
      {/* Premium Discover Header Section */}
      <div className="px-5 pt-4 pb-3 flex flex-col gap-1 border-b border-border/40 bg-slate-950/20 backdrop-blur-md">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Compass className="h-5 w-5 text-cyan-400 drop-shadow-[0_0_8px_rgba(6,182,212,0.4)]" />
            <h2 className="text-lg font-extrabold uppercase tracking-wide" style={{ color: 'var(--text-bright)' }}>
              Discover Catalog
            </h2>
          </div>
          {total > 0 && (
            <span className="text-[10px] text-slate-500 font-mono">
              {total} profiles found
            </span>
          )}
        </div>
        <p className="text-[11px] text-slate-500 max-w-md mt-0.5 leading-relaxed">
          Browse and search all corporate board members, politicians, and fund managers discovered in active data feeds. Add them to start tracking AI evaluations.
        </p>
      </div>

      {/* Filter and Search Bar */}
      <div className="px-5 mt-3 space-y-3">
        <CategoryPills active={category} onChange={setCategory} />
        <div className="flex gap-2">
          <div className="flex-1">
            <SearchBar onSearch={setSearch} placeholder="Search discovered filers..." />
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

      {/* Grid of Discovered Persons */}
      <div className="px-5 mt-4">
        {loading && !trackingId && persons.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-20 gap-2 text-slate-500">
            <Loader2 className="animate-spin text-cyan-400" size={28} />
            <span className="text-xs">Scanning available profiles...</span>
          </div>
        ) : error ? (
          <div className="text-center py-20 text-red-400 text-xs bg-red-950/10 rounded-xl border border-red-500/10">
            Failed to scan discovered filers.
          </div>
        ) : persons.length === 0 ? (
          <div className="text-center py-20 text-slate-500 italic text-xs bg-slate-900/30 rounded-xl border border-border/40">
            No new discovered filers found matching filters.
          </div>
        ) : (
          <div className="space-y-6">
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {persons.map(p => (
                <div 
                  key={p.id} 
                  className="transition-all duration-300"
                >
                  <PersonCard 
                    person={p}
                    performance={null}
                    onToggleFollow={() => {}}
                    onToggleSubscribe={() => {}}
                    onUntrack={() => {}}
                    onTrack={handleTrack}
                    onRefresh={refetch}
                  />
                </div>
              ))}
            </div>

            {/* Pagination Controls */}
            {totalPages > 1 && (
              <div className="flex items-center justify-between border-t border-border/40 pt-4 mt-2">
                <span className="text-[11px] text-slate-500">
                  Page <span className="text-slate-300 font-bold">{page}</span> of <span className="text-slate-300 font-bold">{totalPages}</span>
                </span>
                <div className="flex gap-2">
                  <button
                    onClick={() => setPage(p => Math.max(1, p - 1))}
                    disabled={page === 1}
                    className="p-1.5 rounded-lg border border-border bg-slate-900 text-slate-400 hover:text-slate-200 disabled:opacity-30 disabled:pointer-events-none transition-colors"
                  >
                    <ChevronLeft size={16} />
                  </button>
                  <button
                    onClick={() => setPage(p => Math.min(totalPages, p + 1))}
                    disabled={page === totalPages}
                    className="p-1.5 rounded-lg border border-border bg-slate-900 text-slate-400 hover:text-slate-200 disabled:opacity-30 disabled:pointer-events-none transition-colors"
                  >
                    <ChevronRight size={16} />
                  </button>
                </div>
              </div>
            )}
          </div>
        )}
      </div>

    </div>
  );
}
