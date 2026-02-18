/**
 * Integration test: Backend status endpoint → Frontend AgentStatus type
 */
import { describe, it, expect, beforeAll, afterAll } from 'vitest';
import axios from 'axios';
import type { AxiosInstance } from 'axios';
import type { AgentStatus } from '../types';

const API_BASE_URL = process.env.VITE_API_BASE_URL || 'http://localhost:8000';

describe('Status Endpoint Integration', () => {
  let apiClient: AxiosInstance;

  beforeAll(() => {
    apiClient = axios.create({
      baseURL: API_BASE_URL,
      timeout: 5000,
      headers: {
        'Content-Type': 'application/json',
      },
    });
  });

  afterAll(() => {
    // Cleanup if needed
  });

  it('should fetch status and match AgentStatus interface', async () => {
    // Skip if backend not running (allows tests to run in CI)
    try {
      const response = await apiClient.get<AgentStatus>('/api/v1/bot/status');

      expect(response.status).toBe(200);
      expect(response.data).toBeDefined();

      const status = response.data;

      // Required fields
      expect(status).toHaveProperty('state');
      expect(['stopped', 'starting', 'running', 'stopping', 'error']).toContain(status.state);

      expect(status).toHaveProperty('total_trades');
      expect(typeof status.total_trades).toBe('number');

      expect(status).toHaveProperty('active_positions');
      expect(typeof status.active_positions).toBe('number');

      expect(status).toHaveProperty('config');
      expect(status.config).toHaveProperty('asset_pairs');
      expect(Array.isArray(status.config.asset_pairs)).toBe(true);
      expect(status.config).toHaveProperty('autonomous');
      expect(typeof status.config.autonomous).toBe('boolean');

      // Optional fields - should be present (can be null)
      expect(status).toHaveProperty('agent_ooda_state');
      expect(status).toHaveProperty('uptime_seconds');
      expect(status).toHaveProperty('portfolio_value');
      expect(status).toHaveProperty('daily_pnl');
      expect(status).toHaveProperty('current_asset_pair');
      expect(status).toHaveProperty('last_decision_time');
      expect(status).toHaveProperty('error_message');

      // Verify null-safety for numeric fields
      if (status.portfolio_value !== null) {
        expect(typeof status.portfolio_value).toBe('number');
      }
      if (status.daily_pnl !== null) {
        expect(typeof status.daily_pnl).toBe('number');
      }
      if (status.uptime_seconds !== null) {
        expect(typeof status.uptime_seconds).toBe('number');
      }

      console.log('✓ Status response matches AgentStatus interface');
      console.log(`  State: ${status.state}`);
      console.log(`  Positions: ${status.active_positions}`);
      console.log(`  Trades: ${status.total_trades}`);
      console.log(`  Portfolio: ${status.portfolio_value !== null ? `$${status.portfolio_value.toFixed(2)}` : 'N/A'}`);
    } catch (error) {
      if (axios.isAxiosError(error) && error.code === 'ECONNREFUSED') {
        console.warn('Backend not running - skipping integration test');
        // Don't fail the test if backend is down
        return;
      }
      throw error;
    }
  });

  it('should handle development mode enriched payload', async () => {
    // Skip if backend not running
    try {
      const response = await apiClient.get('/api/v1/bot/status');

      const status = response.data as AgentStatus & {
        balances?: Record<string, number>;
        portfolio?: Record<string, any>;
      };

      // In development, enriched fields may be present
      if (process.env.NODE_ENV === 'development' || process.env.VITE_ENVIRONMENT === 'development') {
        console.log('Dev mode status fields:', {
          hasBalances: !!status.balances,
          hasPortfolio: !!status.portfolio,
        });

        if (status.balances) {
          expect(typeof status.balances).toBe('object');
        }
        if (status.portfolio) {
          expect(typeof status.portfolio).toBe('object');
        }
      }

      // Production should not have these fields
      if (process.env.NODE_ENV === 'production') {
        expect(status.balances).toBeUndefined();
        expect(status.portfolio).toBeUndefined();
      }
    } catch (error) {
      if (axios.isAxiosError(error) && error.code === 'ECONNREFUSED') {
        console.warn('Backend not running - skipping integration test');
        return;
      }
      throw error;
    }
  });

  it('should handle portfolio_value inference correctly', async () => {
    try {
      const response = await apiClient.get<AgentStatus>('/api/v1/bot/status');
      const status = response.data;

      // portfolio_value should be populated if platform is available
      // (even if agent is stopped)
      if (status.state !== 'error') {
        // Either portfolio_value is a number or null
        expect([null, 'number']).toContain(status.portfolio_value === null ? null : typeof status.portfolio_value);

        if (status.portfolio_value !== null) {
          expect(status.portfolio_value).toBeGreaterThanOrEqual(0);
          console.log(`✓ Portfolio value inferred: $${status.portfolio_value.toFixed(2)}`);
        }
      }
    } catch (error) {
      if (axios.isAxiosError(error) && error.code === 'ECONNREFUSED') {
        console.warn('Backend not running - skipping integration test');
        return;
      }
      throw error;
    }
  });
});
