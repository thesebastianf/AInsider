import { useState, useEffect, useCallback } from 'react';
import { useApi } from '../hooks/useApi';
import { getAvailablePersons } from '../api/client';
import SearchBar from '../components/SearchBar';
import CategoryPills from '../components/CategoryPills';
import PersonCard from '../components/PersonCard';
import { Compass, Loader2 } from 'lucide-react';

export default function DiscoverTab() {
  const [search, setSearch] = useState('');
  const [category, setCategory] = useState('All');
  const [sortBy, setSortBy] = useState('name');
  const [trackingId, setTrackingId] = useState(null);

  const fetchAvailable = useCallback(() => {
    const params = {};
    if (search) params.search = search;
    if (category !== 'All') params.category = category;
    if (sortBy !== 'name') params.sort_by = sortBy;
    return getAvailablePersons(params);
  }, [search, category, sortBy]);

  const { data, loading, error, refetch } = useApi(fetchAvailable, [search, category, sortBy]);
  const persons = data?.persons || [];

  const handleTrack = async (personId) => {
    setTrackingId(personId);
    try {
      await fetch(`/api/persons/${personId}/track?is_tracked=true`, {
        method: 'PUT',
      });
      // Small timeout for fluid transition, then refetch
      setTimeout(() => {
        refetch();
        setTrackingId(null);
      }, 500);
    } catch (err) {
      console.error('Failed to start tracking person:', err);
      setTrackingId(null);
    }
  };

  return (
    <div className="flex-1 overflow-y-auto pb-[calc(env(safe-area-inset-bottom)+80px)]">
      
      {/* Premium Discover Header Section */}
      <div className="px-5 pt-4 pb-3 flex flex-col gap-1 border-b border-border/40 bg-slate-950/20 backdrop-blur-md">
        <div className="flex items-center gap-2">
          <Compass className="h-5 w-5 text-cyan-400 drop-shadow-[0_0_8px_rgba(6,182,212,0.4)]" />
          <h2 className="text-lg font-extrabold uppercase tracking-wide" style={{ color: 'var(--text-bright)' }}>
            Discover Catalog
          </h2>
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
            <option value="name">Sort by Name</option>
            <option value="trade_count">Most Trades</option>
          </select>
        </div>
      </div>

      {/* Grid of Discovered Persons */}
      <div className="px-5 mt-4">
        {loading && !trackingId ? (
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
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {persons.map(p => (
              <div 
                key={p.id} 
                className={`transition-all duration-300 ${trackingId === p.id ? 'opacity-30 scale-95 pointer-events-none' : ''}`}
              >
                <PersonCard 
                  person={p}
                  performance={null}
                  onToggleFollow={() => {}}
                  onToggleSubscribe={() => {}}
                  onUntrack={() => {}}
                  onTrack={handleTrack}
                />
              </div>
            ))}
          </div>
        )}
      </div>

    </div>
  );
}
