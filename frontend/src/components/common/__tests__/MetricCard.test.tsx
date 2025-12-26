import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MetricCard } from '../MetricCard';

describe('MetricCard', () => {
  describe('rendering', () => {
    it('renders label and value', () => {
      render(<MetricCard label="Total Balance" value="$10,000" />);
      expect(screen.getByText('Total Balance')).toBeInTheDocument();
      expect(screen.getByText('$10,000')).toBeInTheDocument();
    });

    it('renders numeric value', () => {
      render(<MetricCard label="Count" value={42} />);
      expect(screen.getByText('Count')).toBeInTheDocument();
      expect(screen.getByText('42')).toBeInTheDocument();
    });

    it('uses Card component as container', () => {
      const { container } = render(<MetricCard label="Test" value="123" />);
      const card = container.querySelector('.bg-bg-secondary');
      expect(card).toBeInTheDocument();
    });
  });

  describe('label styling', () => {
    it('applies correct label classes', () => {
      render(<MetricCard label="Test Label" value="Value" />);
      const label = screen.getByText('Test Label');
      expect(label).toHaveClass(
        'text-text-secondary',
        'text-xs',
        'uppercase',
        'tracking-wider',
        'font-mono'
      );
    });
  });

  describe('value styling', () => {
    it('applies default neutral status color', () => {
      const { container } = render(<MetricCard label="Test" value="100" />);
      const valueDiv = container.querySelector('.text-3xl');
      expect(valueDiv).toHaveClass('text-text-primary');
    });

    it('applies positive status color', () => {
      const { container } = render(<MetricCard label="Test" value="100" status="positive" />);
      const valueDiv = container.querySelector('.text-3xl');
      expect(valueDiv).toHaveClass('text-accent-green');
    });

    it('applies negative status color', () => {
      const { container } = render(<MetricCard label="Test" value="100" status="negative" />);
      const valueDiv = container.querySelector('.text-3xl');
      expect(valueDiv).toHaveClass('text-accent-red');
    });

    it('applies value base classes', () => {
      const { container } = render(<MetricCard label="Test" value="100" />);
      const valueDiv = container.querySelector('.text-3xl');
      expect(valueDiv).toHaveClass('text-3xl', 'font-mono', 'font-bold');
    });
  });

  describe('suffix', () => {
    it('renders suffix when provided', () => {
      render(<MetricCard label="Test" value="100" suffix="USD" />);
      expect(screen.getByText('USD')).toBeInTheDocument();
    });

    it('does not render suffix when not provided', () => {
      render(<MetricCard label="Test" value="100" />);
      expect(document.querySelector('.text-xl')).not.toBeInTheDocument();
    });

    it('applies correct suffix styling', () => {
      render(<MetricCard label="Test" value="100" suffix="%" />);
      const suffix = screen.getByText('%');
      expect(suffix).toHaveClass('text-xl', 'ml-1');
    });

    it('renders suffix with value', () => {
      render(<MetricCard label="Test" value="100" suffix="kg" />);
      const valueContainer = screen.getByText('100').parentElement;
      expect(valueContainer).toContainElement(screen.getByText('kg'));
    });
  });

  describe('change percentage', () => {
    it('renders positive change with plus sign', () => {
      render(<MetricCard label="Test" value="100" change={15.5} />);
      expect(screen.getByText('+15.50%')).toBeInTheDocument();
    });

    it('renders negative change without plus sign', () => {
      render(<MetricCard label="Test" value="100" change={-8.25} />);
      expect(screen.getByText('-8.25%')).toBeInTheDocument();
    });

    it('renders zero change with plus sign', () => {
      render(<MetricCard label="Test" value="100" change={0} />);
      expect(screen.getByText('+0.00%')).toBeInTheDocument();
    });

    it('applies green color for positive change', () => {
      render(<MetricCard label="Test" value="100" change={10} />);
      const changeElement = screen.getByText('+10.00%');
      expect(changeElement).toHaveClass('text-accent-green');
    });

    it('applies red color for negative change', () => {
      render(<MetricCard label="Test" value="100" change={-10} />);
      const changeElement = screen.getByText('-10.00%');
      expect(changeElement).toHaveClass('text-accent-red');
    });

    it('applies green color for zero change', () => {
      render(<MetricCard label="Test" value="100" change={0} />);
      const changeElement = screen.getByText('+0.00%');
      expect(changeElement).toHaveClass('text-accent-green');
    });

    it('does not render change when undefined', () => {
      const { container } = render(<MetricCard label="Test" value="100" />);
      const changeText = container.textContent?.match(/[+-]\d+\.\d+%/);
      expect(changeText).toBeNull();
    });

    it('formats change to 2 decimal places', () => {
      render(<MetricCard label="Test" value="100" change={5.123456} />);
      expect(screen.getByText('+5.12%')).toBeInTheDocument();
    });

    it('applies correct change styling', () => {
      render(<MetricCard label="Test" value="100" change={10} />);
      const changeElement = screen.getByText('+10.00%');
      expect(changeElement).toHaveClass('text-sm', 'font-mono');
    });
  });

  describe('layout', () => {
    it('uses flex column layout with gap', () => {
      const { container } = render(<MetricCard label="Test" value="100" />);
      const innerContainer = container.querySelector('.flex');
      expect(innerContainer).toHaveClass('flex', 'flex-col', 'gap-2');
    });
  });

  describe('complex scenarios', () => {
    it('renders all props together', () => {
      render(
        <MetricCard
          label="Portfolio Value"
          value="$50,000"
          suffix="USD"
          change={12.5}
          status="positive"
        />
      );
      expect(screen.getByText('Portfolio Value')).toBeInTheDocument();
      expect(screen.getByText('$50,000')).toBeInTheDocument();
      expect(screen.getByText('USD')).toBeInTheDocument();
      expect(screen.getByText('+12.50%')).toBeInTheDocument();
    });

    it('handles negative change with negative status', () => {
      const { container } = render(
        <MetricCard
          label="Loss"
          value="$1,000"
          change={-25}
          status="negative"
        />
      );
      const valueDiv = container.querySelector('.text-3xl');
      const change = screen.getByText('-25.00%');
      expect(valueDiv).toHaveClass('text-accent-red');
      expect(change).toHaveClass('text-accent-red');
    });

    it('renders large numeric values', () => {
      render(<MetricCard label="Big Number" value={1234567890} />);
      expect(screen.getByText('1234567890')).toBeInTheDocument();
    });

    it('renders decimal values', () => {
      render(<MetricCard label="Precise" value={123.456} />);
      expect(screen.getByText('123.456')).toBeInTheDocument();
    });

    it('handles very small changes', () => {
      render(<MetricCard label="Test" value="100" change={0.01} />);
      expect(screen.getByText('+0.01%')).toBeInTheDocument();
    });

    it('handles very large changes', () => {
      render(<MetricCard label="Test" value="100" change={999.99} />);
      expect(screen.getByText('+999.99%')).toBeInTheDocument();
    });
  });

  describe('edge cases', () => {
    it('renders empty string value', () => {
      render(<MetricCard label="Empty" value="" />);
      expect(screen.getByText('Empty')).toBeInTheDocument();
    });

    it('renders zero as value', () => {
      render(<MetricCard label="Zero" value={0} />);
      expect(screen.getByText('0')).toBeInTheDocument();
    });

    it('handles empty suffix gracefully', () => {
      render(<MetricCard label="Test" value="100" suffix="" />);
      expect(screen.getByText('Test')).toBeInTheDocument();
      expect(screen.getByText('100')).toBeInTheDocument();
    });
  });
});
