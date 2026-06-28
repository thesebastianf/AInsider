const categories = ['All', 'Congress', 'Senate', 'Fund Manager'];

export default function CategoryPills({ active, onChange }) {
  return (
    <div className="flex gap-2 overflow-x-auto no-scrollbar px-5 py-3">
      {categories.map((cat) => {
        const isActive = active === cat;
        return (
          <button
            key={cat}
            onClick={() => onChange(cat)}
            className={`shrink-0 px-4 py-1.5 rounded-full text-xs font-semibold transition-all duration-300 whitespace-nowrap border ${
              isActive 
                ? 'bg-gradient-to-r from-blue-600 to-cyan-600 text-white shadow-[0_0_15px_rgba(6,182,212,0.3)] border-transparent' 
                : 'bg-slate-800 text-slate-300 border-slate-700 hover:border-slate-500'
            }`}
          >
            {cat}
          </button>
        );
      })}
    </div>
  );
}
