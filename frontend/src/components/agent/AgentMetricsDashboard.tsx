import React, { useMemo, useState } from 'react';
import type { AgentStatus, Position, Decision } from '../../api/types';
import type { AgentStreamEvent } from '../../api/hooks/useAgentStream';
import { Card } from '../common/Card';
import { Badge } from '../common/Badge';
import { usePositions } from '../../api/hooks/usePositions';
import { useDecisions } from '../../api/hooks/useDecisions';
import { mapMutationError, useClosePosition } from '../../api/mutations/useAgentControl';

interface Props {
  status: AgentStatus | null | undefined;
  events: AgentStreamEvent[];
  isConnected: boolean;
}

export const AgentMetricsDashboard: React.FC<Props> = ({ status, events, isConnected }) => {
  const { data: positionsData, refetch: refetchPositions } = usePositions();
  const positions: Position[] = positionsData ?? [];
  const { data: decisionsData } = useDecisions(5);
  const decisions: Decision[] = decisionsData ?? [];
  const [closeError, setCloseError] = useState<string | null>(null);
  const [closingIds, setClosingIds] = useState<Set<string>>(new Set());
  const closePosition = useClosePosition();

  // Helper to normalize confidence values to 0-100 range
  const normalizeConfidence = (value: number | undefined): number | null => {
    if (value === null || value === undefined || Number.isNaN(value)) {
      return null;
    }
    // If value is in 0-1 range, multiply by 100; otherwise assume already a percentage
    return value <= 1 ? value * 100 : value;
  };

  const recentDecisions = useMemo(() => {
    const decisionEvents = events.filter((evt) =>
      ['decision_approved', 'decision_rejected'].includes(evt.event)
    );
    return decisionEvents.slice(-5).reverse();
  }, [events]);

  const signalAlerts = useMemo(() => {
    return events
      .filter((evt) => evt.event === 'signal_delivery_failure')
      .slice(-3)
      .reverse();
  }, [events]);

  const avgConfidence = useMemo(() => {
    const decisionEvents = events.filter((evt) =>
      ['decision_approved', 'decision_rejected'].includes(evt.event)
    );
    const confidences = decisionEvents
      .map((evt) => {
        const rawValue = evt.data?.confidence ?? evt.data?.confidence_score ?? 0;
        return normalizeConfidence(Number(rawValue));
      })
      .filter((v) => v !== null && v > 0) as number[];

    return confidences && confidences.length
      ? confidences.reduce((acc, v) => acc + v, 0) / confidences.length
      : null;
  }, [events]);

  const totalUnrealized = useMemo(
    () => (Array.isArray(positions) ? positions : []).reduce((acc, pos) => acc + (pos.unrealized_pnl || 0), 0),
    [positions]
  );

  const handleClosePosition = async (positionId: string) => {
    setCloseError(null);
    setClosingIds((prev) => new Set(prev).add(positionId));
    try {
      await closePosition.mutateAsync(positionId);
      await refetchPositions();
    } catch (err) {
      setCloseError(mapMutationError(err));
    } finally {
      setClosingIds((prev) => {
        const next = new Set(prev);
        next.delete(positionId);
        return next;
      });
    }
  };

  return (
    <Card>
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-lg font-mono font-bold text-accent-cyan uppercase">Live Metrics</h2>
        <Badge variant={isConnected ? 'success' : 'danger'}>
          {isConnected ? 'STREAMING' : 'DISCONNECTED'}
        </Badge>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
        <div>
          <p className="text-xs text-text-secondary mb-1">PORTFOLIO VALUE</p>
          <p className="font-mono text-lg">
            {status?.portfolio_value !== null && status?.portfolio_value !== undefined
              ? `$${status.portfolio_value.toFixed(2)}`
              : 'N/A'}
          </p>
        </div>
        <div>
          <p className="text-xs text-text-secondary mb-1">UNREALIZED P&L</p>
          <p className={`font-mono text-lg ${totalUnrealized >= 0 ? 'text-green-300' : 'text-accent-red'}`}>
            {totalUnrealized >= 0 ? '+' : ''}{totalUnrealized.toFixed(2)}
          </p>
        </div>
        <div>
          <p className="text-xs text-text-secondary mb-1">AVG CONFIDENCE (RECENT)</p>
          <p className="font-mono text-lg">
            {avgConfidence !== null && avgConfidence !== undefined
              ? `${avgConfidence.toFixed(1)}%`
              : 'N/A'}
          </p>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <div className="space-y-3">
          <p className="text-sm font-mono text-text-secondary">Recent Decisions</p>
          <div className="space-y-2">
            {recentDecisions && recentDecisions.length === 0 && (
              <p className="text-xs font-mono text-text-muted">No recent decisions</p>
            )}
            {recentDecisions && recentDecisions.map((evt, idx) => (
              <div
                key={`${evt.event}-${idx}`}
                className="flex items-center justify-between rounded border border-border px-3 py-2"
              >
                <div>
                  <p className="font-mono text-sm">{evt.data?.asset || evt.data?.asset_pair}</p>
                  <p className="text-xs text-text-secondary font-mono">{evt.data?.reason || evt.data?.reasoning}</p>
                </div>
                <Badge variant={evt.event === 'decision_approved' ? 'success' : 'danger'}>
                  {evt.data?.action}
                  {evt.data?.confidence !== undefined && evt.data?.confidence !== null
                    ? ` ${normalizeConfidence(Number(evt.data.confidence))?.toFixed(0) ?? ''}%`
                    : ''}
                </Badge>
              </div>
            ))}
          </div>
        </div>

        <div className="space-y-3">
          <p className="text-sm font-mono text-text-secondary">Open Positions</p>
          {closeError && (
            <p className="text-xs font-mono text-accent-red">{closeError}</p>
          )}
          <div className="space-y-2">
            {positions.length === 0 && (
              <p className="text-xs font-mono text-text-muted">No active positions</p>
            )}
            {Array.isArray(positions) && positions.map((pos) => (
              <div
                key={pos.id}
                className="flex items-center justify-between rounded border border-border px-3 py-2"
              >
                <div>
                  <p className="font-mono text-sm">{pos.asset_pair}</p>
                  <p className="text-xs text-text-secondary font-mono">
                    {pos.side} • {pos.size} @ {pos.entry_price}
                  </p>
                </div>
                <div className="flex items-center gap-2">
                  <Badge variant={pos.unrealized_pnl >= 0 ? 'success' : 'danger'}>
                    {pos.unrealized_pnl >= 0 ? '+' : ''}{pos.unrealized_pnl.toFixed(2)}
                  </Badge>
                  <button
                    className="text-xs font-mono px-2 py-1 border border-border rounded hover:border-accent-cyan"
                    onClick={() => handleClosePosition(pos.id)}
                    disabled={closingIds.has(pos.id)}
                  >
                    {closingIds.has(pos.id) ? 'Closing…' : 'Close'}
                  </button>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mt-6">
        <div className="space-y-2">
          <p className="text-sm font-mono text-text-secondary">Signal Delivery Alerts</p>
          {signalAlerts && signalAlerts.length === 0 && (
            <p className="text-xs font-mono text-text-muted">No signal delivery issues</p>
          )}
          {signalAlerts && signalAlerts.map((evt, idx) => (
            <div
              key={`alert-${idx}`}
              className="rounded border border-accent-red px-3 py-2 bg-accent-red bg-opacity-10"
            >
              <p className="font-mono text-sm text-accent-red">Failures: {evt.data?.failed_count}</p>
              {evt.data?.reasons && (
                <p className="text-xs text-accent-red font-mono">{evt.data.reasons.join('; ')}</p>
              )}
            </div>
          ))}
        </div>

        <div className="space-y-2">
          <p className="text-sm font-mono text-text-secondary">Recent Decisions (API)</p>
          {decisions.length === 0 && (
            <p className="text-xs font-mono text-text-muted">No recent decisions</p>
          )}
          {Array.isArray(decisions) && decisions.map((decision) => (
            <div
              key={decision.decision_id}
              className="flex items-center justify-between rounded border border-border px-3 py-2"
            >
              <div>
                <p className="font-mono text-sm">{decision.asset_pair}</p>
                <p className="text-xs text-text-secondary font-mono">
                  {(decision.reasoning || '').slice(0, 120)}
                </p>
              </div>
              <Badge variant={decision.action === 'BUY' ? 'success' : 'warning'}>
                {decision.action}
                {decision.confidence !== undefined && decision.confidence !== null
                  ? ` ${normalizeConfidence(Number(decision.confidence))?.toFixed(0) ?? ''}%`
                  : ''}
              </Badge>
            </div>
          ))}
        </div>
      </div>
    </Card>
  );
};
