import { useState, useEffect, useCallback } from 'react';
import { useApi } from '../hooks/useApi';
import { getSystemStats, getSystemLogs } from '../api/client';
import { BarChart3, Clock, Users, Activity, Cpu, Database } from 'lucide-react';
import StatWidget from '../components/StatWidget';
import LogConsole from '../components/LogConsole';

function formatUptime(seconds) {
  if (!seconds) return '0s';
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  if (h > 0) return `${h}h ${m}m`;
  return `${m}m`;
}

export default function DeveloperTab() {
  const fetchStats = useCallback(() => getSystemStats(), []);
  const fetchLogs = useCallback(() => getSystemLogs(200), []);

  const { data: stats } = useApi(fetchStats, []);
  const { data: logsData, refetch: refetchLogs } = useApi(fetchLogs, []);

  // Auto-refresh logs every 5 seconds
  useEffect(() => {
    const interval = setInterval(refetchLogs, 5000);
    return () => clearInterval(interval);
  }, [refetchLogs]);

  return (
    <div className="px-5 py-5 grid grid-cols-1 lg:grid-cols-3 gap-6 animate-fade-in items-start">
      {/* ─── Dashboard Stats (1/3 width on large screens) ─── */}
      <div className="lg:col-span-1 space-y-5">
        <div className="flex items-center gap-2">
          <Activity size={16} className="text-blue-400" />
          <span className="text-sm font-semibold text-slate-200">System Dashboard</span>
        </div>

        {/* Stats Grid */}
        <div className="grid grid-cols-2 gap-3">
          <StatWidget
            icon={BarChart3}
            label="Trades"
            value={stats?.total_trades ?? '–'}
            color="#3b82f6"
          />
          <StatWidget
            icon={Clock}
            label="Uptime"
            value={formatUptime(stats?.uptime_seconds)}
            color="#10b981"
          />
          <StatWidget
            icon={Users}
            label="Persons"
            value={stats?.total_persons ?? '–'}
            color="#a855f7"
          />
          <StatWidget
            icon={Cpu}
            label="LLM"
            value={stats?.llm_status === 'configured' ? '✅' : '⚠️'}
            sub={stats?.llm_status}
            color={stats?.llm_status === 'configured' ? '#10b981' : '#f59e0b'}
          />
        </div>

        {/* Status Rows */}
        <div className="space-y-3">
          {/* Database */}
          <div className="glass-card p-3 flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Database size={14} className="text-slate-400" />
              <span className="text-xs text-slate-400">Database Connection</span>
            </div>
            <span className="text-xs font-semibold text-emerald-400">
              {stats?.db_status || 'checking...'}
            </span>
          </div>

          {/* Pipeline Status */}
          <div className="glass-card p-3 space-y-2">
            <span className="text-[10px] font-bold text-cyan-400 uppercase tracking-wider block">Data Ingestion Pipeline</span>
            <div className="flex justify-between items-center text-[11px]">
              <span className="text-slate-500">Last Ingestion Run</span>
              <span className="text-slate-300 font-mono">
                {stats?.last_pipeline_run ? new Date(stats.last_pipeline_run).toLocaleString() : 'Never'}
              </span>
            </div>
            <div className="flex justify-between items-center text-[11px]">
              <span className="text-slate-500">Next Scheduled Run</span>
              <span className="text-slate-300 font-mono">
                {stats?.next_pipeline_run ? new Date(stats.next_pipeline_run).toLocaleString() : 'Not scheduled'}
              </span>
            </div>
          </div>

          {/* yfinance Price Updater Status */}
          <div className="glass-card p-3 space-y-2">
            <span className="text-[10px] font-bold text-cyan-400 uppercase tracking-wider block">yfinance Stock Price Updater</span>
            <div className="flex justify-between items-center text-[11px]">
              <span className="text-slate-500">Last Price Update</span>
              <span className="text-slate-300 font-mono">
                {stats?.last_price_update ? new Date(stats.last_price_update).toLocaleString() : 'Never'}
              </span>
            </div>
            <div className="flex justify-between items-center text-[11px]">
              <span className="text-slate-500">Next Scheduled Update</span>
              <span className="text-slate-300 font-mono">
                {stats?.next_price_update ? new Date(stats.next_price_update).toLocaleString() : 'Not scheduled'}
              </span>
            </div>
          </div>

          {/* Database Backup Status */}
          <div className="glass-card p-3 space-y-2">
            <span className="text-[10px] font-bold text-cyan-400 uppercase tracking-wider block">Database Backup</span>
            <div className="flex justify-between items-center text-[11px]">
              <span className="text-slate-500">Next Scheduled Backup</span>
              <span className="text-slate-300 font-mono">
                {stats?.next_backup_run ? new Date(stats.next_backup_run).toLocaleString() : 'Not scheduled'}
              </span>
            </div>
          </div>
        </div>
      </div>

      {/* ─── Log Console (2/3 width on large screens) ─────── */}
      <div className="lg:col-span-2">
        <div className="flex items-center justify-between mb-2">
          <span className="text-xs font-semibold text-slate-400 uppercase tracking-wider">Live Logs</span>
          <span className="text-[10px] text-slate-600">{logsData?.logs?.length || 0} entries</span>
        </div>
        <LogConsole logs={logsData?.logs || []} />
      </div>
    </div>
  );
}
