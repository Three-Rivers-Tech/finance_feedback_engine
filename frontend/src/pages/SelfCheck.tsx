import React, { useEffect, useMemo, useState } from 'react';
import apiClient, { handleApiError } from '../api/client';
import { API_BASE_URL, APP_VERSION } from '../utils/constants';

type CheckResult = {
  ok: boolean;
  message: string;
  details?: unknown;
};

export const SelfCheck: React.FC = () => {
  const [health, setHealth] = useState<CheckResult | null>(null);
  const [botStatus, setBotStatus] = useState<CheckResult | null>(null);
  const [loading, setLoading] = useState(true);
  const [starting, setStarting] = useState(false);
  const [startMessage, setStartMessage] = useState<string | null>(null);
  const [stopping, setStopping] = useState(false);
  const [stopMessage, setStopMessage] = useState<string | null>(null);
  const [assetPair, setAssetPair] = useState<string>('BTCUSD');
  const [toast, setToast] = useState<string | null>(null);

  const apiKeyPresent = useMemo(() => !!(localStorage.getItem('api_key') || import.meta.env.VITE_API_KEY), []);

  useEffect(() => {
    let cancelled = false;

    async function runChecks() {
      setLoading(true);
      try {
        // Health check (no auth expected)
        try {
          // If API_BASE_URL is the proxy path ('/api'), call root /health to avoid '/api/health' mismatch
          const base = API_BASE_URL.replace(/\/$/, '');
          const healthUrl = base === '/api' ? '/health' : `${base}/health`;
          const res = await fetch(healthUrl);
          const data = await res.json().catch(() => ({}));
          if (!cancelled) {
            setHealth({ ok: res.ok, message: res.ok ? 'Healthy' : `HTTP ${res.status}`, details: data });
          }
        } catch (err) {
          if (!cancelled) setHealth({ ok: false, message: 'Network error reaching /health', details: String(err) });
        }

        await refreshBotStatus();
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    runChecks();
    const interval = setInterval(() => {
      refreshBotStatus();
    }, 3000);
    return () => {
      cancelled = true;
      clearInterval(interval);
    };
  }, []);

  async function handleStartBot() {
    setStarting(true);
    setStartMessage(null);
    try {
      const payload = {
        autonomous: true,
        // Keep payload minimal; backend fills defaults
      };
      const res = await apiClient.post('/api/v1/bot/start', payload);
      setStartMessage('Start request accepted');
      setBotStatus({ ok: true, message: 'RUNNING or STARTING', details: res.data });
      showToast('Bot start accepted');
    } catch (err) {
      const msg = handleApiError(err);
      setStartMessage(msg);
      setBotStatus({ ok: false, message: msg, details: err });
    } finally {
      setStarting(false);
    }
  }

  async function handleStartBotWithPair() {
    setStarting(true);
    setStartMessage(null);
    try {
      const payload = {
        autonomous: true,
        asset_pairs: [assetPair.trim()],
      };
      const res = await apiClient.post('/api/v1/bot/start', payload);
      setStartMessage(`Start ${assetPair} request accepted`);
      setBotStatus({ ok: true, message: 'RUNNING or STARTING', details: res.data });
      showToast(`Bot start for ${assetPair} accepted`);
    } catch (err) {
      const msg = handleApiError(err);
      setStartMessage(msg);
      setBotStatus({ ok: false, message: msg, details: err });
    } finally {
      setStarting(false);
    }
  }

  async function handleStopBot() {
    setStopping(true);
    setStopMessage(null);
    try {
      await apiClient.post('/api/v1/bot/stop');
      setStopMessage('Stop request accepted');
      // Refresh status after stop
      await refreshBotStatus();
      showToast('Bot stop accepted');
    } catch (err) {
      const msg = handleApiError(err);
      setStopMessage(msg);
    } finally {
      setStopping(false);
    }
  }

  async function refreshBotStatus() {
    try {
      const res = await apiClient.get('/api/v1/bot/status');
      setBotStatus({ ok: true, message: 'OK', details: res.data });
    } catch (err) {
      const msg = handleApiError(err);
      setBotStatus({ ok: false, message: msg, details: err });
    }
  }

  function showToast(message: string) {
    setToast(message);
    setTimeout(() => setToast(null), 4000);
  }

  const InfoRow: React.FC<{ label: string; value: React.ReactNode }> = ({ label, value }) => (
    <div className="flex items-start justify-between py-2">
      <div className="text-text-secondary font-mono text-xs">{label}</div>
      <div className="text-text-primary font-mono text-xs text-right max-w-[70%] break-words">{value}</div>
    </div>
  );

  const StatusBadge: React.FC<{ ok?: boolean | null; label?: string }> = ({ ok, label }) => {
    const variant = ok ? 'bg-green-500' : 'bg-red-500';
    const text = label || (ok ? 'OK' : 'ERROR');
    return (
      <span className={`inline-block px-2 py-0.5 rounded text-xs font-mono text-white ${variant}`}>{text}</span>
    );
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-mono font-bold text-accent-cyan">Self-Check</h2>
        {loading ? <span className="text-text-secondary font-mono text-xs">Running checks…</span> : null}
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <div className="border-3 border-border-primary bg-bg-secondary p-4 rounded">
          <h3 className="font-mono text-sm mb-3">Environment</h3>
          <InfoRow label="App Version" value={APP_VERSION} />
          <InfoRow label="API Base URL" value={API_BASE_URL} />
          <InfoRow label="API Key Present" value={<StatusBadge ok={apiKeyPresent} label={apiKeyPresent ? 'YES' : 'NO'} />} />
        </div>

        <div className="border-3 border-border-primary bg-bg-secondary p-4 rounded">
          <h3 className="font-mono text-sm mb-3">API Health</h3>
          <div className="flex items-center justify-between">
            <span className="font-mono text-xs text-text-secondary">/health</span>
            <StatusBadge ok={health?.ok} />
          </div>
          <pre className="mt-3 text-xs font-mono bg-bg-primary p-3 rounded max-h-56 overflow-auto">
            {JSON.stringify(health?.details ?? { message: health?.message }, null, 2)}
          </pre>
        </div>

        <div className="border-3 border-border-primary bg-bg-secondary p-4 rounded md:col-span-2">
          <h3 className="font-mono text-sm mb-3">Bot Status</h3>
          <div className="flex items-center justify-between">
            <span className="font-mono text-xs text-text-secondary">GET /api/v1/bot/status</span>
            <StatusBadge ok={botStatus?.ok} />
          </div>
          {/* Quick metrics */}
          <div className="mt-3 grid grid-cols-2 gap-3">
            <InfoRow label="State" value={String((botStatus?.details as any)?.state ?? 'unknown')} />
            <InfoRow label="Asset Pair" value={String((botStatus?.details as any)?.current_asset_pair ?? 'n/a')} />
            <InfoRow label="Total Trades" value={String((botStatus?.details as any)?.total_trades ?? '0')} />
            <InfoRow label="Portfolio Value" value={String((botStatus?.details as any)?.portfolio_value ?? 'n/a')} />
            <InfoRow label="Daily PnL" value={String((botStatus?.details as any)?.daily_pnl ?? 'n/a')} />
          </div>
          <div className="mt-3 flex items-center gap-3">
            <button
              onClick={handleStartBot}
              disabled={starting}
              className={`px-3 py-1 font-mono text-xs border-3 rounded ${
                starting
                  ? 'bg-border-primary text-text-secondary cursor-not-allowed'
                  : 'bg-accent-cyan text-bg-primary hover:opacity-90'
              }`}
            >
              {starting ? 'Starting…' : 'Start Bot'}
            </button>
            <input
              value={assetPair}
              onChange={(e) => setAssetPair(e.target.value.toUpperCase())}
              className="px-2 py-1 font-mono text-xs border-3 border-border-primary rounded bg-bg-primary text-text-primary w-28"
              placeholder="BTCUSD"
              aria-label="Asset Pair"
            />
            <button
              onClick={handleStartBotWithPair}
              disabled={starting || !assetPair.trim()}
              className={`px-3 py-1 font-mono text-xs border-3 rounded ${
                starting || !assetPair.trim()
                  ? 'bg-border-primary text-text-secondary cursor-not-allowed'
                  : 'bg-accent-cyan text-bg-primary hover:opacity-90'
              }`}
            >
              {starting ? 'Starting…' : `Start ${assetPair}`}
            </button>
            <button
              onClick={handleStopBot}
              disabled={stopping}
              className={`px-3 py-1 font-mono text-xs border-3 rounded ${
                stopping
                  ? 'bg-border-primary text-text-secondary cursor-not-allowed'
                  : 'bg-red-500 text-bg-primary hover:opacity-90'
              }`}
            >
              {stopping ? 'Stopping…' : 'Stop Bot'}
            </button>
            {startMessage && (
              <span className="text-xs font-mono text-text-secondary">{startMessage}</span>
            )}
            {stopMessage && (
              <span className="text-xs font-mono text-text-secondary">{stopMessage}</span>
            )}
          </div>
          {!apiKeyPresent && (
            <div className="mt-3 text-xs font-mono text-yellow-400">
              Tip: If you see 401 Unauthorized, set an API key in localStorage under key "api_key" or define VITE_API_KEY in frontend .env.
            </div>
          )}
          <pre className="mt-3 text-xs font-mono bg-bg-primary p-3 rounded max-h-72 overflow-auto">
            {JSON.stringify(botStatus?.details ?? { message: botStatus?.message }, null, 2)}
          </pre>
        </div>
      </div>

      <div className="border-3 border-border-primary bg-bg-secondary p-4 rounded">
        <h3 className="font-mono text-sm mb-3">Quick Fixes</h3>
        <ul className="list-disc ml-5 space-y-1 text-xs font-mono text-text-secondary">
          <li>Backend: start with ENVIRONMENT=development and ALLOW_API_WITHOUT_DB=1 for local testing.</li>
          <li>Frontend: ensure VITE_API_BASE_URL points to your API (e.g., http://localhost:8001).</li>
          <li>If bot status returns 401, set an API key via localStorage: localStorage.setItem('api_key', 'your-key').</li>
        </ul>
      </div>

      {toast && (
        <div className="fixed bottom-4 right-4 px-4 py-3 bg-bg-secondary border-3 border-accent-cyan rounded shadow-lg font-mono text-xs text-text-primary">
          {toast}
        </div>
      )}
    </div>
  );
};

export default SelfCheck;
