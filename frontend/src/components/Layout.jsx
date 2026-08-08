import { Bell, Sun, Moon, RefreshCw, Search, Loader2, User, TrendingUp, Compass } from 'lucide-react';
import AppLogo from './AppLogo';
import { useState, useEffect, useRef } from 'react';
import { unifiedLookup } from '../api/client';
import SymbolOverviewModal from './SymbolOverviewModal';
import PersonDetailModal from './PersonDetailModal';
import { getInitials, getAvatarColor } from '../utils/avatarUtils';

export default function Layout({ children, activeTab, bottomNav }) {
  const [theme, setTheme] = useState(() => localStorage.getItem('ainsider-theme') || 'dark');
  const [isSyncing, setIsSyncing] = useState(false);
  const [selectedSymbol, setSelectedSymbol] = useState(null);
  const [selectedPerson, setSelectedPerson] = useState(null);

  // Search state
  const [searchQuery, setSearchQuery] = useState('');
  const [searchResults, setSearchResults] = useState({ persons: [], assets: [] });
  const [isSearching, setIsSearching] = useState(false);
  const [showDropdown, setShowDropdown] = useState(false);
  const [imgErrors, setImgErrors] = useState({});
  const searchRef = useRef(null);

  useEffect(() => {
    const isDark = theme === 'dark';
    document.documentElement.classList.toggle('dark', isDark);
    document.documentElement.classList.toggle('light-theme', !isDark);
    localStorage.setItem('ainsider-theme', theme);
  }, [theme]);

  // Listen for global custom event to open symbol overview from anywhere
  useEffect(() => {
    const handleOpenSymbol = (e) => {
      if (e.detail) {
        setSelectedSymbol(e.detail);
      }
    };
    window.addEventListener('open-symbol-overview', handleOpenSymbol);
    return () => window.removeEventListener('open-symbol-overview', handleOpenSymbol);
  }, []);

  // Debounced search for universal lookup (persons + assets)
  useEffect(() => {
    if (!searchQuery.trim()) {
      setSearchResults({ persons: [], assets: [] });
      setShowDropdown(false);
      return;
    }

    const timer = setTimeout(async () => {
      setIsSearching(true);
      try {
        const res = await unifiedLookup(searchQuery.trim());
        setSearchResults(res || { persons: [], assets: [] });
        setShowDropdown(true);
      } catch (err) {
        console.error('Failed to execute unified lookup:', err);
      } finally {
        setIsSearching(false);
      }
    }, 220);

    return () => clearTimeout(timer);
  }, [searchQuery]);

  // Close dropdown on click outside
  useEffect(() => {
    const handleClickOutside = (e) => {
      if (searchRef.current && !searchRef.current.contains(e.target)) {
        setShowDropdown(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  useEffect(() => {
    const fetchStatus = async () => {
      try {
        const res = await fetch('/api/system/stats');
        const data = await res.json();
        setIsSyncing(data.is_pipeline_running);
      } catch (e) {
        // ignore
      }
    };
    fetchStatus();
    const interval = setInterval(fetchStatus, 10000);
    return () => clearInterval(interval);
  }, []);

  const toggleTheme = () => {
    setTheme(t => (t === 'dark' ? 'light' : 'dark'));
  };

  const handleImageError = (id) => {
    setImgErrors((prev) => ({ ...prev, [id]: true }));
  };

  const handleSelectPerson = (person) => {
    setSelectedPerson(person);
    setShowDropdown(false);
    setSearchQuery('');
  };

  const handleSelectAsset = (ticker) => {
    setSelectedSymbol(ticker);
    setShowDropdown(false);
    setSearchQuery('');
  };

  const hasPersons = (searchResults.persons || []).length > 0;
  const hasAssets = (searchResults.assets || []).length > 0;
  const hasResults = hasPersons || hasAssets;

  return (
    <div className="w-full max-w-[1440px] h-full relative flex flex-col overflow-hidden border-x border-slate-800/20 dark:border-slate-800/50 mx-auto"
      style={{ background: 'var(--bg-main)', color: 'var(--text-main)' }}
    >
      {/* ─── Ambient Glow am oberen Rand ────────────────── */}
      <div className="absolute top-0 left-0 w-full h-40 bg-[image:var(--ambient-glow)] pointer-events-none z-0" />

      {/* ─── Header ─────────────────────────────────────── */}
      <header className="px-5 pt-[calc(env(safe-area-inset-top)+12px)] pb-3 flex justify-between items-center border-b border-slate-800/80 sticky top-0 z-20"
        style={{
          background: 'var(--header-bg)',
          backdropFilter: 'blur(12px)',
          WebkitBackdropFilter: 'blur(12px)',
        }}
      >
        <div className="flex items-center gap-3">
          <AppLogo className="drop-shadow-[0_0_10px_rgba(6,182,212,0.3)]" />
          <div className="flex flex-col">
            <h1 className="text-xl font-bold text-white tracking-wide leading-none">
              <span className="text-transparent bg-clip-text bg-gradient-to-r from-blue-400 to-cyan-400 font-extrabold tracking-tighter">AI</span>nsider
            </h1>
            <span className="text-[9px] text-slate-400 uppercase tracking-[0.2em] mt-0.5">Global Tracker</span>
          </div>
        </div>

        {/* ─── Universal Lookup Search Bar ────────────────────── */}
        <div ref={searchRef} className="relative hidden sm:flex flex-1 max-w-lg mx-4">
          <div className="relative w-full flex items-center">
            <Search size={14} className="absolute left-3.5 text-slate-400 pointer-events-none" />
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              onFocus={() => { if (searchQuery.trim()) setShowDropdown(true); }}
              placeholder="Universal Lookup: Search People, Symbols, ISINs (e.g. Pelosi, AAPL)..."
              className="w-full pl-9 pr-8 py-1.5 bg-slate-900/80 dark:bg-slate-950/80 border border-slate-700/60 rounded-full text-xs text-slate-200 placeholder-slate-500 focus:outline-none focus:border-cyan-500/60 transition-all shadow-inner"
            />
            {isSearching && (
              <Loader2 size={12} className="absolute right-3.5 text-cyan-400 animate-spin" />
            )}
          </div>

          {/* Search Suggestions Dropdown */}
          {showDropdown && (
            <div className="absolute top-full left-0 w-full mt-2 bg-slate-900 border border-slate-700 rounded-xl shadow-2xl overflow-hidden z-50 animate-fade-in max-h-[75vh] overflow-y-auto">
              {!hasResults ? (
                <div className="px-4 py-4 text-xs text-slate-400 italic text-center">
                  No people or stock assets found matching "{searchQuery}"
                </div>
              ) : (
                <div className="divide-y divide-slate-800/80">
                  {/* Category 1: People / Insiders */}
                  {hasPersons && (
                    <div>
                      <div className="px-4 py-2 bg-slate-950/60 text-[10px] font-extrabold uppercase tracking-wider text-slate-400 flex items-center gap-1.5 border-b border-slate-800/60">
                        <User size={12} className="text-cyan-400" />
                        <span>Filers & Insiders ({searchResults.persons.length})</span>
                      </div>
                      <div className="divide-y divide-slate-800/40">
                        {searchResults.persons.map((person) => {
                          const hasPhoto = Boolean(person.photo_url) && !imgErrors[`search-p-${person.id}`];
                          return (
                            <button
                              key={`person-${person.id}`}
                              onClick={() => handleSelectPerson(person)}
                              className="w-full px-4 py-2.5 flex items-center justify-between hover:bg-slate-800/80 text-left transition-colors group"
                            >
                              <div className="flex items-center gap-3 min-w-0">
                                <div 
                                  className="w-8 h-8 rounded-full overflow-hidden border border-slate-700 shrink-0 flex items-center justify-center font-bold text-white text-xs shadow-sm"
                                  style={{ backgroundColor: getAvatarColor(person.name) }}
                                >
                                  {hasPhoto ? (
                                    <img
                                      src={person.photo_url}
                                      alt={person.name}
                                      className="w-full h-full object-cover"
                                      onError={() => handleImageError(`search-p-${person.id}`)}
                                    />
                                  ) : (
                                    <span>{getInitials(person.name)}</span>
                                  )}
                                </div>
                                <div className="min-w-0">
                                  <div className="text-xs font-bold text-slate-200 group-hover:text-cyan-300 transition-colors truncate">
                                    {person.display_name || person.name}
                                  </div>
                                  <div className="text-[10px] text-slate-400 flex items-center gap-1.5">
                                    <span className="text-cyan-400 uppercase font-mono font-semibold">{person.category}</span>
                                    <span>•</span>
                                    <span className={person.is_tracked ? 'text-emerald-400 font-semibold' : 'text-slate-500'}>
                                      {person.is_tracked ? 'Tracked' : 'Discovered'}
                                    </span>
                                  </div>
                                </div>
                              </div>

                              <div className="text-right shrink-0">
                                <span className="text-[11px] font-semibold text-slate-300 font-mono">
                                  {person.trade_count} trade{person.trade_count !== 1 ? 's' : ''}
                                </span>
                              </div>
                            </button>
                          );
                        })}
                      </div>
                    </div>
                  )}

                  {/* Category 2: Stocks & ISINs */}
                  {hasAssets && (
                    <div>
                      <div className="px-4 py-2 bg-slate-950/60 text-[10px] font-extrabold uppercase tracking-wider text-slate-400 flex items-center gap-1.5 border-b border-slate-800/60">
                        <TrendingUp size={12} className="text-amber-400" />
                        <span>Stock Assets & ISINs ({searchResults.assets.length})</span>
                      </div>
                      <div className="divide-y divide-slate-800/40">
                        {searchResults.assets.map((asset) => (
                          <button
                            key={`asset-${asset.ticker}`}
                            onClick={() => handleSelectAsset(asset.ticker)}
                            className="w-full px-4 py-2.5 flex items-center justify-between hover:bg-slate-800/80 text-left transition-colors group"
                          >
                            <div className="flex items-center gap-3">
                              <span className="px-2 py-0.5 rounded bg-cyan-500/10 border border-cyan-500/20 text-cyan-400 font-mono font-bold text-xs">
                                {asset.ticker}
                              </span>
                              <div>
                                <div className="text-xs font-bold text-slate-200 group-hover:text-cyan-300 transition-colors">
                                  {asset.company_name}
                                </div>
                                {asset.isin && (
                                  <div className="text-[10px] text-slate-500 font-mono">
                                    ISIN: {asset.isin}
                                  </div>
                                )}
                              </div>
                            </div>

                            <div className="text-right">
                              <span className="text-[11px] font-semibold text-slate-300 block font-mono">
                                {asset.trade_count} trade{asset.trade_count !== 1 ? 's' : ''}
                              </span>
                              <span className="text-[10px] text-slate-500 block">
                                {asset.distinct_insiders_count} insider{asset.distinct_insiders_count !== 1 ? 's' : ''}
                              </span>
                            </div>
                          </button>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              )}
            </div>
          )}
        </div>

        <div className="flex items-center gap-3">
          {/* Sync Indicator */}
          {isSyncing && (
            <div className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-full bg-blue-500/10 border border-blue-500/20 text-blue-400">
              <RefreshCw size={12} className="animate-spin" />
              <span className="text-[10px] font-bold tracking-wide uppercase">Syncing</span>
            </div>
          )}
          
          {/* Theme Toggler */}
          <button 
            onClick={toggleTheme}
            title={theme === 'dark' ? 'Switch to Light Mode' : 'Switch to Dark Mode'}
            className="p-2 bg-slate-800/50 dark:bg-slate-800/50 rounded-full hover:bg-slate-700/50 transition-colors border border-slate-700/50 text-slate-300 hover:text-white"
          >
            {theme === 'dark' ? <Sun className="h-5 w-5 text-amber-400" /> : <Moon className="h-5 w-5 text-indigo-500" />}
          </button>
          
          <button className="relative p-2 bg-slate-800/50 rounded-full hover:bg-slate-700 transition-colors border border-slate-700/50 group">
            <Bell className="h-5 w-5 text-slate-300 group-hover:text-white transition-colors" />
            <span className="absolute top-1.5 right-1.5 w-2 h-2 bg-red-500 rounded-full shadow-[0_0_8px_rgba(239,68,68,0.8)] animate-pulse" />
          </button>
        </div>
      </header>

      {/* Mobile Universal Search Row (shown on small screens) */}
      <div ref={searchRef} className="px-4 py-2 sm:hidden border-b border-slate-800/80 bg-slate-950/60 relative">
        <div className="relative flex items-center">
          <Search size={14} className="absolute left-3 text-slate-400 pointer-events-none" />
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            onFocus={() => { if (searchQuery.trim()) setShowDropdown(true); }}
            placeholder="Search People, Symbols, ISINs..."
            className="w-full pl-9 pr-8 py-1.5 bg-slate-900 border border-slate-700/60 rounded-full text-xs text-slate-200 placeholder-slate-500 focus:outline-none focus:border-cyan-500/60"
          />
          {isSearching && (
            <Loader2 size={12} className="absolute right-3 text-cyan-400 animate-spin" />
          )}
        </div>

        {/* Mobile Suggestions Dropdown */}
        {showDropdown && (
          <div className="absolute top-full left-4 right-4 mt-1 bg-slate-900 border border-slate-700 rounded-xl shadow-2xl overflow-hidden z-50 max-h-[60vh] overflow-y-auto divide-y divide-slate-800/80">
            {hasPersons && (
              <div>
                <div className="px-3 py-1.5 bg-slate-950 text-[9px] font-bold uppercase text-slate-400">Filers & Insiders</div>
                {searchResults.persons.map((p) => (
                  <button
                    key={`m-p-${p.id}`}
                    onClick={() => handleSelectPerson(p)}
                    className="w-full px-3 py-2 flex items-center justify-between text-left hover:bg-slate-800"
                  >
                    <span className="text-xs font-bold text-slate-200">{p.name}</span>
                    <span className="text-[10px] text-cyan-400 font-mono">{p.category}</span>
                  </button>
                ))}
              </div>
            )}
            {hasAssets && (
              <div>
                <div className="px-3 py-1.5 bg-slate-950 text-[9px] font-bold uppercase text-slate-400">Stock Assets</div>
                {searchResults.assets.map((a) => (
                  <button
                    key={`m-a-${a.ticker}`}
                    onClick={() => handleSelectAsset(a.ticker)}
                    className="w-full px-3 py-2 flex items-center justify-between text-left hover:bg-slate-800"
                  >
                    <span className="text-xs font-bold text-cyan-400 font-mono">{a.ticker}</span>
                    <span className="text-[10px] text-slate-400">{a.trade_count} trades</span>
                  </button>
                ))}
              </div>
            )}
          </div>
        )}
      </div>

      {/* ─── Content ────────────────────────────────────── */}
      <main className="flex-1 overflow-y-auto overflow-x-hidden pb-24 relative z-10">
        {children}
      </main>

      {/* ─── Global Symbol Overview Modal ───────────────── */}
      {selectedSymbol && (
        <SymbolOverviewModal
          symbolOrIsin={selectedSymbol}
          onClose={() => setSelectedSymbol(null)}
        />
      )}

      {/* ─── Global Person Detail Modal ─────────────────── */}
      {selectedPerson && (
        <PersonDetailModal
          person={selectedPerson}
          onClose={() => setSelectedPerson(null)}
        />
      )}

      {/* ─── Sticky Bottom Navigation ───────────────────── */}
      {bottomNav}
    </div>
  );
}

