import { Briefcase, Compass, Activity, Settings, TerminalSquare } from 'lucide-react';

const tabs = [
  { id: 'portfolios', label: 'Portfolios', icon: Briefcase },
  { id: 'discover', label: 'Discover', icon: Compass },
  { id: 'feed', label: 'Live Feed', icon: Activity },
  { id: 'settings', label: 'Settings', icon: Settings },
  { id: 'developer', label: 'Developer', icon: TerminalSquare },
];

export default function BottomNav({ activeTab, onTabChange }) {
  return (
    <nav className="absolute bottom-0 w-full z-20 flex justify-between items-center px-6 py-3 pb-[calc(env(safe-area-inset-bottom)+12px)] border-t border-slate-800"
      style={{
        background: 'rgba(2, 6, 23, 0.95)',
        backdropFilter: 'blur(16px)',
        WebkitBackdropFilter: 'blur(16px)',
      }}
    >
      {tabs.map((tab) => {
        const isActive = activeTab === tab.id;
        const Icon = tab.icon;
        return (
          <button
            key={tab.id}
            id={`nav-${tab.id}`}
            onClick={() => onTabChange(tab.id)}
            className={`flex flex-col items-center gap-1 transition-all duration-300 ${isActive ? 'text-cyan-400 scale-110' : 'text-slate-500 hover:text-slate-300'}`}
          >
            <Icon 
              className={`h-6 w-6 transition-all duration-300 ${isActive ? 'fill-cyan-500/20 drop-shadow-[0_0_8px_rgba(6,182,212,0.5)]' : ''}`} 
              strokeWidth={isActive ? 2 : 1.5}
            />
            <span className="text-[10px] font-medium tracking-wide">{tab.label}</span>
          </button>
        );
      })}
    </nav>
  );
}
