import React, { useMemo, useState } from 'react';
import type { AgentStreamEvent } from '../../api/hooks/useAgentStream';
import { Card } from '../common/Card';
import { Badge } from '../common/Badge';
import { Spinner } from '../common/Spinner';

interface AgentActivityFeedProps {
  events: AgentStreamEvent[];
  isConnected: boolean;
  isLoading?: boolean;
}

interface ActivityItem {
  id: string;
  timestamp: number;
  type: string;
  title: string;
  description?: string;
  variant: 'success' | 'warning' | 'danger' | 'info';
  icon: string;
}

export const AgentActivityFeed: React.FC<AgentActivityFeedProps> = ({
  events,
  isConnected,
  isLoading = false,
}) => {
  const [maxEvents, setMaxEvents] = useState(10);

  const activities = useMemo<ActivityItem[]>(() => {
    if (!Array.isArray(events)) {
      return [];
    }
    return events
      .filter((e) => e.event !== 'heartbeat' && e.event !== 'status')
      .map((event, index): ActivityItem => {
        const timestamp = event.data?.timestamp || Date.now() / 1000;
        const id = `${event.event}-${timestamp}-${index}`;

        switch (event.event) {
          case 'state_transition':
            return {
              id,
              timestamp,
              type: event.event,
              title: `State: ${event.data.from} → ${event.data.to}`,
              description: formatStateDescription(event.data.to),
              variant: getStateVariant(event.data.to),
              icon: getStateIcon(event.data.to),
            };

          case 'decision_made': {
            const action = event.data.action;
            const variant: 'success' | 'danger' | 'info' = action === 'BUY' ? 'success' : action === 'SELL' ? 'danger' : 'info';
            return {
              id,
              timestamp,
              type: event.event,
              title: `Decision: ${action} ${event.data.asset_pair}`,
              description: `Confidence: ${event.data.confidence}% • ${event.data.reasoning?.substring(0, 60)}...`,
              variant,
              icon: '📊',
            };
          }

          case 'trade_executed': {
            const side = event.data.side;
            const variant: 'success' | 'danger' = side === 'LONG' ? 'success' : 'danger';
            return {
              id,
              timestamp,
              type: event.event,
              title: `Trade Executed: ${side} ${event.data.asset_pair}`,
              description: `Size: ${event.data.size} @ $${event.data.entry_price?.toFixed(2)}`,
              variant,
              icon: '✅',
            };
          }

          case 'position_closed': {
            const pnl = event.data.pnl_pct || 0;
            const variant: 'success' | 'danger' = pnl > 0 ? 'success' : 'danger';
            return {
              id,
              timestamp,
              type: event.event,
              title: `Position Closed: ${event.data.asset_pair}`,
              description: `P&L: ${pnl > 0 ? '+' : ''}${pnl?.toFixed(2)}%`,
              variant,
              icon: pnl > 0 ? '🎉' : '💔',
            };
          }

          case 'error':
            return {
              id,
              timestamp,
              type: event.event,
              title: 'Error Occurred',
              description: event.data.message || event.data.error || 'Unknown error',
              variant: 'danger' as const,
              icon: '⚠️',
            };

          case 'recovery_complete':
            return {
              id,
              timestamp,
              type: event.event,
              title: 'Recovery Complete',
              description: `Recovered ${event.data.positions_count || 0} positions`,
              variant: 'success' as const,
              icon: '🔄',
            };

          case 'recovery_failed':
            return {
              id,
              timestamp,
              type: event.event,
              title: 'Recovery Failed',
              description: event.data.error || 'Recovery process failed',
              variant: 'danger' as const,
              icon: '❌',
            };

          case 'risk_check_failed':
            return {
              id,
              timestamp,
              type: event.event,
              title: 'Risk Check Failed',
              description: event.data.reason || 'Risk limits exceeded',
              variant: 'warning' as const,
              icon: '🛑',
            };

          default:
            return {
              id,
              timestamp,
              type: event.event,
              title: formatEventType(event.event),
              description: JSON.stringify(event.data).substring(0, 80),
              variant: 'info' as const,
              icon: '•',
            };
        }
      })
      .sort((a, b) => b.timestamp - a.timestamp)
      .slice(0, maxEvents);
  }, [events, maxEvents]);

  const totalEvents = Array.isArray(events)
    ? events.filter((e) => e.event !== 'heartbeat' && e.event !== 'status').length
    : 0;

  if (isLoading) {
    return (
      <Card>
        <div className="flex items-center justify-center py-8">
          <Spinner />
        </div>
      </Card>
    );
  }

  return (
    <Card>
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-3">
          <h2 className="text-lg font-mono font-bold text-accent-cyan uppercase">
            Activity Feed
          </h2>
          {totalEvents > 0 && (
            <Badge variant="info" className="text-xs">
              {totalEvents}
            </Badge>
          )}
        </div>
        <div className="flex items-center gap-2">
          <div className={`w-2 h-2 rounded-full ${isConnected ? 'bg-accent-green' : 'bg-accent-red'} animate-pulse`} />
          <span className="text-xs text-text-muted font-mono">
            {isConnected ? 'LIVE' : 'DISCONNECTED'}
          </span>
        </div>
      </div>

      {activities.length === 0 ? (
        <div className="text-center py-8 text-text-muted font-mono text-sm">
          {isConnected ? 'Waiting for activity...' : 'No recent activity'}
        </div>
      ) : (
        <>
          <div className="space-y-3 max-h-[400px] overflow-y-auto pr-2 custom-scrollbar">
            {activities.map((activity) => (
              <div
                key={activity.id}
                className="flex items-start gap-3 p-3 rounded border border-border-primary bg-bg-secondary hover:bg-bg-tertiary transition-colors"
              >
                <div className="text-2xl flex-shrink-0 mt-0.5">
                  {activity.icon}
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-start justify-between gap-2 mb-1">
                    <h3 className="text-sm font-mono font-semibold text-text-primary truncate">
                      {activity.title}
                    </h3>
                    <Badge variant={activity.variant} className="flex-shrink-0 text-xs">
                      {formatEventType(activity.type)}
                    </Badge>
                  </div>
                  {activity.description && (
                    <p className="text-xs text-text-secondary font-mono line-clamp-2">
                      {activity.description}
                    </p>
                  )}
                  <div className="text-xs text-text-muted font-mono mt-1">
                    {formatTimestamp(activity.timestamp)}
                  </div>
                </div>
              </div>
            ))}
          </div>

          {totalEvents > maxEvents && (
            <button
              onClick={() => setMaxEvents(maxEvents + 10)}
              className="w-full mt-3 py-2 text-xs font-mono text-accent-cyan hover:text-accent-cyan-bright border border-accent-cyan hover:border-accent-cyan-bright rounded transition-colors"
            >
              Show More ({totalEvents - maxEvents} remaining)
            </button>
          )}
        </>
      )}
    </Card>
  );
};

function formatStateDescription(state: string): string {
  const descriptions: Record<string, string> = {
    IDLE: 'Waiting for next cycle',
    RECOVERING: 'Recovering open positions',
    PERCEPTION: 'Gathering market data',
    REASONING: 'Analyzing decision with AI',
    RISK_CHECK: 'Validating risk constraints',
    EXECUTION: 'Executing trade',
    LEARNING: 'Recording feedback',
  };
  return descriptions[state] || state;
}

function getStateVariant(state: string): 'success' | 'warning' | 'danger' | 'info' {
  const variants: Record<string, 'success' | 'warning' | 'danger' | 'info'> = {
    IDLE: 'info',
    RECOVERING: 'warning',
    PERCEPTION: 'info',
    REASONING: 'info',
    RISK_CHECK: 'warning',
    EXECUTION: 'success',
    LEARNING: 'success',
  };
  return variants[state] || 'info';
}

function getStateIcon(state: string): string {
  const icons: Record<string, string> = {
    IDLE: '⏸️',
    RECOVERING: '🔄',
    PERCEPTION: '👁️',
    REASONING: '🧠',
    RISK_CHECK: '🔍',
    EXECUTION: '⚡',
    LEARNING: '📚',
  };
  return icons[state] || '🤖';
}

function formatEventType(type: string): string {
  return type
    .split('_')
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1).toLowerCase())
    .join(' ');
}

function formatTimestamp(timestamp: number): string {
  const date = new Date(timestamp * 1000);
  const now = new Date();
  const diff = now.getTime() - date.getTime();
  const seconds = Math.floor(diff / 1000);
  const minutes = Math.floor(seconds / 60);
  const hours = Math.floor(minutes / 60);

  if (seconds < 60) {
    return `${seconds}s ago`;
  } else if (minutes < 60) {
    return `${minutes}m ago`;
  } else if (hours < 24) {
    return `${hours}h ago`;
  } else {
    return date.toLocaleTimeString();
  }
}
