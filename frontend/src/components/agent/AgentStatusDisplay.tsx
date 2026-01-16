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

  const getUnifiedStateVariant = (unifiedStatus: string): string => {
    switch (unifiedStatus) {
      case 'ready':
      case 'active':
        return 'success'; // Green
      case 'error':
        return 'danger'; // Red
      case 'transitioning':
      case 'initializing':
        return 'warning'; // Yellow
      case 'offline':
      default:
        return 'neutral'; // Gray
    }
  };

  const getOodaStateDisplay = (oodaState: string | null) => {
    if (!oodaState) return 'N/A';

    // Special handling for RECOVERING state with blue color and spinner
    if (oodaState === 'RECOVERING') {
      return (
        <div className="flex items-center gap-2">
          <span className="animate-spin inline-block w-4 h-4 border-2 border-blue-400 border-t-transparent rounded-full" />
          <span className="text-blue-400 font-mono">{oodaState}</span>
        </div>
      );
    }

    // Active states (green)
    if (['PERCEPTION', 'REASONING', 'RISK_CHECK', 'EXECUTION', 'LEARNING'].includes(oodaState)) {
      return <span className="text-green-400 font-mono">{oodaState}</span>;
    }

    // Default (IDLE or other)
    return <span className="font-mono">{oodaState}</span>;
  };

  return (
    <Card>
      <h2 className="text-lg font-mono font-bold text-accent-cyan mb-4 uppercase">
        Agent Status {isLive ? <span className="text-xs text-green-400">• live</span> : null}
      </h2>
      <div className="grid grid-cols-2 gap-4">
        <div>
          <p className="text-xs text-text-secondary mb-2">STATUS</p>
          <Badge variant={getUnifiedStateVariant(status.unified_status)}>
            {(status.unified_status || 'unknown').toUpperCase()}
          </Badge>
          {status.status_description && (
            <p className="text-xs text-text-secondary mt-1">
              {status.status_description}
        <div>
          <p className="text-xs text-text-secondary mb-2">OPERATIONAL</p>
          <p className="font-mono">
            {status.is_operational === true ? (
              <span className="text-green-400">+ Yes</span>
            ) : status.is_operational === false ? (
              <span className="text-red-400">- No</span>
            ) : (
              <span className="text-text-secondary">Unknown</span>
            )}
          </p>
        </div>
        <div>
            <p className="text-xs text-text-secondary mb-2">
                DETAILED STATE
                <span className="ml-1 text-xs opacity-50">(advanced)</span>
            </p>
            {getOodaStateDisplay(status.agent_ooda_state)}
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
      {status.agent_ooda_state === 'RECOVERING' && (
        <div className="mt-4 p-4 bg-blue-500 bg-opacity-20 border-2 border-blue-400 rounded">
          <p className="text-sm text-blue-300 font-mono">
            ⏳ Checking for existing positions...
          </p>
        </div>
      )}
      {status.error_message && (
        <div className="mt-4 p-4 bg-accent-red bg-opacity-20 border-3 border-accent-red">
          <p className="text-xs text-accent-red font-mono">{status.error_message}</p>
        </div>
      )}
    </Card>
  );
};
