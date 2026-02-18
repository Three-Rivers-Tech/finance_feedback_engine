import React from 'react';
import { useHealth } from '../../api/hooks/useHealth';
import { Card } from '../common/Card';
import { Badge } from '../common/Badge';
import { Spinner } from '../common/Spinner';

interface CircuitBreakerInfo {
  state: string;
  failure_count: number;
}

export const CircuitBreakerStatus: React.FC = () => {
  const { data: health, isLoading } = useHealth();

  if (isLoading) {
    return (
      <Card>
        <Spinner />
      </Card>
    );
  }

  if (!health?.circuit_breakers) {
    return (
      <Card>
        <p className="text-text-secondary font-mono text-sm">No circuit breaker data</p>
      </Card>
    );
  }

  const getStateVariant = (state: string): 'success' | 'warning' | 'danger' => {
    if (state === 'CLOSED') return 'success';
    if (state === 'HALF_OPEN') return 'warning';
    return 'danger';
  };

  const breakers = Object.entries(health.circuit_breakers) as Array<[string, CircuitBreakerInfo]>;

  return (
    <Card>
      <h2 className="text-lg font-mono font-bold text-accent-cyan mb-4 uppercase">
        Circuit Breakers
      </h2>
      <div className="space-y-3">
        {breakers.map(([name, breaker]) => (
          <div key={name} className="flex items-center justify-between">
            <span className="font-mono text-sm">{name}</span>
            <div className="flex items-center gap-3">
              <span className="text-xs text-text-muted">Failures: {breaker.failure_count}</span>
              <Badge variant={getStateVariant(breaker.state)}>{breaker.state}</Badge>
            </div>
          </div>
        ))}
      </div>
    </Card>
  );
};
