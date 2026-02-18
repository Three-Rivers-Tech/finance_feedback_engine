import React from 'react';
import { PositionsTable } from '../components/dashboard/PositionsTable';
import { RecentDecisions } from '../components/dashboard/RecentDecisions';

export const PositionsTrades: React.FC = () => {
  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-mono font-bold text-accent-cyan uppercase">Positions & Trades</h1>
      <PositionsTable />
      <RecentDecisions />
    </div>
  );
};
