export default function AppLogo({ className = "" }) {
  return (
    <div className={`relative flex items-center justify-center ${className}`}>
      <svg width="36" height="36" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
        <defs>
          <linearGradient id="ai-gradient" x1="0%" y1="100%" x2="100%" y2="0%">
            <stop offset="0%" stopColor="#3b82f6" /> {/* Blue 500 */}
            <stop offset="100%" stopColor="#06b6d4" /> {/* Cyan 500 */}
          </linearGradient>
          
          {/* Glow Filter für den Neon-Effekt */}
          <filter id="neon-glow" x="-20%" y="-20%" width="140%" height="140%">
            <feGaussianBlur stdDeviation="1.2" result="blur" />
            <feComposite in="SourceGraphic" in2="blur" operator="over" />
          </filter>
        </defs>

        {/* Äußerer Radar-Ring (Tracker) */}
        <circle 
          cx="12" cy="12" r="11" 
          stroke="url(#ai-gradient)" 
          strokeWidth="1" 
          strokeDasharray="4 4" 
          opacity="0.4"
          className="animate-[spin_20s_linear_infinite]"
          style={{ transformOrigin: 'center' }}
        />

        {/* Innerer, solider Ring */}
        <circle cx="12" cy="12" r="9" stroke="rgba(59,130,246,0.2)" strokeWidth="0.5" />

        {/* Das messerscharfe 'A' / Der Aufwärts-Trend */}
        <path 
          d="M12 3 L20 18 H15.5 L12 11 L8.5 18 H4 L12 3Z" 
          fill="url(#ai-gradient)" 
          filter="url(#neon-glow)"
        />

        {/* Schwebender KI-Datenknoten im Zentrum */}
        <circle 
          cx="12" cy="15" r="2.5" 
          fill="#ffffff" 
          filter="url(#neon-glow)"
        />
      </svg>
    </div>
  );
}
