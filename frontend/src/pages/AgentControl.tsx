import React, { useMemo } from 'react';
import type { AgentStatus } from '../api/types';
import { AgentStatusDisplay } from '../components/agent/AgentStatusDisplay';
import { AgentControlPanel } from '../components/agent/AgentControlPanel';
import { AgentActivityFeed } from '../components/agent/AgentActivityFeed';
import { AgentMetricsDashboard } from '../components/agent/AgentMetricsDashboard';
import { useAgentStream } from '../api/hooks/useAgentStream';
import { OllamaStatusAlert } from '../components/common/OllamaStatusAlert';
import { useHealth } from '../api/hooks/useHealth';
import { useAgentStatus } from '../api/hooks/useAgentStatus';

export const AgentControl: React.FC = () => {
  const {
    status: liveStatus,
    events,
    isConnected,
    error: streamError,
    sendStart,
    canSendCommands,
    startInFlight,
  } = useAgentStream();
  const { data: health, isLoading: healthLoading } = useHealth();
  const {
    data: snapshotStatus,
    isLoading: statusLoading,
    isFetching: statusFetching,
    refetch: refetchStatus,
  } = useAgentStatus();

  const status = useMemo<AgentStatus | null | undefined>(
    () => liveStatus ?? snapshotStatus,
    [liveStatus, snapshotStatus]
  );
  const isLoading = !status && !streamError && (statusLoading || statusFetching);

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-mono font-bold text-accent-cyan uppercase">
        Agent Control
      </h1>

      {/* Ollama status warning for debate mode */}
      {!healthLoading && health?.components?.ollama && (
        <OllamaStatusAlert ollama={health.components.ollama} />
      )}

      {streamError && (
        <div className="p-4 border-3 border-accent-red bg-accent-red bg-opacity-10 text-xs font-mono text-accent-red">
          Live stream error: {streamError}
        </div>
      )}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <AgentStatusDisplay status={status} isLoading={isLoading} isLive={isConnected} />
        <AgentActivityFeed events={events} isConnected={isConnected} isLoading={isLoading} />
      </div>
      <AgentControlPanel
        status={status}
        onRefresh={refetchStatus}
        onStartViaSocket={sendStart}
        socketReady={canSendCommands}
        socketStartInFlight={startInFlight}
      />
      <AgentMetricsDashboard
        status={status}
        events={events}
        isConnected={isConnected}
      />
    </div>
  );
};
