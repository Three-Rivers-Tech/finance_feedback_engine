import React, { useMemo, useState } from 'react';
import apiClient, { handleApiError } from '../../api/client';
import type { AgentStatus } from '../../api/types';
import { Button } from '../common/Button';
import { Card } from '../common/Card';

type Props = {
  status: AgentStatus | null | undefined;
  onRefresh?: () => Promise<void>;
};

export const AgentControlPanel: React.FC<Props> = ({ status, onRefresh }) => {
  const [isStarting, setIsStarting] = useState(false);
  const [isStopping, setIsStopping] = useState(false);
  const [isPausing, setIsPausing] = useState(false);
  const [isResuming, setIsResuming] = useState(false);
  const [isSavingConfig, setIsSavingConfig] = useState(false);
  const [isSendingTrade, setIsSendingTrade] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [configForm, setConfigForm] = useState({
    stop_loss_pct: '',
    position_size_pct: '',
    confidence_threshold: '',
  });

  const [tradeForm, setTradeForm] = useState({
    asset_pair: '',
    action: 'BUY',
    size: '',
    price: '',
  });

  const isRunning = status?.state === 'running';
  const isPaused = useMemo(() => status?.config?.paused === true, [status]);

  const refresh = async () => {
    if (onRefresh) {
      await onRefresh();
    }
  };

  const handleStart = async () => {
    setIsStarting(true);
    setError(null);
    try {
      await apiClient.post('/api/v1/bot/start', {});
      await refresh();
    } catch (err) {
      setError(handleApiError(err));
    } finally {
      setIsStarting(false);
    }
  };

  const handleStop = async () => {
    setIsStopping(true);
    setError(null);
    try {
      await apiClient.post('/api/v1/bot/stop');
      await refresh();
    } catch (err) {
      setError(handleApiError(err));
    } finally {
      setIsStopping(false);
    }
  };

  const handlePause = async () => {
    setIsPausing(true);
    setError(null);
    try {
      await apiClient.post('/api/v1/bot/pause');
      await refresh();
    } catch (err) {
      setError(handleApiError(err));
    } finally {
      setIsPausing(false);
    }
  };

  const handleResume = async () => {
    setIsResuming(true);
    setError(null);
    try {
      await apiClient.post('/api/v1/bot/resume');
      await refresh();
    } catch (err) {
      setError(handleApiError(err));
    } finally {
      setIsResuming(false);
    }
  };

  const handleEmergencyStop = async () => {
    if (!confirm('⚠️ EMERGENCY STOP: Close all positions and halt trading immediately?')) {
      return;
    }
    setError(null);
    try {
      await apiClient.post('/api/v1/bot/emergency-stop?close_positions=true');
      await refresh();
    } catch (err) {
      setError(handleApiError(err));
    }
  };

  const handleConfigSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    setIsSavingConfig(true);
    setError(null);
    try {
      const payload = {
        stop_loss_pct: configForm.stop_loss_pct ? Number(configForm.stop_loss_pct) : undefined,
        position_size_pct: configForm.position_size_pct ? Number(configForm.position_size_pct) : undefined,
        confidence_threshold: configForm.confidence_threshold ? Number(configForm.confidence_threshold) : undefined,
      };
      await apiClient.patch('/api/v1/bot/config', payload);
      await refresh();
    } catch (err) {
      setError(handleApiError(err));
    } finally {
      setIsSavingConfig(false);
    }
  };

  const handleTradeSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    setIsSendingTrade(true);
    setError(null);
    try {
      const payload = {
        asset_pair: tradeForm.asset_pair,
        action: tradeForm.action,
        size: tradeForm.size ? Number(tradeForm.size) : undefined,
        price: tradeForm.price ? Number(tradeForm.price) : undefined,
      };
      await apiClient.post('/api/v1/bot/manual-trade', payload);
      setTradeForm({ ...tradeForm, price: '', size: '' });
      await refresh();
    } catch (err) {
      setError(handleApiError(err));
    } finally {
      setIsSendingTrade(false);
    }
  };

  return (
    <Card>
      <h2 className="text-lg font-mono font-bold text-accent-cyan mb-4 uppercase">
        Agent Controls
      </h2>
      {error && (
        <div className="mb-4 p-4 bg-accent-red bg-opacity-20 border-3 border-accent-red">
          <p className="text-xs text-accent-red font-mono">{error}</p>
        </div>
      )}

      <div className="flex flex-wrap gap-3 mb-6">
        {!isRunning ? (
          <Button variant="primary" onClick={handleStart} disabled={isStarting}>
            {isStarting ? 'Starting...' : 'Start Agent'}
          </Button>
        ) : (
          <Button variant="secondary" onClick={handleStop} disabled={isStopping}>
            {isStopping ? 'Stopping...' : 'Stop Agent'}
          </Button>
        )}

        <Button variant="danger" onClick={handleEmergencyStop}>
          🚨 Emergency Stop
        </Button>

        <Button
          variant="secondary"
          onClick={handlePause}
          disabled={!isRunning || isPaused || isPausing}
        >
          {isPausing ? 'Pausing...' : 'Pause'}
        </Button>

        <Button
          variant="primary"
          onClick={handleResume}
          disabled={!isPaused || isResuming}
        >
          {isResuming ? 'Resuming...' : 'Resume'}
        </Button>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <form className="space-y-3" onSubmit={handleConfigSubmit}>
          <p className="text-sm font-mono text-text-secondary">Live Config</p>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            <label className="flex flex-col gap-1 text-sm font-mono">
              Stop loss %
              <input
                className="bg-surface-secondary border border-border px-3 py-2 rounded"
                value={configForm.stop_loss_pct}
                onChange={(e) => setConfigForm({ ...configForm, stop_loss_pct: e.target.value })}
                placeholder="0.02"
                type="number"
                step="0.001"
                min="0"
              />
            </label>
            <label className="flex flex-col gap-1 text-sm font-mono">
              Position size %
              <input
                className="bg-surface-secondary border border-border px-3 py-2 rounded"
                value={configForm.position_size_pct}
                onChange={(e) => setConfigForm({ ...configForm, position_size_pct: e.target.value })}
                placeholder="0.01"
                type="number"
                step="0.001"
                min="0"
              />
            </label>
            <label className="flex flex-col gap-1 text-sm font-mono md:col-span-2">
              Confidence threshold
              <input
                className="bg-surface-secondary border border-border px-3 py-2 rounded"
                value={configForm.confidence_threshold}
                onChange={(e) => setConfigForm({ ...configForm, confidence_threshold: e.target.value })}
                placeholder="0.7"
                type="number"
                step="0.05"
                min="0"
                max="1"
              />
            </label>
          </div>
          <Button type="submit" variant="primary" disabled={isSavingConfig}>
            {isSavingConfig ? 'Saving...' : 'Save Config'}
          </Button>
        </form>

        <form className="space-y-3" onSubmit={handleTradeSubmit}>
          <p className="text-sm font-mono text-text-secondary">Manual Trade</p>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            <label className="flex flex-col gap-1 text-sm font-mono">
              Asset pair
              <input
                className="bg-surface-secondary border border-border px-3 py-2 rounded"
                value={tradeForm.asset_pair}
                onChange={(e) => setTradeForm({ ...tradeForm, asset_pair: e.target.value.toUpperCase() })}
                placeholder="BTCUSD"
                required
              />
            </label>
            <label className="flex flex-col gap-1 text-sm font-mono">
              Action
              <select
                className="bg-surface-secondary border border-border px-3 py-2 rounded"
                value={tradeForm.action}
                onChange={(e) => setTradeForm({ ...tradeForm, action: e.target.value })}
              >
                <option value="BUY">BUY / LONG</option>
                <option value="SELL">SELL / SHORT</option>
              </select>
            </label>
            <label className="flex flex-col gap-1 text-sm font-mono">
              Size
              <input
                className="bg-surface-secondary border border-border px-3 py-2 rounded"
                value={tradeForm.size}
                onChange={(e) => setTradeForm({ ...tradeForm, size: e.target.value })}
                type="number"
                min="0"
                step="0.0001"
                placeholder="0.01"
              />
            </label>
            <label className="flex flex-col gap-1 text-sm font-mono">
              Limit price (optional)
              <input
                className="bg-surface-secondary border border-border px-3 py-2 rounded"
                value={tradeForm.price}
                onChange={(e) => setTradeForm({ ...tradeForm, price: e.target.value })}
                type="number"
                min="0"
                step="0.01"
                placeholder="Market"
              />
            </label>
          </div>
          <Button type="submit" variant="secondary" disabled={isSendingTrade}>
            {isSendingTrade ? 'Sending...' : 'Send Trade'}
          </Button>
        </form>
      </div>
    </Card>
  );
};
