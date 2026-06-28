import { useEffect, useRef } from 'react';

export default function LogConsole({ logs = [] }) {
  const endRef = useRef(null);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [logs.length]);

  const levelColors = {
    INFO: 'text-green-400',
    WARN: 'text-yellow-400',
    ERROR: 'text-red-400',
    DEBUG: 'text-blue-400',
  };

  return (
    <div className="bg-[#0a0a0a] rounded-xl border border-slate-700 font-mono text-xs overflow-hidden shadow-inner relative flex flex-col h-64">
      {/* Cyan/Blue Top Gradient Bar */}
      <div className="absolute top-0 left-0 w-full h-1 bg-gradient-to-r from-blue-500 to-cyan-500 z-10" />
      
      {/* Console Header */}
      <div className="flex justify-between items-center px-4 py-2 mt-1 border-b border-slate-800 bg-[#0a0a0a]">
        <span className="text-slate-500">root@ainsider-core:~# tail -f /var/log/sys.log</span>
        <span className="text-cyan-500 flex items-center gap-1.5 font-sans text-[10px] font-bold tracking-wider">
          <span className="w-1.5 h-1.5 rounded-full bg-cyan-500 animate-pulse" />
          LIVE STREAM
        </span>
      </div>

      {/* Log Entries */}
      <div className="flex-1 overflow-y-auto p-4 space-y-1.5 opacity-90 leading-relaxed">
        {logs.length === 0 ? (
          <div className="text-slate-600 flex items-center gap-2">
            <span className="animate-pulse">█</span>
            Waiting for logs...
          </div>
        ) : (
          logs.map((log, i) => (
            <div key={i} className="flex gap-2 hover:bg-white/[0.02] px-1 -mx-1 rounded">
              <span className="text-slate-600 shrink-0">
                [{log.timestamp.split(' ')[1] || log.timestamp}]
              </span>
              <span className={`shrink-0 font-bold ${levelColors[log.level] || 'text-slate-400'}`}>
                {log.level.padEnd(5)}:
              </span>
              <span className="text-slate-300">{log.message}</span>
            </div>
          ))
        )}
        <div className="animate-pulse mt-4 text-cyan-500 block">█</div>
        <div ref={endRef} />
      </div>
    </div>
  );
}
