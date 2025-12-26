import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { Card } from '../Card';

describe('Card', () => {
  describe('rendering', () => {
    it('renders children content', () => {
      render(<Card>Card Content</Card>);
      expect(screen.getByText('Card Content')).toBeInTheDocument();
    });

    it('renders as a div element', () => {
      const { container } = render(<Card>Test</Card>);
      expect(container.querySelector('div')).toBeInTheDocument();
    });
  });

  describe('styling', () => {
    it('applies base card classes', () => {
      const { container } = render(<Card>Test</Card>);
      const card = container.querySelector('div');
      expect(card).toHaveClass(
        'bg-bg-secondary',
        'border-3',
        'border-border-primary',
        'p-6'
      );
    });

    it('applies custom className when provided', () => {
      const { container } = render(
        <Card className="custom-class">Test</Card>
      );
      const card = container.querySelector('div');
      expect(card).toHaveClass('custom-class');
    });

    it('combines custom className with base classes', () => {
      const { container } = render(
        <Card className="extra-margin shadow-lg">Test</Card>
      );
      const card = container.querySelector('div');
      expect(card).toHaveClass('bg-bg-secondary', 'extra-margin', 'shadow-lg');
    });

    it('applies empty className by default', () => {
      const { container } = render(<Card>Test</Card>);
      const card = container.querySelector('div');
      const classes = card?.className || '';
      expect(classes).not.toContain('undefined');
      expect(classes).not.toContain('null');
    });
  });

  describe('content', () => {
    it('renders simple text content', () => {
      render(<Card>Simple Text</Card>);
      expect(screen.getByText('Simple Text')).toBeInTheDocument();
    });

    it('renders numeric content', () => {
      render(<Card>{123}</Card>);
      expect(screen.getByText('123')).toBeInTheDocument();
    });

    it('renders multiple children', () => {
      render(
        <Card>
          <h1>Title</h1>
          <p>Paragraph</p>
          <button>Button</button>
        </Card>
      );
      expect(screen.getByText('Title')).toBeInTheDocument();
      expect(screen.getByText('Paragraph')).toBeInTheDocument();
      expect(screen.getByText('Button')).toBeInTheDocument();
    });

    it('renders nested components', () => {
      render(
        <Card>
          <div>
            <span>Nested</span>
          </div>
        </Card>
      );
      expect(screen.getByText('Nested')).toBeInTheDocument();
    });

    it('renders complex content with various elements', () => {
      render(
        <Card>
          <header>Header</header>
          <section>Section Content</section>
          <footer>Footer</footer>
        </Card>
      );
      expect(screen.getByText('Header')).toBeInTheDocument();
      expect(screen.getByText('Section Content')).toBeInTheDocument();
      expect(screen.getByText('Footer')).toBeInTheDocument();
    });

    it('handles empty content', () => {
      const { container } = render(<Card>{''}</Card>);
      const card = container.querySelector('div');
      expect(card).toBeInTheDocument();
      expect(card?.textContent).toBe('');
    });

    it('renders React fragments as children', () => {
      render(
        <Card>
          <>
            <span>Fragment 1</span>
            <span>Fragment 2</span>
          </>
        </Card>
      );
      expect(screen.getByText('Fragment 1')).toBeInTheDocument();
      expect(screen.getByText('Fragment 2')).toBeInTheDocument();
    });
  });

  describe('composition', () => {
    it('can be used as a container for other cards', () => {
      render(
        <Card className="outer">
          <Card className="inner">Inner Card</Card>
        </Card>
      );
      expect(screen.getByText('Inner Card')).toBeInTheDocument();
    });

    it('maintains proper nesting structure', () => {
      const { container } = render(
        <Card className="parent">
          <Card className="child">Child</Card>
        </Card>
      );
      const parent = container.querySelector('.parent');
      const child = container.querySelector('.child');
      expect(parent).toContainElement(child as HTMLElement);
    });
  });
});
