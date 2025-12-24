import React from 'react';
import { AgentStatusDisplay } from '../components/agent/AgentStatusDisplay';
import { AgentControlPanel } from '../components/agent/AgentControlPanel';
import { CircuitBreakerStatus } from '../components/agent/CircuitBreakerStatus';

export const AgentControl: React.FC = () => {
  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-mono font-bold text-accent-cyan uppercase">
        Agent Control
      </h1>
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <AgentStatusDisplay />
        <CircuitBreakerStatus />
      </div>
      <AgentControlPanel />
    </div>
  );
};
