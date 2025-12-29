import React from 'react';

type ButtonVariant = 'primary' | 'danger' | 'secondary';

interface ButtonProps {
  children: React.ReactNode;
  variant?: ButtonVariant;
  onClick?: () => void;
  disabled?: boolean;
  className?: string;
  type?: 'button' | 'submit' | 'reset';
}

export const Button: React.FC<ButtonProps> = ({
  children,
  variant = 'primary',
  onClick,
  disabled,
  className = '',
  type = 'button',
}) => {
  const baseClasses = 'px-6 py-3 font-mono text-sm uppercase border-3 transition-colors disabled:opacity-50 disabled:cursor-not-allowed';

  const variantClasses = {
    primary: 'bg-accent-cyan text-bg-primary border-accent-cyan hover:bg-transparent hover:text-accent-cyan',
    danger: 'bg-accent-red text-white border-accent-red hover:bg-transparent hover:text-accent-red',
    secondary: 'bg-transparent text-text-primary border-border-primary hover:border-accent-cyan hover:text-accent-cyan',
  };

  return (
    <button
      type={type}
      onClick={onClick}
      disabled={disabled}
      className={`${baseClasses} ${variantClasses[variant]} ${className}`}
    >
      {children}
    </button>
  );
};
