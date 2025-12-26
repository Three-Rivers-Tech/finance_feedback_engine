import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import {
  formatCurrency,
  formatPercent,
  formatNumber,
  formatDate,
  formatRelativeTime,
  formatUptime,
} from '../formatters';

describe('formatters', () => {
  describe('formatCurrency', () => {
    it('formats positive numbers as USD by default', () => {
      expect(formatCurrency(1000)).toBe('$1,000.00');
    });

    it('formats negative numbers correctly', () => {
      expect(formatCurrency(-500)).toBe('-$500.00');
    });

    it('formats zero correctly', () => {
      expect(formatCurrency(0)).toBe('$0.00');
    });

    it('formats decimal values with 2 decimal places', () => {
      expect(formatCurrency(123.456)).toBe('$123.46');
    });

    it('rounds to 2 decimal places', () => {
      expect(formatCurrency(99.999)).toBe('$100.00');
    });

    it('formats large numbers with commas', () => {
      expect(formatCurrency(1234567.89)).toBe('$1,234,567.89');
    });

    it('formats very small positive numbers', () => {
      expect(formatCurrency(0.01)).toBe('$0.01');
    });

    it('supports custom currency codes', () => {
      const result = formatCurrency(1000, 'EUR');
      expect(result).toContain('1,000.00');
    });

    it('handles very large numbers', () => {
      expect(formatCurrency(999999999.99)).toBe('$999,999,999.99');
    });

    it('formats negative decimals', () => {
      expect(formatCurrency(-123.45)).toBe('-$123.45');
    });
  });

  describe('formatPercent', () => {
    it('formats decimal to percentage with + sign for positive values', () => {
      expect(formatPercent(0.05)).toBe('+5.00%');
    });

    it('formats negative decimal without extra sign', () => {
      expect(formatPercent(-0.03)).toBe('-3.00%');
    });

    it('formats zero with + sign', () => {
      expect(formatPercent(0)).toBe('+0.00%');
    });

    it('formats small positive percentages', () => {
      expect(formatPercent(0.0011)).toBe('+0.11%');
    });

    it('formats with custom decimal places', () => {
      expect(formatPercent(0.12345, 3)).toBe('+12.345%');
    });

    it('formats with 0 decimal places', () => {
      expect(formatPercent(0.1234, 0)).toBe('+12%');
    });

    it('formats large percentages', () => {
      expect(formatPercent(1.5)).toBe('+150.00%');
    });

    it('formats very small negative percentages', () => {
      expect(formatPercent(-0.0001)).toBe('-0.01%');
    });

    it('handles 1 decimal place', () => {
      expect(formatPercent(0.123, 1)).toBe('+12.3%');
    });

    it('formats exactly 1 (100%)', () => {
      expect(formatPercent(1.0)).toBe('+100.00%');
    });

    it('formats exactly -1 (-100%)', () => {
      expect(formatPercent(-1.0)).toBe('-100.00%');
    });
  });

  describe('formatNumber', () => {
    it('formats number with 2 decimal places by default', () => {
      expect(formatNumber(123.456)).toBe('123.46');
    });

    it('formats integer with 2 decimal places', () => {
      expect(formatNumber(100)).toBe('100.00');
    });

    it('formats with custom decimal places', () => {
      expect(formatNumber(123.456789, 4)).toBe('123.4568');
    });

    it('formats with 0 decimal places', () => {
      expect(formatNumber(123.456, 0)).toBe('123');
    });

    it('formats negative numbers', () => {
      expect(formatNumber(-456.789)).toBe('-456.79');
    });

    it('formats zero', () => {
      expect(formatNumber(0)).toBe('0.00');
    });

    it('rounds correctly using toFixed', () => {
      // JavaScript toFixed rounds half away from zero
      expect(formatNumber(1.555, 2)).toBe('1.55');
      expect(formatNumber(1.565, 2)).toBe('1.56');
    });

    it('rounds down correctly', () => {
      expect(formatNumber(1.554, 2)).toBe('1.55');
    });

    it('formats very small numbers', () => {
      expect(formatNumber(0.00123, 5)).toBe('0.00123');
    });

    it('formats very large numbers', () => {
      expect(formatNumber(9999999.99)).toBe('9999999.99');
    });
  });

  describe('formatDate', () => {
    it('formats Date object correctly', () => {
      const date = new Date('2024-01-15T14:30:45');
      const result = formatDate(date);
      expect(result).toMatch(/Jan 15, 2024 \d{2}:\d{2}:\d{2}/);
    });

    it('formats date string correctly', () => {
      const dateString = '2024-12-25T09:15:30';
      const result = formatDate(dateString);
      expect(result).toMatch(/Dec 25, 2024 \d{2}:\d{2}:\d{2}/);
    });

    it('includes time in the format', () => {
      const date = new Date('2024-03-20T23:59:59');
      const result = formatDate(date);
      expect(result).toContain('23:59:59');
    });

    it('formats January correctly', () => {
      const date = new Date('2024-01-01T00:00:00');
      const result = formatDate(date);
      expect(result).toContain('Jan 01, 2024');
    });

    it('formats December correctly', () => {
      const date = new Date('2024-12-31T23:59:59');
      const result = formatDate(date);
      expect(result).toContain('Dec 31, 2024');
    });
  });

  describe('formatRelativeTime', () => {
    beforeEach(() => {
      // Mock current time to 2024-01-01 12:00:00
      vi.useFakeTimers();
      vi.setSystemTime(new Date('2024-01-01T12:00:00'));
    });

    afterEach(() => {
      vi.useRealTimers();
    });

    it('returns "Just now" for times less than 1 minute ago', () => {
      const date = new Date('2024-01-01T11:59:30'); // 30 seconds ago
      expect(formatRelativeTime(date)).toBe('Just now');
    });

    it('returns minutes for times less than 1 hour ago', () => {
      const date = new Date('2024-01-01T11:45:00'); // 15 minutes ago
      expect(formatRelativeTime(date)).toBe('15m ago');
    });

    it('returns hours for times less than 24 hours ago', () => {
      const date = new Date('2024-01-01T08:00:00'); // 4 hours ago
      expect(formatRelativeTime(date)).toBe('4h ago');
    });

    it('returns days for times 24 hours or more ago', () => {
      const date = new Date('2023-12-30T12:00:00'); // 2 days ago
      expect(formatRelativeTime(date)).toBe('2d ago');
    });

    it('handles exactly 1 minute ago', () => {
      const date = new Date('2024-01-01T11:59:00');
      expect(formatRelativeTime(date)).toBe('1m ago');
    });

    it('handles exactly 1 hour ago', () => {
      const date = new Date('2024-01-01T11:00:00');
      expect(formatRelativeTime(date)).toBe('1h ago');
    });

    it('handles exactly 24 hours ago', () => {
      const date = new Date('2023-12-31T12:00:00');
      expect(formatRelativeTime(date)).toBe('1d ago');
    });

    it('handles date strings', () => {
      const dateString = '2024-01-01T11:50:00';
      expect(formatRelativeTime(dateString)).toBe('10m ago');
    });

    it('handles very recent times (seconds)', () => {
      const date = new Date('2024-01-01T11:59:59');
      expect(formatRelativeTime(date)).toBe('Just now');
    });

    it('handles multiple days ago', () => {
      const date = new Date('2023-12-20T12:00:00'); // 12 days ago
      expect(formatRelativeTime(date)).toBe('12d ago');
    });
  });

  describe('formatUptime', () => {
    it('formats seconds only when less than 1 minute', () => {
      expect(formatUptime(45)).toBe('45s');
    });

    it('formats minutes and seconds when less than 1 hour', () => {
      expect(formatUptime(125)).toBe('2m 5s'); // 2 minutes 5 seconds
    });

    it('formats hours and minutes when 1 hour or more', () => {
      expect(formatUptime(3665)).toBe('1h 1m'); // 1 hour 1 minute 5 seconds
    });

    it('formats exactly 1 minute', () => {
      expect(formatUptime(60)).toBe('1m 0s');
    });

    it('formats exactly 1 hour', () => {
      expect(formatUptime(3600)).toBe('1h 0m');
    });

    it('formats zero seconds', () => {
      expect(formatUptime(0)).toBe('0s');
    });

    it('formats large uptime values', () => {
      expect(formatUptime(86400)).toBe('24h 0m'); // 24 hours
    });

    it('formats complex uptime', () => {
      expect(formatUptime(7384)).toBe('2h 3m'); // 2h 3m 4s
    });

    it('handles exactly 30 seconds', () => {
      expect(formatUptime(30)).toBe('30s');
    });

    it('handles 59 seconds', () => {
      expect(formatUptime(59)).toBe('59s');
    });

    it('handles 59 minutes 59 seconds', () => {
      expect(formatUptime(3599)).toBe('59m 59s');
    });

    it('handles multiple hours', () => {
      expect(formatUptime(10800)).toBe('3h 0m'); // 3 hours
    });

    it('handles very large uptime (days worth)', () => {
      expect(formatUptime(259200)).toBe('72h 0m'); // 3 days in hours
    });
  });

  describe('edge cases and integration', () => {
    it('formatCurrency handles NaN gracefully', () => {
      const result = formatCurrency(NaN);
      expect(result).toBe('$NaN');
    });

    it('formatPercent handles very precise decimals', () => {
      expect(formatPercent(0.123456789, 6)).toBe('+12.345679%');
    });

    it('formatNumber handles scientific notation', () => {
      expect(formatNumber(1e-10, 15)).toBe('0.000000000100000');
    });

    it('formatDate handles ISO 8601 strings', () => {
      const result = formatDate('2024-06-15T18:30:00Z');
      expect(result).toMatch(/Jun 15, 2024/);
    });

    it('all formatters handle their inputs consistently', () => {
      // Verify type safety by ensuring formatters work with valid inputs
      expect(() => formatCurrency(100)).not.toThrow();
      expect(() => formatPercent(0.5)).not.toThrow();
      expect(() => formatNumber(42)).not.toThrow();
      expect(() => formatDate(new Date())).not.toThrow();
      expect(() => formatRelativeTime(new Date())).not.toThrow();
      expect(() => formatUptime(3600)).not.toThrow();
    });
  });
});
