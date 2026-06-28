import { Bell, Sun, Moon } from 'lucide-react';
import AppLogo from './AppLogo';
import { useState, useEffect } from 'react';

export default function Layout({ children, activeTab, bottomNav }) {
  const [theme, setTheme] = useState(() => localStorage.getItem('ainsider-theme') || 'dark');

  useEffect(() => {
    const isDark = theme === 'dark';
    document.documentElement.classList.toggle('dark', isDark);
    document.documentElement.classList.toggle('light-theme', !isDark);
    localStorage.setItem('ainsider-theme', theme);
  }, [theme]);

  const toggleTheme = () => {
    setTheme(t => (t === 'dark' ? 'light' : 'dark'));
  };

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
        <div className="flex items-center gap-2">
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

      {/* ─── Content ────────────────────────────────────── */}
      <main className="flex-1 overflow-y-auto overflow-x-hidden pb-24 relative z-10">
        {children}
      </main>

      {/* ─── Sticky Bottom Navigation ───────────────────── */}
      {bottomNav}
    </div>
  );
}
