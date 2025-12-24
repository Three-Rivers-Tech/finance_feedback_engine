import React from 'react';

interface CardProps {
  children: React.ReactNode;
  className?: string;
}

export const Card: React.FC<CardProps> = ({ children, className = '' }) => {
  return (
    <div className={`bg-bg-secondary border-3 border-border-primary p-6 ${className}`}>
      {children}
    </div>
  );
};
