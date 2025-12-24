import React from 'react';
import { Card } from '../components/common/Card';
import { GRAFANA_URL } from '../utils/constants';

export const Analytics: React.FC = () => {
  const dashboardUrl = `${GRAFANA_URL}/d/ffe-trading-metrics/finance-feedback-engine-trading-metrics?orgId=1&refresh=5s&kiosk`;

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-mono font-bold text-accent-cyan uppercase">
        Performance Analytics
      </h1>
      <Card className="p-0 overflow-hidden">
        <div className="p-4 bg-bg-tertiary border-b-3 border-border-primary">
          <p className="text-sm text-text-secondary font-mono">
            Real-time metrics from Grafana (auto-refresh every 5s)
          </p>
        </div>
        <iframe
          src={dashboardUrl}
          width="100%"
          height="800"
          frameBorder="0"
          title="Trading Metrics Dashboard"
          className="bg-bg-primary"
        />
      </Card>
      <div className="text-sm text-text-muted font-mono">
        <p>💡 Tip: Click "Exit Kiosk Mode" in Grafana to access full dashboard controls</p>
      </div>
    </div>
  );
};
