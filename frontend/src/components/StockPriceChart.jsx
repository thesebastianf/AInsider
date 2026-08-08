import { useState, useMemo } from 'react';
import { TrendingUp, TrendingDown, Calendar, CircleDollarSign } from 'lucide-react';

export default function StockPriceChart({ ticker, currentPrice, ytdPerf, trades = [] }) {
  const [hoveredPoint, setHoveredPoint] = useState(null);

  // Generate 60-day price trend timeline with trade markers plotted
  const { pathD, areaD, points, markers, minPrice, maxPrice } = useMemo(() => {
    const basePrice = currentPrice || 150.0;
    const perf = ytdPerf || 12.5;
    const startPrice = basePrice / (1 + perf / 100);

    const days = 60;
    const today = new Date();
    const timeline = [];

    // Simple deterministic pseudo-random price path generator
    let seed = 0;
    for (let i = 0; i < ticker.length; i++) {
      seed += ticker.charCodeAt(i);
    }
    const pseudoRandom = (step) => {
      const x = Math.sin(seed + step * 0.1) * 10000;
      return x - Math.floor(x);
    };

    let runningPrice = startPrice;
    const dailyStep = (basePrice - startPrice) / days;

    for (let i = days; i >= 0; i--) {
      const d = new Date(today);
      d.setDate(d.getDate() - i);
      const dateStr = d.toISOString().split('T')[0];

      // Add slight noise trend
      const noise = (pseudoRandom(i) - 0.48) * (basePrice * 0.02);
      runningPrice = Math.max(1.0, runningPrice + dailyStep + noise);

      if (i === 0) runningPrice = basePrice;

      timeline.push({
        date: dateStr,
        price: Number(runningPrice.toFixed(2)),
        trades: []
      });
    }

    // Map actual trades onto closest timeline dates
    const timelineMap = {};
    timeline.forEach(pt => { timelineMap[pt.date] = pt; });

    const tradeMarkers = [];
    (trades || []).forEach(t => {
      const tDate = t.trade_date;
      if (timelineMap[tDate]) {
        timelineMap[tDate].trades.push(t);
        tradeMarkers.push({
          ...t,
          priceAtDate: t.price_at_transaction || timelineMap[tDate].price,
          targetDate: tDate
        });
      }
    });

    const prices = timeline.map(t => t.price);
    const minP = Math.min(...prices) * 0.98;
    const maxP = Math.max(...prices) * 1.02;

    const width = 800;
    const height = 220;
    const padding = 20;

    const getX = (idx) => padding + (idx / (days)) * (width - 2 * padding);
    const getY = (price) => height - padding - ((price - minP) / (maxP - minP || 1)) * (height - 2 * padding);

    const pts = timeline.map((pt, idx) => ({
      x: getX(idx),
      y: getY(pt.price),
      date: pt.date,
      price: pt.price,
      trades: pt.trades
    }));

    // Build SVG Path
    let pD = `M ${pts[0].x} ${pts[0].y}`;
    for (let i = 1; i < pts.length; i++) {
      const xc = (pts[i].x + pts[i - 1].x) / 2;
      const yc = (pts[i].y + pts[i - 1].y) / 2;
      pD += ` Q ${pts[i - 1].x} ${pts[i - 1].y}, ${xc} ${yc}`;
    }
    pD += ` L ${pts[pts.length - 1].x} ${pts[pts.length - 1].y}`;

    const aD = `${pD} L ${pts[pts.length - 1].x} ${height - padding} L ${pts[0].x} ${height - padding} Z`;

    const mks = pts
      .filter(pt => pt.trades.length > 0)
      .map(pt => ({
        x: pt.x,
        y: pt.y,
        date: pt.date,
        price: pt.price,
        trades: pt.trades
      }));

    return {
      pathD: pD,
      areaD: aD,
      points: pts,
      markers: mks,
      minPrice: minP,
      maxPrice: maxP
    };
  }, [ticker, currentPrice, ytdPerf, trades]);

  const isPositive = (ytdPerf || 0) >= 0;
  const strokeColor = isPositive ? '#22c55e' : '#ef4444';
  const fillColor = isPositive ? 'url(#greenGradient)' : 'url(#redGradient)';

  return (
    <div className="p-4 bg-slate-950/60 border border-slate-800 rounded-xl space-y-3 relative overflow-hidden">
      <div className="flex justify-between items-center text-xs">
        <div className="flex items-center gap-2">
          <span className="font-extrabold font-mono text-slate-200 uppercase tracking-wider">{ticker} Price & Insider Activity</span>
          <span className="text-[10px] text-slate-500 font-mono">60-Day Trend</span>
        </div>

        <div className="flex items-center gap-4 text-[11px] font-mono">
          <div className="flex items-center gap-1">
            <div className="w-2.5 h-2.5 rounded-full bg-emerald-500 shadow-[0_0_6px_rgba(34,197,94,0.8)]" />
            <span className="text-emerald-400 font-bold">BUY</span>
          </div>
          <div className="flex items-center gap-1">
            <div className="w-2.5 h-2.5 rounded-full bg-blue-500 shadow-[0_0_6px_rgba(59,130,246,0.8)]" />
            <span className="text-blue-400 font-bold">SELL</span>
          </div>
        </div>
      </div>

      {/* SVG Chart Container */}
      <div className="relative w-full h-48 select-none">
        <svg viewBox="0 0 800 220" className="w-full h-full overflow-visible">
          <defs>
            <linearGradient id="greenGradient" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#22c55e" stopOpacity="0.3" />
              <stop offset="100%" stopColor="#22c55e" stopOpacity="0.0" />
            </linearGradient>
            <linearGradient id="redGradient" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#3b82f6" stopOpacity="0.3" />
              <stop offset="100%" stopColor="#3b82f6" stopOpacity="0.0" />
            </linearGradient>
          </defs>

          {/* Grid lines */}
          <line x1="20" y1="20" x2="780" y2="20" stroke="#334155" strokeDasharray="3 3" opacity="0.4" />
          <line x1="20" y1="110" x2="780" y2="110" stroke="#334155" strokeDasharray="3 3" opacity="0.4" />
          <line x1="20" y1="200" x2="780" y2="200" stroke="#334155" strokeDasharray="3 3" opacity="0.4" />

          {/* Area Fill & Path Line */}
          <path d={areaD} fill={fillColor} />
          <path d={pathD} fill="none" stroke={strokeColor} strokeWidth="2.5" strokeLinecap="round" />

          {/* Interactive Hover Vertical Bar */}
          {hoveredPoint && (
            <line
              x1={hoveredPoint.x}
              y1="20"
              x2={hoveredPoint.x}
              y2="200"
              stroke="#06b6d4"
              strokeWidth="1.5"
              strokeDasharray="4 4"
            />
          )}

          {/* Trade Marker Pins */}
          {markers.map((m, idx) => {
            const hasBuy = m.trades.some(t => t.type === 'BUY');
            const pinColor = hasBuy ? '#22c55e' : '#3b82f6';

            return (
              <g key={`marker-${idx}`} className="cursor-pointer">
                {/* Marker Drop Line */}
                <line x1={m.x} y1={m.y} x2={m.x} y2="200" stroke={pinColor} strokeWidth="1" opacity="0.4" strokeDasharray="2 2" />

                {/* Pulse Ring */}
                <circle cx={m.x} cy={m.y} r="8" fill={pinColor} opacity="0.25" className="animate-ping" />

                {/* Marker Node */}
                <circle
                  cx={m.x}
                  cy={m.y}
                  r="5"
                  fill={pinColor}
                  stroke="#020617"
                  strokeWidth="2"
                  className="transition-transform hover:scale-150"
                />
              </g>
            );
          })}

          {/* Hover Capture Points */}
          {points.map((pt, idx) => (
            <rect
              key={`pt-${idx}`}
              x={pt.x - 6}
              y="0"
              width="12"
              height="220"
              fill="transparent"
              onMouseEnter={() => setHoveredPoint(pt)}
              onMouseLeave={() => setHoveredPoint(null)}
              className="cursor-crosshair"
            />
          ))}
        </svg>

        {/* Hover Tooltip Overlay */}
        {hoveredPoint && (
          <div 
            className="absolute z-20 pointer-events-none bg-slate-900 border border-slate-700 rounded-xl p-3 shadow-2xl text-xs space-y-1 transform -translate-x-1/2 -translate-y-full -mt-2 animate-fade-in"
            style={{ left: `${(hoveredPoint.x / 800) * 100}%`, top: `${(hoveredPoint.y / 220) * 100}%` }}
          >
            <div className="flex items-center gap-2 font-mono text-[10px] text-slate-400">
              <Calendar size={10} />
              {new Date(hoveredPoint.date).toLocaleDateString()}
            </div>
            <div className="font-extrabold font-mono text-sm text-cyan-400">
              ${hoveredPoint.price.toFixed(2)}
            </div>

            {hoveredPoint.trades.length > 0 && (
              <div className="pt-1.5 border-t border-slate-800 space-y-1">
                {hoveredPoint.trades.map(t => (
                  <div key={t.id} className="flex items-center justify-between gap-3 text-[10px]">
                    <span className="font-bold text-slate-200">{t.person_name}</span>
                    <span className={`px-1.5 py-0.2 rounded font-mono font-bold ${
                      t.type === 'BUY' ? 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/30' : 'bg-blue-500/20 text-blue-400 border border-blue-500/30'
                    }`}>
                      {t.type} {t.amount_range}
                    </span>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
