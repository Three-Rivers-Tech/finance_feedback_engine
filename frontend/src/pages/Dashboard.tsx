import React from 'react';
import { PortfolioOverview } from '../components/dashboard/PortfolioOverview';
import { PositionsTable } from '../components/dashboard/PositionsTable';
import { RecentDecisions } from '../components/dashboard/RecentDecisions';
import { OllamaStatusAlert } from '../components/common/OllamaStatusAlert';
import { useHealth } from '../api/hooks/useHealth';

export const Dashboard: React.FC = () => {
  const { data: health, isLoading } = useHealth();

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-mono font-bold text-accent-cyan uppercase">
        Dashboard
      </h1>

      {/* Show Ollama status alert if there are issues */}
      {!isLoading && health?.components?.ollama && (
        <OllamaStatusAlert ollama={health.components.ollama} />
      )}

      <PortfolioOverview />
      <PositionsTable />
      <RecentDecisions />
    </div>
  );
};
