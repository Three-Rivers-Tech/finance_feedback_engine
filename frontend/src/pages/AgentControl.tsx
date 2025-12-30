import React, { useCallback, useEffect, useMemo, useState } from 'react';
import apiClient from '../api/client';
import type { AgentStatus } from '../api/types';
import { AgentStatusDisplay } from '../components/agent/AgentStatusDisplay';
import { AgentControlPanel } from '../components/agent/AgentControlPanel';
import { CircuitBreakerStatus } from '../components/agent/CircuitBreakerStatus';
import { AgentMetricsDashboard } from '../components/agent/AgentMetricsDashboard';
import { useAgentStream } from '../api/hooks/useAgentStream';

export const AgentControl: React.FC = () => {
  const { status: liveStatus, events, isConnected, error: streamError } = useAgentStream();
  const [manualStatus, setManualStatus] = useState<AgentStatus | null>(null);

  const refreshStatus = useCallback(async () => {
    const response = await apiClient.get('/api/v1/bot/status');
    setManualStatus(response.data as AgentStatus);
  }, []);

  useEffect(() => {
    if (liveStatus) {
      // Prefer live stream updates over manual snapshots
      setManualStatus(null);
    }
  }, [liveStatus]);

  const status = useMemo(() => manualStatus ?? liveStatus, [manualStatus, liveStatus]);
  const isLoading = !status && !streamError;

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-mono font-bold text-accent-cyan uppercase">
        Agent Control
      </h1>
      {streamError && (
        <div className="p-4 border-3 border-accent-red bg-accent-red bg-opacity-10 text-xs font-mono text-accent-red">
          Live stream error: {streamError}
        </div>
      )}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <AgentStatusDisplay status={status} isLoading={isLoading} isLive={isConnected} />
        <CircuitBreakerStatus />
      </div>
      <AgentControlPanel status={status} onRefresh={refreshStatus} />
      <AgentMetricsDashboard
        status={status}
        events={events}
        isConnected={isConnected}
      />
    </div>
  );
};
