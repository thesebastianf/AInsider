import { Search } from 'lucide-react';
import { useState, useEffect } from 'react';

export default function SearchBar({ onSearch }) {
  const [value, setValue] = useState('');

  useEffect(() => {
    const timer = setTimeout(() => {
      onSearch(value);
    }, 300);
    return () => clearTimeout(timer);
  }, [value]);

  return (
    <div className="px-5 pt-4 pb-1">
      <div className="relative">
        <Search
          className="absolute left-3.5 top-1/2 -translate-y-1/2 text-slate-500 pointer-events-none"
          size={16}
        />
        <input
          id="search-persons"
          type="text"
          placeholder="Search persons or tickers..."
          value={value}
          onChange={(e) => setValue(e.target.value)}
          className="w-full pl-10 pr-4 py-2.5 rounded-xl text-sm font-medium text-slate-200 placeholder-slate-500 outline-none transition-all duration-200 focus:ring-2 focus:ring-blue-500/30"
          style={{
            background: 'rgba(15, 23, 42, 0.6)',
            backdropFilter: 'blur(8px)',
            border: '1px solid rgba(148, 163, 184, 0.12)',
          }}
        />
      </div>
    </div>
  );
}
