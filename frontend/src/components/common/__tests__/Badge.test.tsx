import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { Badge } from '../Badge';

describe('Badge', () => {
  describe('rendering', () => {
    it('renders children content', () => {
      render(<Badge>Test Badge</Badge>);
      expect(screen.getByText('Test Badge')).toBeInTheDocument();
    });

    it('renders as a span element', () => {
      const { container } = render(<Badge>Test</Badge>);
      expect(container.querySelector('span')).toBeInTheDocument();
    });
  });

  describe('variants', () => {
    it('applies neutral variant by default', () => {
      const { container } = render(<Badge>Default</Badge>);
      const badge = container.querySelector('span');
      expect(badge).toHaveClass('bg-bg-tertiary', 'text-text-primary');
    });

    it('applies success variant classes', () => {
      const { container } = render(<Badge variant="success">Success</Badge>);
      const badge = container.querySelector('span');
      expect(badge).toHaveClass('bg-accent-green', 'text-bg-primary');
    });

    it('applies danger variant classes', () => {
      const { container } = render(<Badge variant="danger">Danger</Badge>);
      const badge = container.querySelector('span');
      expect(badge).toHaveClass('bg-accent-red', 'text-white');
    });

    it('applies warning variant classes', () => {
      const { container } = render(<Badge variant="warning">Warning</Badge>);
      const badge = container.querySelector('span');
      expect(badge).toHaveClass('bg-accent-amber', 'text-bg-primary');
    });

    it('applies info variant classes', () => {
      const { container } = render(<Badge variant="info">Info</Badge>);
      const badge = container.querySelector('span');
      expect(badge).toHaveClass('bg-accent-cyan', 'text-bg-primary');
    });
  });

  describe('styling', () => {
    it('applies base classes for all badges', () => {
      const { container } = render(<Badge>Test</Badge>);
      const badge = container.querySelector('span');
      expect(badge).toHaveClass(
        'inline-block',
        'px-3',
        'py-1',
        'text-xs',
        'font-mono',
        'uppercase'
      );
    });

    it('applies custom className when provided', () => {
      const { container } = render(
        <Badge className="custom-class">Test</Badge>
      );
      const badge = container.querySelector('span');
      expect(badge).toHaveClass('custom-class');
    });

    it('combines custom className with variant classes', () => {
      const { container } = render(
        <Badge variant="success" className="extra-margin">
          Test
        </Badge>
      );
      const badge = container.querySelector('span');
      expect(badge).toHaveClass('bg-accent-green', 'extra-margin');
    });
  });

  describe('content', () => {
    it('renders text content', () => {
      render(<Badge>Text Content</Badge>);
      expect(screen.getByText('Text Content')).toBeInTheDocument();
    });

    it('renders numeric content', () => {
      render(<Badge>{42}</Badge>);
      expect(screen.getByText('42')).toBeInTheDocument();
    });

    it('renders multiple children', () => {
      render(
        <Badge>
          <span>First</span>
          <span>Second</span>
        </Badge>
      );
      expect(screen.getByText('First')).toBeInTheDocument();
      expect(screen.getByText('Second')).toBeInTheDocument();
    });

    it('renders empty badge when children is empty string', () => {
      const { container } = render(<Badge>{''}</Badge>);
      const badge = container.querySelector('span');
      expect(badge).toBeInTheDocument();
      expect(badge?.textContent).toBe('');
    });
  });
});
