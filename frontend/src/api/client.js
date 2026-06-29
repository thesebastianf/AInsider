/**
 * AInsider Tracker – API Client
 * Fetch wrapper for all backend API calls.
 */

const BASE = '/api';

async function request(path, options = {}) {
  const url = `${BASE}${path}`;
  const config = {
    headers: { 'Content-Type': 'application/json', ...options.headers },
    ...options,
  };

  const resp = await fetch(url, config);

  if (!resp.ok) {
    const error = await resp.text().catch(() => 'Unknown error');
    throw new Error(`API ${resp.status}: ${error}`);
  }

  if (resp.status === 204) return null;
  return resp.json();
}

// ═══ Persons ═════════════════════════════════════════════════
export const getPersons = (params = {}) => {
  const qs = new URLSearchParams(params).toString();
  return request(`/persons${qs ? `?${qs}` : ''}`);
};

export const toggleFollow = (personId) =>
  request(`/persons/${personId}/follow`, { method: 'PUT' });

export const createPerson = (data) =>
  request('/persons', { method: 'POST', body: JSON.stringify(data) });

export const getAvailablePersons = (params = {}) => {
  const qs = new URLSearchParams(params).toString();
  return request(`/persons/available/list${qs ? `?${qs}` : ''}`);
};

export const trackPerson = (id, isTracked = true) =>
  request(`/persons/${id}/track?is_tracked=${isTracked}`, { method: 'PUT' });

export const toggleSubscription = (personId) =>
  request(`/persons/${personId}/subscribe`, { method: 'PUT' });

export const updateDisplayName = (personId, displayName) =>
  request(`/persons/${personId}/display-name`, {
    method: 'PUT',
    body: JSON.stringify({ display_name: displayName || null }),
  });

export const uploadPersonPhoto = (personId, file) => {
  const fd = new FormData();
  fd.append('file', file);
  return fetch(`/api/persons/${personId}/upload-photo`, { method: 'POST', body: fd })
    .then(r => { if (!r.ok) throw new Error('Upload failed'); return r.json(); });
};

export const deletePersonPhoto = (personId) =>
  request(`/persons/${personId}/upload-photo`, { method: 'DELETE' });

// ═══ Trades ══════════════════════════════════════════════════
export const getTrades = (params = {}) => {
  const qs = new URLSearchParams(params).toString();
  return request(`/trades${qs ? `?${qs}` : ''}`);
};

// ═══ Performance ═════════════════════════════════════════════
export const getPerformance = (ticker) =>
  request(`/performance/${ticker}`);

export const getAllPerformance = () =>
  request('/performance');

// ═══ Settings ════════════════════════════════════════════════
export const getSettings = () => request('/settings');
export const updateSettings = (data) =>
  request('/settings', { method: 'PUT', body: JSON.stringify(data) });

// ═══ LLM Providers ═══════════════════════════════════════════
export const getLLMProviders = () => request('/settings/llm');
export const createLLMProvider = (data) =>
  request('/settings/llm', { method: 'POST', body: JSON.stringify(data) });
export const updateLLMProvider = (id, data) =>
  request(`/settings/llm/${id}`, { method: 'PUT', body: JSON.stringify(data) });
export const activateLLMProvider = (id) =>
  request(`/settings/llm/${id}/activate`, { method: 'PUT' });
export const deleteLLMProvider = (id) =>
  request(`/settings/llm/${id}`, { method: 'DELETE' });
export const testLLMProvider = (id) =>
  request(`/settings/llm/${id}/test`, { method: 'POST' });

// ═══ Notification Providers ══════════════════════════════════
export const getNotificationProviders = () => request('/settings/notifications');
export const getNotificationFields = () => request('/settings/notifications/fields');
export const createNotificationProvider = (data) =>
  request('/settings/notifications', { method: 'POST', body: JSON.stringify(data) });
export const updateNotificationProvider = (id, data) =>
  request(`/settings/notifications/${id}`, { method: 'PUT', body: JSON.stringify(data) });
export const deleteNotificationProvider = (id) =>
  request(`/settings/notifications/${id}`, { method: 'DELETE' });
export const testNotificationProvider = (id) =>
  request(`/settings/notifications/${id}/test`, { method: 'POST' });

// ═══ System ══════════════════════════════════════════════════
export const getSystemStats = () => request('/system/stats');
export const getSystemLogs = (limit = 100) => request(`/system/logs?limit=${limit}`);
export const triggerPipeline = () =>
  request('/system/trigger-pipeline', { method: 'POST' });
export const triggerBackup = () =>
  request('/system/trigger-backup', { method: 'POST' });
export const triggerPrices = () =>
  request('/system/trigger-prices', { method: 'POST' });
export const healthCheck = () => request('/health');
export const getInsights = () => request('/system/insights');
