import React from 'react';
import { PortfolioOverview } from '../components/dashboard/PortfolioOverview';
import { PositionsTable } from '../components/dashboard/PositionsTable';
import { RecentDecisions } from '../components/dashboard/RecentDecisions';

export const Dashboard: React.FC = () => {
  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-mono font-bold text-accent-cyan uppercase">
        Dashboard
      </h1>
      <PortfolioOverview />
      <PositionsTable />
      <RecentDecisions />
    </div>
  );
};
