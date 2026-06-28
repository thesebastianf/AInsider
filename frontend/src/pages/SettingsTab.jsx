import { useState, useEffect, useCallback } from 'react';
import { useApi } from '../hooks/useApi';
import {
  getSettings, updateSettings,
  getLLMProviders, createLLMProvider, deleteLLMProvider,
  activateLLMProvider, testLLMProvider,
  getNotificationProviders, getNotificationFields,
  createNotificationProvider, deleteNotificationProvider,
  updateNotificationProvider, testNotificationProvider,
  triggerPipeline,
} from '../api/client';
import {
  Brain, Bell, Database, Plus, Trash2, Power, FlaskConical,
  Check, X, Loader2, ChevronDown, ChevronUp, RefreshCw,
} from 'lucide-react';

// ═══ Provider Icons ══════════════════════════════════════════
const PROVIDER_ICONS = {
  ollama: '🦙', openai: '🤖', anthropic: '🧠', custom: '⚙️',
  telegram: '📨', gotify: '🔔', pushover: '📲', discord: '💬', slack: '💼', ntfy: '📡',
};

// ═══ LLM Section ═════════════════════════════════════════════
function LLMSection() {
  const { data: providers, refetch } = useApi(getLLMProviders, []);
  const [showAdd, setShowAdd] = useState(false);
  const [testing, setTesting] = useState(null);
  const [testResult, setTestResult] = useState(null);
  const [form, setForm] = useState({
    provider_type: 'ollama', name: '', api_url: '', api_key: '', model_name: '',
  });

  const presets = {
    ollama: { api_url: 'http://localhost:11434', model_name: 'llama3' },
    openai: { api_url: 'https://api.openai.com', model_name: 'gpt-4o-mini' },
    anthropic: { api_url: 'https://api.anthropic.com', model_name: 'claude-sonnet-4-20250514' },
    custom: { api_url: '', model_name: '' },
  };

  const handleTypeChange = (type) => {
    const preset = presets[type];
    setForm(f => ({ ...f, provider_type: type, ...preset, name: f.name }));
  };

  const handleAdd = async () => {
    if (!form.name || !form.api_url || !form.model_name) return;
    await createLLMProvider(form);
    setShowAdd(false);
    setForm({ provider_type: 'ollama', name: '', api_url: '', api_key: '', model_name: '' });
    refetch();
  };

  const handleTest = async (id) => {
    setTesting(id);
    setTestResult(null);
    try {
      const res = await testLLMProvider(id);
      setTestResult({ id, ...res });
    } catch (e) {
      setTestResult({ id, success: false, message: e.message });
    }
    setTesting(null);
  };

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Brain size={16} className="text-purple-400" />
          <span className="text-sm font-semibold text-slate-200">AI / LLM Provider</span>
        </div>
        <button onClick={() => setShowAdd(!showAdd)}
          className="p-1.5 rounded-lg bg-blue-500/15 text-blue-400 hover:bg-blue-500/25 transition-colors">
          <Plus size={14} />
        </button>
      </div>

      {/* Add Form */}
      {showAdd && (
        <div className="glass-card p-4 space-y-3 animate-slide-up">
          <div className="flex gap-2">
            {['ollama', 'openai', 'anthropic', 'custom'].map(t => (
              <button key={t} onClick={() => handleTypeChange(t)}
                className={`px-2.5 py-1 rounded-lg text-[11px] font-semibold transition-colors ${
                  form.provider_type === t ? 'bg-blue-500 text-white' : 'bg-slate-800 text-slate-400'
                }`}>
                {PROVIDER_ICONS[t]} {t}
              </button>
            ))}
          </div>
          <input placeholder="Display name" value={form.name}
            onChange={e => setForm(f => ({ ...f, name: e.target.value }))}
            className="w-full px-3 py-2 rounded-lg bg-slate-900/80 border border-slate-700/50 text-sm text-slate-200 outline-none focus:border-blue-500/50" />
          <input placeholder="API URL" value={form.api_url}
            onChange={e => setForm(f => ({ ...f, api_url: e.target.value }))}
            className="w-full px-3 py-2 rounded-lg bg-slate-900/80 border border-slate-700/50 text-sm text-slate-200 outline-none focus:border-blue-500/50" />
          {form.provider_type !== 'ollama' && (
            <input placeholder="API Key" type="password" value={form.api_key}
              onChange={e => setForm(f => ({ ...f, api_key: e.target.value }))}
              className="w-full px-3 py-2 rounded-lg bg-slate-900/80 border border-slate-700/50 text-sm text-slate-200 outline-none focus:border-blue-500/50" />
          )}
          <input placeholder="Model name" value={form.model_name}
            onChange={e => setForm(f => ({ ...f, model_name: e.target.value }))}
            className="w-full px-3 py-2 rounded-lg bg-slate-900/80 border border-slate-700/50 text-sm text-slate-200 outline-none focus:border-blue-500/50" />
          <button onClick={handleAdd}
            className="w-full py-2 rounded-lg bg-blue-500 text-white text-sm font-semibold hover:bg-blue-600 transition-colors">
            Add Provider
          </button>
        </div>
      )}

      {/* Provider List */}
      {(providers || []).map(p => (
        <div key={p.id} className="glass-card p-3 flex items-center gap-3">
          <span className="text-lg">{PROVIDER_ICONS[p.provider_type]}</span>
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2">
              <span className="text-sm font-medium text-slate-200 truncate">{p.name}</span>
              {p.is_active && (
                <span className="px-1.5 py-0.5 rounded text-[9px] font-bold bg-emerald-500/15 text-emerald-400 border border-emerald-500/25">
                  ACTIVE
                </span>
              )}
            </div>
            <p className="text-[11px] text-slate-500 truncate">{p.model_name} · {p.api_url}</p>
          </div>
          <div className="flex items-center gap-1">
            <button onClick={() => handleTest(p.id)} title="Test"
              className="p-1.5 rounded-lg hover:bg-slate-700/50 transition-colors text-slate-400">
              {testing === p.id ? <Loader2 size={14} className="animate-spin" /> : <FlaskConical size={14} />}
            </button>
            {!p.is_active && (
              <button onClick={async () => { await activateLLMProvider(p.id); refetch(); }} title="Activate"
                className="p-1.5 rounded-lg hover:bg-emerald-500/15 transition-colors text-slate-400 hover:text-emerald-400">
                <Power size={14} />
              </button>
            )}
            <button onClick={async () => { await deleteLLMProvider(p.id); refetch(); }} title="Delete"
              className="p-1.5 rounded-lg hover:bg-red-500/15 transition-colors text-slate-400 hover:text-red-400">
              <Trash2 size={14} />
            </button>
          </div>
          {testResult?.id === p.id && (
            <div className={`absolute -bottom-8 left-0 right-0 text-[10px] p-1.5 rounded ${
              testResult.success ? 'text-emerald-400' : 'text-red-400'
            }`}>
              {testResult.success ? '✅' : '❌'} {testResult.message}
            </div>
          )}
        </div>
      ))}
      {testResult && (
        <div className={`px-3 py-2 rounded-lg text-xs ${
          testResult.success ? 'bg-emerald-500/10 text-emerald-400' : 'bg-red-500/10 text-red-400'
        }`}>
          {testResult.success ? '✅' : '❌'} {testResult.message}
        </div>
      )}
    </div>
  );
}

// ═══ Notification Section ════════════════════════════════════
function NotifySection() {
  const { data: providers, refetch } = useApi(getNotificationProviders, []);
  const { data: fields } = useApi(getNotificationFields, []);
  const [showAdd, setShowAdd] = useState(false);
  const [testing, setTesting] = useState(null);
  const [testResult, setTestResult] = useState(null);
  const [provType, setProvType] = useState('telegram');
  const [name, setName] = useState('');
  const [configFields, setConfigFields] = useState({});

  useEffect(() => {
    setConfigFields({});
  }, [provType]);

  const handleAdd = async () => {
    if (!name) return;
    await createNotificationProvider({
      provider_type: provType, name, config_json: configFields,
    });
    setShowAdd(false);
    setName('');
    setConfigFields({});
    refetch();
  };

  const handleTest = async (id) => {
    setTesting(id);
    try {
      const res = await testNotificationProvider(id);
      setTestResult({ id, ...res });
    } catch (e) {
      setTestResult({ id, success: false, message: e.message });
    }
    setTesting(null);
  };

  const handleToggle = async (p) => {
    await updateNotificationProvider(p.id, { is_enabled: !p.is_enabled });
    refetch();
  };

  const currentFields = fields?.[provType] || {};

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Bell size={16} className="text-amber-400" />
          <span className="text-sm font-semibold text-slate-200">Notifications</span>
        </div>
        <button onClick={() => setShowAdd(!showAdd)}
          className="p-1.5 rounded-lg bg-blue-500/15 text-blue-400 hover:bg-blue-500/25 transition-colors">
          <Plus size={14} />
        </button>
      </div>

      {showAdd && (
        <div className="glass-card p-4 space-y-3 animate-slide-up">
          <div className="flex flex-wrap gap-1.5">
            {['telegram', 'gotify', 'pushover', 'discord', 'slack', 'ntfy'].map(t => (
              <button key={t} onClick={() => setProvType(t)}
                className={`px-2.5 py-1 rounded-lg text-[11px] font-semibold transition-colors ${
                  provType === t ? 'bg-blue-500 text-white' : 'bg-slate-800 text-slate-400'
                }`}>
                {PROVIDER_ICONS[t]} {t}
              </button>
            ))}
          </div>
          <input placeholder="Display name" value={name} onChange={e => setName(e.target.value)}
            className="w-full px-3 py-2 rounded-lg bg-slate-900/80 border border-slate-700/50 text-sm text-slate-200 outline-none focus:border-blue-500/50" />
          {Object.entries(currentFields).map(([key, label]) => (
            <input key={key} placeholder={label} value={configFields[key] || ''}
              onChange={e => setConfigFields(f => ({ ...f, [key]: e.target.value }))}
              type={key.includes('token') || key.includes('key') ? 'password' : 'text'}
              className="w-full px-3 py-2 rounded-lg bg-slate-900/80 border border-slate-700/50 text-sm text-slate-200 outline-none focus:border-blue-500/50" />
          ))}
          <button onClick={handleAdd}
            className="w-full py-2 rounded-lg bg-blue-500 text-white text-sm font-semibold hover:bg-blue-600 transition-colors">
            Add Provider
          </button>
        </div>
      )}

      {(providers || []).map(p => (
        <div key={p.id} className="glass-card p-3 flex items-center gap-3">
          <span className="text-lg">{PROVIDER_ICONS[p.provider_type]}</span>
          <div className="flex-1 min-w-0">
            <span className="text-sm font-medium text-slate-200 truncate block">{p.name}</span>
            <p className="text-[11px] text-slate-500">
              {p.provider_type}{p.last_test ? ` · Tested ${new Date(p.last_test).toLocaleDateString()}` : ''}
            </p>
          </div>
          <div className="flex items-center gap-1">
            <button onClick={() => handleTest(p.id)} title="Test"
              className="p-1.5 rounded-lg hover:bg-slate-700/50 transition-colors text-slate-400">
              {testing === p.id ? <Loader2 size={14} className="animate-spin" /> : <FlaskConical size={14} />}
            </button>
            <button onClick={() => handleToggle(p)} title={p.is_enabled ? 'Disable' : 'Enable'}
              className={`p-1.5 rounded-lg transition-colors ${
                p.is_enabled ? 'text-emerald-400 hover:bg-emerald-500/15' : 'text-slate-600 hover:bg-slate-700/50'
              }`}>
              <Power size={14} />
            </button>
            <button onClick={async () => { await deleteNotificationProvider(p.id); refetch(); }} title="Delete"
              className="p-1.5 rounded-lg hover:bg-red-500/15 transition-colors text-slate-400 hover:text-red-400">
              <Trash2 size={14} />
            </button>
          </div>
        </div>
      ))}
      {testResult && (
        <div className={`px-3 py-2 rounded-lg text-xs ${
          testResult.success ? 'bg-emerald-500/10 text-emerald-400' : 'bg-red-500/10 text-red-400'
        }`}>
          {testResult.success ? '✅' : '❌'} {testResult.message}
        </div>
      )}
    </div>
  );
}

// ═══ Data Source Section ═════════════════════════════════════
function DataSourceSection() {
  const { data: settings, refetch: refetchSettings } = useApi(getSettings, []);
  const providers = settings?.data_source_providers || [];
  
  const [fieldsData, setFieldsData] = useState(null);
  const [showAdd, setShowAdd] = useState(false);
  const [provType, setProvType] = useState('house');
  const [name, setName] = useState('');
  const [configFields, setConfigFields] = useState({});
  const [syncing, setSyncing] = useState(false);
  const [copiedId, setCopiedId] = useState(null);

  // Fetch fields lazily
  useEffect(() => {
    if (showAdd && !fieldsData) {
      fetch('/api/settings/datasources/fields')
        .then(res => res.json())
        .then(setFieldsData)
        .catch(console.error);
    }
  }, [showAdd, fieldsData]);

  useEffect(() => {
    setConfigFields({});
  }, [provType]);

  const handleAdd = async () => {
    if (!name) return;
    await fetch('/api/settings/datasources', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ provider_type: provType, name, config_json: configFields })
    });
    setShowAdd(false);
    setName('');
    setConfigFields({});
    refetchSettings();
  };

  const handleToggle = async (p) => {
    await fetch(`/api/settings/datasources/${p.id}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ is_enabled: !p.is_enabled })
    });
    refetchSettings();
  };

  const handleDelete = async (id) => {
    await fetch(`/api/settings/datasources/${id}`, { method: 'DELETE' });
    refetchSettings();
  };

  const handleSync = async () => {
    setSyncing(true);
    try {
      await triggerPipeline();
      setTimeout(refetchSettings, 1000);
    } catch (e) {
      console.error(e);
    }
    setSyncing(false);
  };

  const currentFields = fieldsData?.[provType] || {};
  const DS_ICONS = { house: '🏛️', senate: '🏛️', quiver: '📈', sec13f: '🏦', sec_form4: '🏢', directors_dealings: '🇪🇺' };
  const DS_URLS = {
    house: 'https://congress.kadoa.com/data/trades.json',
    senate: 'https://raw.githubusercontent.com/timothycarambat/senate-stock-watcher-data/master/aggregate/all_transactions.json',
    quiver: 'https://api.quiverquant.com (Requires API Key)',
    sec13f: 'SEC EDGAR (13F RSS Feed / API)',
    sec_form4: 'https://www.sec.gov/cgi-bin/browse-edgar (Form 4 Atom Feed)',
    directors_dealings: 'https://www.wallstreet-online.de/rss/nachrichten-directors-dealings.xml',
  };

  const DS_DESCS = {
    house: 'Official Financial Disclosure Reports filed by US Representatives, parsed in real-time by the House Stock Watcher project.',
    senate: 'Public Financial Disclosure reports filed by US Senators, aggregated by the Senate Stock Watcher project.',
    quiver: 'Alternative data service tracking politician trades, lobbying activities, and government contracts. Requires an API Key.',
    sec13f: 'Official quarterly holdings reports (Form 13F) filed by major institutional fund managers to the US SEC EDGAR system.',
    sec_form4: 'Real-time statement of changes in beneficial ownership of securities (Form 4) filed by corporate directors, officers, and CEOs to the US SEC EDGAR system.',
    directors_dealings: 'Real-time management transaction reports (Directors\' Dealings) filed by DAX / European corporate board members and executives.',
  };

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Database size={16} className="text-blue-400" />
          <span className="text-sm font-semibold text-slate-200">Data Sources</span>
        </div>
        <button onClick={() => setShowAdd(!showAdd)}
          className="p-1.5 rounded-lg bg-blue-500/15 text-blue-400 hover:bg-blue-500/25 transition-colors">
          <Plus size={14} />
        </button>
      </div>

      {showAdd && (
        <div className="glass-card p-4 space-y-3 animate-slide-up">
          <div className="flex flex-wrap gap-1.5">
            {['house', 'senate', 'quiver', 'sec13f', 'sec_form4', 'directors_dealings'].map(t => (
              <button key={t} onClick={() => setProvType(t)}
                className={`px-2.5 py-1 rounded-lg text-[11px] font-semibold transition-colors ${
                  provType === t ? 'bg-blue-500 text-white' : 'bg-slate-800 text-slate-400'
                }`}>
                {DS_ICONS[t]} {t}
              </button>
            ))}
          </div>

          {/* Selected Provider Info */}
          <div className="p-2.5 bg-slate-900/50 dark:bg-slate-950/50 rounded-lg border border-slate-800/30 dark:border-slate-800/60 text-[10px] text-slate-400 leading-relaxed space-y-1">
            <span className="font-semibold text-slate-300 dark:text-slate-200 block uppercase tracking-wider text-[9px]">
              Source Information
            </span>
            <p>{DS_DESCS[provType]}</p>
            <p className="font-mono text-[9px] text-slate-500 dark:text-slate-500 truncate">{DS_URLS[provType]}</p>
          </div>

          <input placeholder="Display name" value={name} onChange={e => setName(e.target.value)}
            className="w-full px-3 py-2 rounded-lg bg-slate-900/80 border border-slate-700/50 text-sm text-slate-200 outline-none focus:border-blue-500/50" />
          {Object.entries(currentFields).map(([key, label]) => (
            <input key={key} placeholder={label} value={configFields[key] || ''}
              onChange={e => setConfigFields(f => ({ ...f, [key]: e.target.value }))}
              type={key.includes('token') || key.includes('key') ? 'password' : 'text'}
              className="w-full px-3 py-2 rounded-lg bg-slate-900/80 border border-slate-700/50 text-sm text-slate-200 outline-none focus:border-blue-500/50" />
          ))}
          <button onClick={handleAdd}
            className="w-full py-2 rounded-lg bg-blue-500 text-white text-sm font-semibold hover:bg-blue-600 transition-colors">
            Add Source
          </button>
        </div>
      )}

      {providers.length === 0 ? (
         <div className="text-xs text-slate-500 italic p-2 text-center bg-slate-900/50 rounded-lg">
           No active data sources. The pipeline will not fetch trades.
         </div>
      ) : (
        providers.map(p => (
          <div key={p.id} className="glass-card p-3 flex items-center gap-3">
            <span className="text-lg">{DS_ICONS[p.provider_type] || '📡'}</span>
            <div className="flex-1 min-w-0">
              <span className="text-sm font-medium text-slate-200 truncate block">{p.name}</span>
              <p className="text-[10px] text-slate-500 truncate mt-0.5" title={DS_URLS[p.provider_type]}>
                {DS_URLS[p.provider_type] || p.provider_type}
              </p>
              <p className="text-[9px] text-slate-400 mt-1 flex flex-wrap items-center gap-1.5">
                <span>{p.last_fetch ? `Synced: ${new Date(p.last_fetch).toLocaleString()}` : 'Not synced yet'}</span>
                {p.config_json?.last_status === 'success' && (
                  <span className="px-1 py-0.5 rounded text-[8px] bg-emerald-500/10 text-emerald-400 border border-emerald-500/10 font-bold font-mono">
                    +{p.config_json.last_count} rows
                  </span>
                )}
                {p.config_json?.last_status === 'error' && (
                  <span 
                    onClick={(e) => {
                      e.stopPropagation();
                      navigator.clipboard.writeText(p.config_json.last_error || '');
                      setCopiedId(p.id);
                      setTimeout(() => setCopiedId(null), 2000);
                    }}
                    title="Click to copy full error message"
                    className="px-1 py-0.5 rounded text-[8px] bg-red-500/10 text-red-400 border border-red-500/10 font-bold font-mono truncate max-w-[150px] cursor-pointer hover:bg-red-500/20 active:bg-red-500/30 transition-all select-none"
                  >
                    {copiedId === p.id ? 'Copied!' : `Error: ${p.config_json.last_error}`}
                  </span>
                )}
              </p>
            </div>
            <div className="flex items-center gap-1 shrink-0">
              <button onClick={() => handleToggle(p)} title={p.is_enabled ? 'Disable' : 'Enable'}
                className={`p-1.5 rounded-lg transition-colors ${
                  p.is_enabled ? 'text-emerald-400 hover:bg-emerald-500/15' : 'text-slate-600 hover:bg-slate-700/50'
                }`}>
                <Power size={14} />
              </button>
              <button onClick={() => handleDelete(p.id)} title="Delete"
                className="p-1.5 rounded-lg hover:bg-red-500/15 transition-colors text-slate-400 hover:text-red-400">
                <Trash2 size={14} />
              </button>
            </div>
          </div>
        ))
      )}

      <div className="glass-card p-3 space-y-3 mt-4 bg-blue-900/10 border-blue-900/30">
        {settings?.last_pipeline_run && (
          <div className="flex items-center justify-between">
            <span className="text-xs text-slate-400">Last Sync</span>
            <span className="text-xs text-blue-300">
              {new Date(settings.last_pipeline_run).toLocaleString()}
            </span>
          </div>
        )}
        <button onClick={handleSync} disabled={syncing}
          className="w-full py-2 rounded-lg bg-blue-500/20 text-blue-400 text-sm font-semibold hover:bg-blue-500/30 transition-colors flex items-center justify-center gap-2 disabled:opacity-50">
          <RefreshCw size={14} className={syncing ? 'animate-spin' : ''} />
          {syncing ? 'Syncing Pipeline...' : 'Run Pipeline Now'}
        </button>
      </div>
    </div>
  );
}

// ═══ Main Settings Tab ═══════════════════════════════════════
export default function SettingsTab() {
  return (
    <div className="px-5 py-5 grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6 animate-fade-in items-start">
      <LLMSection />
      <NotifySection />
      <DataSourceSection />
    </div>
  );
}
