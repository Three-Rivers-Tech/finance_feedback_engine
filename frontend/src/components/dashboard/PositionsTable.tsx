import React from 'react';
import { usePositions } from '../../api/hooks/usePositions';
import { Card } from '../common/Card';
import { Spinner } from '../common/Spinner';
import { Badge } from '../common/Badge';
import { formatCurrency, formatPercent } from '../../services/formatters';

export const PositionsTable: React.FC = () => {
  const { data: positions, isLoading, error } = usePositions();

  if (isLoading) {
    return (
      <Card>
        <Spinner />
      </Card>
    );
  }

  if (error) {
    // Check if it's an auth error
    const isAuthError = error.message?.includes('401') || error.message?.includes('Unauthorized');
    return (
      <Card>
        <div className="text-center p-4">
          <p className="text-accent-yellow font-mono mb-2">
            {isAuthError ? '🔐 Authentication Required' : '⚠️ Error Loading Positions'}
          </p>
          <p className="text-text-secondary text-sm font-mono">
            {isAuthError
              ? 'API key required. Set VITE_API_KEY in frontend/.env file.'
              : error.message}
          </p>
        </div>
      </Card>
    );
  }

  if (!positions || positions.length === 0) {
    return (
      <Card>
        <p className="text-center text-text-secondary font-mono">No active positions</p>
      </Card>
    );
  }

  return (
    <Card>
      <h2 className="text-lg font-mono font-bold text-accent-cyan mb-4 uppercase">
        Active Positions
      </h2>
      <div className="overflow-x-auto">
        <table className="w-full font-mono text-sm">
          <thead>
            <tr className="border-b-3 border-border-primary">
              <th className="text-left py-3 px-2 text-text-secondary uppercase">Pair</th>
              <th className="text-left py-3 px-2 text-text-secondary uppercase">Side</th>
              <th className="text-right py-3 px-2 text-text-secondary uppercase">Size</th>
              <th className="text-right py-3 px-2 text-text-secondary uppercase">Entry</th>
              <th className="text-right py-3 px-2 text-text-secondary uppercase">Current</th>
              <th className="text-right py-3 px-2 text-text-secondary uppercase">P&L</th>
              <th className="text-right py-3 px-2 text-text-secondary uppercase">P&L %</th>
            </tr>
          </thead>
          <tbody>
            {positions.map((position) => (
              <tr
                key={position.id}
                className="border-b border-border-primary hover:bg-bg-tertiary transition-colors"
              >
                <td className="py-3 px-2">{position.asset_pair}</td>
                <td className="py-3 px-2">
                  <Badge variant={position.side === 'LONG' ? 'success' : 'danger'}>
                    {position.side}
                  </Badge>
                </td>
                <td className="text-right py-3 px-2">{position.size}</td>
                <td className="text-right py-3 px-2">{formatCurrency(position.entry_price)}</td>
                <td className="text-right py-3 px-2">{formatCurrency(position.current_price)}</td>
                <td
                  className={`text-right py-3 px-2 font-bold ${
                    position.unrealized_pnl >= 0 ? 'text-accent-green' : 'text-accent-red'
                  }`}
                >
                  {formatCurrency(position.unrealized_pnl)}
                </td>
                <td
                  className={`text-right py-3 px-2 font-bold ${
                    position.unrealized_pnl_pct >= 0 ? 'text-accent-green' : 'text-accent-red'
                  }`}
                >
                  {formatPercent(position.unrealized_pnl_pct)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Card>
  );
};
