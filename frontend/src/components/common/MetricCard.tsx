import React from 'react';
import { Card } from './Card';

interface MetricCardProps {
  label: string;
  value: string | number;
  change?: number;
  suffix?: string;
  status?: 'positive' | 'negative' | 'neutral';
}

export const MetricCard: React.FC<MetricCardProps> = ({
  label,
  value,
  change,
  suffix,
  status = 'neutral',
}) => {
  const statusColors = {
    positive: 'text-accent-green',
    negative: 'text-accent-red',
    neutral: 'text-text-primary',
  };

  return (
    <Card className="flex flex-col gap-2">
      <div className="text-text-secondary text-xs uppercase tracking-wider font-mono">
        {label}
      </div>
      <div className={`text-3xl font-mono font-bold ${statusColors[status]}`}>
        {value}
        {suffix && <span className="text-xl ml-1">{suffix}</span>}
      </div>
      {change !== undefined && (
        <div className={`text-sm font-mono ${change >= 0 ? 'text-accent-green' : 'text-accent-red'}`}>
          {change >= 0 ? '+' : ''}{change.toFixed(2)}%
        </div>
      )}
    </Card>
  );
};
