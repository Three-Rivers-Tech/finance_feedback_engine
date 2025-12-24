import React from 'react';
import { useDecisions } from '../../api/hooks/useDecisions';
import { Card } from '../common/Card';
import { Spinner } from '../common/Spinner';
import { Badge } from '../common/Badge';
import { formatRelativeTime } from '../../services/formatters';

export const RecentDecisions: React.FC = () => {
  const { data: decisions, isLoading } = useDecisions(10);

  if (isLoading) {
    return (
      <Card>
        <Spinner />
      </Card>
    );
  }

  if (!decisions || decisions.length === 0) {
    return (
      <Card>
        <p className="text-center text-text-secondary font-mono">No recent decisions</p>
      </Card>
    );
  }

  const getActionVariant = (action: string) => {
    if (action === 'BUY') return 'success';
    if (action === 'SELL') return 'danger';
    return 'warning';
  };

  return (
    <Card>
      <h2 className="text-lg font-mono font-bold text-accent-cyan mb-4 uppercase">
        Recent AI Decisions
      </h2>
      <div className="space-y-4">
        {decisions.map((decision) => (
          <div
            key={decision.decision_id}
            className="border-l-3 border-border-primary pl-4 hover:border-accent-cyan transition-colors"
          >
            <div className="flex items-start justify-between gap-4">
              <div className="flex-1">
                <div className="flex items-center gap-3 mb-2">
                  <span className="font-mono font-bold">{decision.asset_pair}</span>
                  <Badge variant={getActionVariant(decision.action)}>
                    {decision.action}
                  </Badge>
                  <span className="text-xs text-text-secondary">
                    Confidence: {decision.confidence.toFixed(0)}%
                  </span>
                </div>
                <p className="text-sm text-text-secondary">{decision.reasoning}</p>
              </div>
              <div className="text-right">
                <p className="text-xs text-text-muted">
                  {formatRelativeTime(decision.timestamp)}
                </p>
              </div>
            </div>
          </div>
        ))}
      </div>
    </Card>
  );
};
