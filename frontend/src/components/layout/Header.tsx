import React from 'react';
import { useHealth } from '../../api/hooks/useHealth';
import { Badge } from '../common/Badge';
import { APP_VERSION } from '../../utils/constants';

export const Header: React.FC = () => {
  const { data: health } = useHealth();

  const statusVariant = health?.status === 'healthy' ? 'success' : health?.status === 'degraded' ? 'warning' : 'danger';

  return (
    <header className="bg-bg-secondary border-b-3 border-border-primary px-6 py-4">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-mono font-bold text-accent-cyan">
            FINANCE FEEDBACK ENGINE
          </h1>
          <p className="text-xs text-text-secondary font-mono mt-1">v{APP_VERSION}</p>
        </div>
        <div className="flex items-center gap-4">
          {health && (
            <div className="flex items-center gap-2">
              <span className="text-xs text-text-secondary font-mono">API STATUS</span>
              <Badge variant={statusVariant}>
                {health.status.toUpperCase()}
              </Badge>
            </div>
          )}
        </div>
      </div>
    </header>
  );
};
