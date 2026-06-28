import { useState, useCallback } from 'react';
import { useApi } from '../hooks/useApi';
import { getPersons, toggleFollow, getAllPerformance } from '../api/client';
import SearchBar from '../components/SearchBar';
import CategoryPills from '../components/CategoryPills';
import PersonCard from '../components/PersonCard';

export default function PortfoliosTab() {
  const [search, setSearch] = useState('');
  const [category, setCategory] = useState('All');

  const fetchPersons = useCallback(() => {
    const params = {};
    if (search) params.search = search;
    if (category !== 'All') params.category = category;
    return getPersons(params);
  }, [search, category]);

  const { data: personsData, loading, error, refetch } = useApi(fetchPersons, [search, category]);
  const { data: perfData } = useApi(getAllPerformance, []);

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

  return (
    <div className="animate-fade-in">
      <SearchBar onSearch={setSearch} />
      <CategoryPills active={category} onChange={setCategory} />

      <div className="px-4 pb-4 space-y-3">
        {loading && !personsData ? (
          // Skeleton loaders
          Array.from({ length: 4 }).map((_, i) => (
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
          personsData?.persons?.map((person, i) => (
            <div key={person.id} style={{ animationDelay: `${i * 0.05}s` }}>
              <PersonCard
                person={person}
                performance={perfMap}
                onToggleFollow={handleFollow}
              />
            </div>
          ))
        )}
      </div>
    </div>
  );
}
