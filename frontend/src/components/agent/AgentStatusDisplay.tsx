import React from 'react';
import type { AgentStatus } from '../../api/types';
import { Card } from '../common/Card';
import { Badge } from '../common/Badge';
import { Spinner } from '../common/Spinner';
import { formatUptime } from '../../services/formatters';

type Props = {
  status: AgentStatus | null | undefined;
  isLoading?: boolean;
  isLive?: boolean;
};

export const AgentStatusDisplay: React.FC<Props> = ({ status, isLoading = false, isLive = false }) => {
  if (isLoading) {
    return (
      <Card>
        <Spinner />
      </Card>
    );
  }

  if (!status) {
    return (
      <Card>
        <p className="text-text-secondary font-mono">Agent status unavailable</p>
      </Card>
    );
  }

  const getStateVariant = (state: string) => {
    if (state === 'running') return 'success';
    if (state === 'error') return 'danger';
    if (state === 'starting' || state === 'stopping') return 'warning';
    return 'neutral';
  };

  return (
    <Card>
      <h2 className="text-lg font-mono font-bold text-accent-cyan mb-4 uppercase">
        Agent Status {isLive ? <span className="text-xs text-green-400">• live</span> : null}
      </h2>
      <div className="grid grid-cols-2 gap-4">
        <div>
          <p className="text-xs text-text-secondary mb-2">STATE</p>
          <Badge variant={getStateVariant(status.state)}>
            {status.state.toUpperCase()}
          </Badge>
        </div>
        <div>
          <p className="text-xs text-text-secondary mb-2">OODA STATE</p>
          <p className="font-mono">{status.agent_ooda_state || 'N/A'}</p>
        </div>
        <div>
          <p className="text-xs text-text-secondary mb-2">UPTIME</p>
          <p className="font-mono">
            {status.uptime_seconds ? formatUptime(status.uptime_seconds) : 'N/A'}
          </p>
        </div>
        <div>
          <p className="text-xs text-text-secondary mb-2">TOTAL TRADES</p>
          <p className="font-mono">{status.total_trades}</p>
        </div>
        <div>
          <p className="text-xs text-text-secondary mb-2">ACTIVE POSITIONS</p>
          <p className="font-mono">{status.active_positions}</p>
        </div>
        <div>
          <p className="text-xs text-text-secondary mb-2">CURRENT PAIR</p>
          <p className="font-mono">{status.current_asset_pair || 'None'}</p>
        </div>
      </div>
      {status.error_message && (
        <div className="mt-4 p-4 bg-accent-red bg-opacity-20 border-3 border-accent-red">
          <p className="text-xs text-accent-red font-mono">{status.error_message}</p>
        </div>
      )}
    </Card>
  );
};
