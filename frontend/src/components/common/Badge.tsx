import React from 'react';

type BadgeVariant = 'success' | 'danger' | 'warning' | 'info' | 'neutral';

interface BadgeProps {
  children: React.ReactNode;
  variant?: BadgeVariant;
  className?: string;
}

export const Badge: React.FC<BadgeProps> = ({
  children,
  variant = 'neutral',
  className = '',
}) => {
  const variantClasses = {
    success: 'bg-accent-green text-bg-primary',
    danger: 'bg-accent-red text-white',
    warning: 'bg-accent-amber text-bg-primary',
    info: 'bg-accent-cyan text-bg-primary',
    neutral: 'bg-bg-tertiary text-text-primary',
  };

  return (
    <span
      className={`inline-block px-3 py-1 text-xs font-mono uppercase ${variantClasses[variant]} ${className}`}
    >
      {children}
    </span>
  );
};
