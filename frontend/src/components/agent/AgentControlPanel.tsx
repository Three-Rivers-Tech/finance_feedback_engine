import React, { useMemo, useState } from 'react';
import type { AgentStatus } from '../../api/types';
import { Button } from '../common/Button';
import { Card } from '../common/Card';
import {
  mapMutationError,
  useEmergencyStopAgent,
  useManualTrade,
  usePauseAgent,
  useResumeAgent,
  useStartAgent,
  useStopAgent,
  useUpdateAgentConfig,
} from '../../api/mutations/useAgentControl';

type Props = {
  status: AgentStatus | null | undefined;
  onRefresh?: () => Promise<unknown>;
  onStartViaSocket?: (payload: { autonomous: boolean; asset_pairs: string[] }) => Promise<void>;
  socketReady?: boolean;
  socketStartInFlight?: boolean;
};

export const AgentControlPanel: React.FC<Props> = ({
  status,
  onRefresh,
  onStartViaSocket,
  socketReady = false,
  socketStartInFlight = false,
}) => {
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

  const [startMode, setStartMode] = useState<'autonomous' | 'telegram'>('autonomous');

  const startAgent = useStartAgent();
  const stopAgent = useStopAgent();
  const pauseAgent = usePauseAgent();
  const resumeAgent = useResumeAgent();
  const emergencyStop = useEmergencyStopAgent();
  const updateConfig = useUpdateAgentConfig();
  const manualTrade = useManualTrade();

  const isRunning = status?.state === 'running';
  const isPaused = useMemo(() => status?.config?.paused === true, [status]);
  const isStartPending = startAgent.isPending || socketStartInFlight;

  const refresh = async () => {
    if (onRefresh) {
      await onRefresh();
    }
  };

  const handleStart = async () => {
    setError(null);
    try {
      if (onStartViaSocket && socketReady) {
        await onStartViaSocket({
          autonomous: startMode === 'autonomous',
          asset_pairs: ['BTCUSD', 'ETHUSD', 'EURUSD'],
        });
        return;
      }

      await startAgent.mutateAsync({
        autonomous: startMode === 'autonomous',
        asset_pairs: ['BTCUSD', 'ETHUSD', 'EURUSD'],
      });
      await refresh();
    } catch (err) {
      setError(mapMutationError(err));
    }
  };

  const handleStop = async () => {
    setError(null);
    try {
      await stopAgent.mutateAsync();
      await refresh();
    } catch (err) {
      setError(mapMutationError(err));
    }
  };

  const handlePause = async () => {
    setError(null);
    try {
      await pauseAgent.mutateAsync();
      await refresh();
    } catch (err) {
      setError(mapMutationError(err));
    }
  };

  const handleResume = async () => {
    setError(null);
    try {
      await resumeAgent.mutateAsync();
      await refresh();
    } catch (err) {
      setError(mapMutationError(err));
    }
  };

  const handleEmergencyStop = async () => {
    if (!confirm('⚠️ EMERGENCY STOP: Close all positions and halt trading immediately?')) {
      return;
    }
    setError(null);
    try {
      await emergencyStop.mutateAsync();
      await refresh();
    } catch (err) {
      setError(mapMutationError(err));
    }
  };

  const handleConfigSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    setError(null);
    try {
      const payload = {
        stop_loss_pct: configForm.stop_loss_pct ? Number(configForm.stop_loss_pct) : undefined,
        position_size_pct: configForm.position_size_pct ? Number(configForm.position_size_pct) : undefined,
        confidence_threshold: configForm.confidence_threshold ? Number(configForm.confidence_threshold) : undefined,
      };
      await updateConfig.mutateAsync(payload);
      await refresh();
    } catch (err) {
      setError(mapMutationError(err));
    }
  };

  const handleTradeSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    setError(null);
    try {
      const payload = {
        asset_pair: tradeForm.asset_pair,
        action: tradeForm.action,
        size: tradeForm.size ? Number(tradeForm.size) : undefined,
        price: tradeForm.price ? Number(tradeForm.price) : undefined,
      };
      await manualTrade.mutateAsync(payload);
      setTradeForm({ ...tradeForm, price: '', size: '' });
      await refresh();
    } catch (err) {
      setError(mapMutationError(err));
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

      {!isRunning && (
        <div className="mb-4 p-4 bg-surface-secondary border border-border rounded">
          <p className="text-sm font-mono text-text-secondary mb-3">Start Mode</p>
          <div className="flex gap-4">
            <label className="flex items-center gap-2 cursor-pointer">
              <input
                type="radio"
                name="startMode"
                value="autonomous"
                checked={startMode === 'autonomous'}
                onChange={(e) => setStartMode(e.target.value as 'autonomous')}
                className="w-4 h-4 text-accent-cyan"
              />
              <span className="text-sm font-mono">Autonomous (Full Trading)</span>
            </label>
            <label className="flex items-center gap-2 cursor-pointer">
              <input
                type="radio"
                name="startMode"
                value="telegram"
                checked={startMode === 'telegram'}
                onChange={(e) => setStartMode(e.target.value as 'telegram')}
                className="w-4 h-4 text-accent-cyan"
              />
              <span className="text-sm font-mono">Signal-Only (Telegram)</span>
            </label>
          </div>
          {startMode === 'telegram' && (
            <p className="mt-2 text-xs font-mono text-accent-yellow">
              ⚠️ Telegram mode requires bot_token and chat_id in config.yaml
            </p>
          )}
        </div>
      )}

      <div className="flex flex-wrap gap-3 mb-6">
        {!isRunning ? (
          <Button variant="primary" onClick={handleStart} disabled={isStartPending}>
            {isStartPending ? 'Starting...' : `Start Agent (${startMode === 'autonomous' ? 'Autonomous' : 'Signal-Only'})`}
          </Button>
        ) : (
          <Button variant="secondary" onClick={handleStop} disabled={stopAgent.isPending}>
            {stopAgent.isPending ? 'Stopping...' : 'Stop Agent'}
          </Button>
        )}

        <Button variant="danger" onClick={handleEmergencyStop}>
          🚨 Emergency Stop
        </Button>

        <Button
          variant="secondary"
          onClick={handlePause}
          disabled={!isRunning || isPaused || pauseAgent.isPending}
        >
          {pauseAgent.isPending ? 'Pausing...' : 'Pause'}
        </Button>

        <Button
          variant="primary"
          onClick={handleResume}
          disabled={!isPaused || resumeAgent.isPending}
        >
          {resumeAgent.isPending ? 'Resuming...' : 'Resume'}
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
          <Button type="submit" variant="primary" disabled={updateConfig.isPending}>
            {updateConfig.isPending ? 'Saving...' : 'Save Config'}
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
          <Button type="submit" variant="secondary" disabled={manualTrade.isPending}>
            {manualTrade.isPending ? 'Sending...' : 'Send Trade'}
          </Button>
        </form>
      </div>
    </Card>
  );
};
