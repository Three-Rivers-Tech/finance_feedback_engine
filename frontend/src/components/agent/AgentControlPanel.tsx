import React, { useState } from 'react';
import apiClient, { handleApiError } from '../../api/client';
import { Button } from '../common/Button';
import { Card } from '../common/Card';
import { useAgentStatus } from '../../api/hooks/useAgentStatus';

export const AgentControlPanel: React.FC = () => {
  const { data: status, refetch } = useAgentStatus();
  const [isStarting, setIsStarting] = useState(false);
  const [isStopping, setIsStopping] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleStart = async () => {
    setIsStarting(true);
    setError(null);
    try {
      await apiClient.post('/api/v1/bot/start');
      await refetch();
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
      await refetch();
    } catch (err) {
      setError(handleApiError(err));
    } finally {
      setIsStopping(false);
    }
  };

  const handleEmergencyStop = async () => {
    if (!confirm('⚠️ EMERGENCY STOP: Close all positions and halt trading immediately?')) {
      return;
    }
    setError(null);
    try {
      await apiClient.post('/api/v1/bot/emergency-stop?close_positions=true');
      await refetch();
    } catch (err) {
      setError(handleApiError(err));
    }
  };

  const isRunning = status?.state === 'running';

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
      <div className="flex gap-4">
        {!isRunning ? (
          <Button
            variant="primary"
            onClick={handleStart}
            disabled={isStarting}
          >
            {isStarting ? 'Starting...' : 'Start Agent'}
          </Button>
        ) : (
          <Button
            variant="secondary"
            onClick={handleStop}
            disabled={isStopping}
          >
            {isStopping ? 'Stopping...' : 'Stop Agent'}
          </Button>
        )}
        <Button
          variant="danger"
          onClick={handleEmergencyStop}
        >
          🚨 Emergency Stop
        </Button>
      </div>
    </Card>
  );
};
