import React from 'react';
import type { Position } from '../../api/types';
import { usePortfolio } from '../../api/hooks/usePortfolio';
import { usePositions } from '../../api/hooks/usePositions';
import { MetricCard } from '../common/MetricCard';
import { Spinner } from '../common/Spinner';
import { formatCurrency } from '../../services/formatters';

export const PortfolioOverview: React.FC = () => {
  const { data: portfolio, isLoading: portfolioLoading } = usePortfolio();
  const { data: positionsData, isLoading: positionsLoading } = usePositions();
  const positions: Position[] = positionsData ?? [];

  if (portfolioLoading || positionsLoading) {
    return <Spinner />;
  }

  const totalPnL = (Array.isArray(positions) ? positions : []).reduce((sum, pos) => sum + pos.unrealized_pnl, 0) || 0;
  const totalPnLPct = portfolio?.balance?.total
    ? (totalPnL / portfolio.balance.total) * 100
    : 0;

  return (
    <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
      <MetricCard
        label="Portfolio Value"
        value={formatCurrency(portfolio?.balance?.total || 0, portfolio?.balance?.currency)}
        status="neutral"
      />
      <MetricCard
        label="Unrealized P&L"
        value={formatCurrency(totalPnL)}
        change={totalPnLPct}
        status={totalPnL >= 0 ? 'positive' : 'negative'}
      />
      <MetricCard
        label="Active Positions"
        value={positions && positions.length ? positions.length : 0}
        suffix={`/ ${portfolio?.max_concurrent_trades || 2}`}
        status="neutral"
      />
    </div>
  );
};
