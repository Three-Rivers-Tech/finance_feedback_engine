import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { Button } from '../Button';

describe('Button', () => {
  describe('rendering', () => {
    it('renders children content', () => {
      render(<Button>Click Me</Button>);
      expect(screen.getByText('Click Me')).toBeInTheDocument();
    });

    it('renders as a button element', () => {
      render(<Button>Test</Button>);
      expect(screen.getByRole('button')).toBeInTheDocument();
    });
  });

  describe('variants', () => {
    it('applies primary variant by default', () => {
      render(<Button>Primary</Button>);
      const button = screen.getByRole('button');
      expect(button).toHaveClass(
        'bg-accent-cyan',
        'text-bg-primary',
        'border-accent-cyan'
      );
    });

    it('applies primary variant classes explicitly', () => {
      render(<Button variant="primary">Primary</Button>);
      const button = screen.getByRole('button');
      expect(button).toHaveClass(
        'bg-accent-cyan',
        'text-bg-primary',
        'border-accent-cyan',
        'hover:bg-transparent',
        'hover:text-accent-cyan'
      );
    });

    it('applies danger variant classes', () => {
      render(<Button variant="danger">Danger</Button>);
      const button = screen.getByRole('button');
      expect(button).toHaveClass(
        'bg-accent-red',
        'text-white',
        'border-accent-red',
        'hover:bg-transparent',
        'hover:text-accent-red'
      );
    });

    it('applies secondary variant classes', () => {
      render(<Button variant="secondary">Secondary</Button>);
      const button = screen.getByRole('button');
      expect(button).toHaveClass(
        'bg-transparent',
        'text-text-primary',
        'border-border-primary',
        'hover:border-accent-cyan',
        'hover:text-accent-cyan'
      );
    });
  });

  describe('button types', () => {
    it('defaults to button type', () => {
      render(<Button>Default</Button>);
      const button = screen.getByRole('button');
      expect(button).toHaveAttribute('type', 'button');
    });

    it('applies submit type when specified', () => {
      render(<Button type="submit">Submit</Button>);
      const button = screen.getByRole('button');
      expect(button).toHaveAttribute('type', 'submit');
    });

    it('applies reset type when specified', () => {
      render(<Button type="reset">Reset</Button>);
      const button = screen.getByRole('button');
      expect(button).toHaveAttribute('type', 'reset');
    });
  });

  describe('disabled state', () => {
    it('is not disabled by default', () => {
      render(<Button>Enabled</Button>);
      const button = screen.getByRole('button');
      expect(button).not.toBeDisabled();
    });

    it('applies disabled attribute when disabled prop is true', () => {
      render(<Button disabled>Disabled</Button>);
      const button = screen.getByRole('button');
      expect(button).toBeDisabled();
    });

    it('applies disabled opacity classes when disabled', () => {
      render(<Button disabled>Disabled</Button>);
      const button = screen.getByRole('button');
      expect(button).toHaveClass('disabled:opacity-50', 'disabled:cursor-not-allowed');
    });

    it('does not call onClick when disabled', () => {
      const handleClick = vi.fn();
      render(
        <Button disabled onClick={handleClick}>
          Disabled
        </Button>
      );
      const button = screen.getByRole('button');
      fireEvent.click(button);
      expect(handleClick).not.toHaveBeenCalled();
    });
  });

  describe('click handling', () => {
    it('calls onClick handler when clicked', () => {
      const handleClick = vi.fn();
      render(<Button onClick={handleClick}>Click Me</Button>);
      const button = screen.getByRole('button');
      fireEvent.click(button);
      expect(handleClick).toHaveBeenCalledTimes(1);
    });

    it('calls onClick multiple times when clicked multiple times', () => {
      const handleClick = vi.fn();
      render(<Button onClick={handleClick}>Click Me</Button>);
      const button = screen.getByRole('button');
      fireEvent.click(button);
      fireEvent.click(button);
      fireEvent.click(button);
      expect(handleClick).toHaveBeenCalledTimes(3);
    });

    it('works without onClick handler', () => {
      render(<Button>No Handler</Button>);
      const button = screen.getByRole('button');
      expect(() => fireEvent.click(button)).not.toThrow();
    });
  });

  describe('styling', () => {
    it('applies base classes for all buttons', () => {
      render(<Button>Test</Button>);
      const button = screen.getByRole('button');
      expect(button).toHaveClass(
        'px-6',
        'py-3',
        'font-mono',
        'text-sm',
        'uppercase',
        'border-3',
        'transition-colors'
      );
    });

    it('applies custom className when provided', () => {
      render(<Button className="custom-class">Test</Button>);
      const button = screen.getByRole('button');
      expect(button).toHaveClass('custom-class');
    });

    it('combines custom className with variant classes', () => {
      render(
        <Button variant="danger" className="extra-padding">
          Test
        </Button>
      );
      const button = screen.getByRole('button');
      expect(button).toHaveClass('bg-accent-red', 'extra-padding');
    });
  });

  describe('accessibility', () => {
    it('is keyboard accessible', () => {
      const handleClick = vi.fn();
      render(<Button onClick={handleClick}>Accessible</Button>);
      const button = screen.getByRole('button');
      button.focus();
      expect(button).toHaveFocus();
    });
  });

  describe('content', () => {
    it('renders text content', () => {
      render(<Button>Text Content</Button>);
      expect(screen.getByText('Text Content')).toBeInTheDocument();
    });

    it('renders numeric content', () => {
      render(<Button>{42}</Button>);
      expect(screen.getByText('42')).toBeInTheDocument();
    });

    it('renders complex children', () => {
      render(
        <Button>
          <span>Icon</span>
          <span>Label</span>
        </Button>
      );
      expect(screen.getByText('Icon')).toBeInTheDocument();
      expect(screen.getByText('Label')).toBeInTheDocument();
    });
  });
});
