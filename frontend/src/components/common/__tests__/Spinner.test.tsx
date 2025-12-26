import { describe, it, expect } from 'vitest';
import { render } from '@testing-library/react';
import { Spinner } from '../Spinner';

describe('Spinner', () => {
  describe('rendering', () => {
    it('renders a spinner element', () => {
      const { container } = render(<Spinner />);
      const spinner = container.querySelector('.animate-spin');
      expect(spinner).toBeInTheDocument();
    });

    it('renders within a flex container', () => {
      const { container } = render(<Spinner />);
      const flexContainer = container.querySelector('.flex');
      expect(flexContainer).toBeInTheDocument();
      expect(flexContainer).toHaveClass('items-center', 'justify-center');
    });
  });

  describe('sizes', () => {
    it('renders medium size by default', () => {
      const { container } = render(<Spinner />);
      const spinner = container.querySelector('.animate-spin');
      expect(spinner).toHaveClass('w-8', 'h-8', 'border-3');
    });

    it('renders small size when specified', () => {
      const { container } = render(<Spinner size="sm" />);
      const spinner = container.querySelector('.animate-spin');
      expect(spinner).toHaveClass('w-4', 'h-4', 'border-2');
    });

    it('renders medium size when explicitly specified', () => {
      const { container } = render(<Spinner size="md" />);
      const spinner = container.querySelector('.animate-spin');
      expect(spinner).toHaveClass('w-8', 'h-8', 'border-3');
    });

    it('renders large size when specified', () => {
      const { container } = render(<Spinner size="lg" />);
      const spinner = container.querySelector('.animate-spin');
      expect(spinner).toHaveClass('w-12', 'h-12', 'border-3');
    });
  });

  describe('styling', () => {
    it('applies border styling for all sizes', () => {
      const { container } = render(<Spinner />);
      const spinner = container.querySelector('.animate-spin');
      expect(spinner).toHaveClass('border-border-primary', 'border-t-accent-cyan');
    });

    it('applies animation class', () => {
      const { container } = render(<Spinner />);
      const spinner = container.querySelector('.animate-spin');
      expect(spinner).toHaveClass('animate-spin');
    });

    it('maintains consistent border colors across sizes', () => {
      const sizes: Array<'sm' | 'md' | 'lg'> = ['sm', 'md', 'lg'];

      sizes.forEach((size) => {
        const { container } = render(<Spinner size={size} />);
        const spinner = container.querySelector('.animate-spin');
        expect(spinner).toHaveClass('border-border-primary', 'border-t-accent-cyan');
      });
    });
  });

  describe('structure', () => {
    it('has correct DOM structure with outer and inner divs', () => {
      const { container } = render(<Spinner />);
      const outerDiv = container.firstChild;
      const innerDiv = outerDiv?.firstChild;

      expect(outerDiv).toHaveClass('flex', 'items-center', 'justify-center');
      expect(innerDiv).toHaveClass('animate-spin');
    });

    it('renders only necessary DOM elements', () => {
      const { container } = render(<Spinner />);
      const allDivs = container.querySelectorAll('div');
      expect(allDivs).toHaveLength(2); // outer container + spinner
    });
  });

  describe('visual appearance', () => {
    it('small spinner has correct dimensions', () => {
      const { container } = render(<Spinner size="sm" />);
      const spinner = container.querySelector('.animate-spin');
      expect(spinner).toHaveClass('w-4', 'h-4');
    });

    it('medium spinner has correct dimensions', () => {
      const { container } = render(<Spinner size="md" />);
      const spinner = container.querySelector('.animate-spin');
      expect(spinner).toHaveClass('w-8', 'h-8');
    });

    it('large spinner has correct dimensions', () => {
      const { container } = render(<Spinner size="lg" />);
      const spinner = container.querySelector('.animate-spin');
      expect(spinner).toHaveClass('w-12', 'h-12');
    });
  });

  describe('accessibility', () => {
    it('renders a visible loading indicator', () => {
      const { container } = render(<Spinner />);
      const spinner = container.querySelector('.animate-spin');
      expect(spinner).toBeInTheDocument();
      expect(spinner).toBeVisible();
    });
  });

  describe('consistency', () => {
    it('renders the same spinner on multiple renders', () => {
      const { container: container1 } = render(<Spinner />);
      const { container: container2 } = render(<Spinner />);

      const spinner1 = container1.querySelector('.animate-spin');
      const spinner2 = container2.querySelector('.animate-spin');

      expect(spinner1?.className).toBe(spinner2?.className);
    });

    it('maintains size classes correctly for all sizes', () => {
      const testCases: Array<{
        size: 'sm' | 'md' | 'lg';
        expectedClasses: { width: string; height: string; border: string };
      }> = [
        { size: 'sm', expectedClasses: { width: 'w-4', height: 'h-4', border: 'border-2' } },
        { size: 'md', expectedClasses: { width: 'w-8', height: 'h-8', border: 'border-3' } },
        { size: 'lg', expectedClasses: { width: 'w-12', height: 'h-12', border: 'border-3' } },
      ];

      testCases.forEach(({ size, expectedClasses }) => {
        const { container } = render(<Spinner size={size} />);
        const spinner = container.querySelector('.animate-spin');

        expect(spinner).toHaveClass(
          expectedClasses.width,
          expectedClasses.height,
          expectedClasses.border
        );
      });
    });
  });
});
