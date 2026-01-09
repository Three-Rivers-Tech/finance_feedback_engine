import { test, expect } from '@playwright/test';
import type { AgentStatus } from '../src/types/agent';

/**
 * E2E tests for the Bot Status API endpoint
 * Tests the full request/response cycle with real HTTP calls
 */
test.describe('Bot Status API E2E', () => {
  const API_KEY = 'dev-key-12345';
  const API_BASE_URL = 'http://localhost:8000';

  test('should fetch status with authentication', async ({ request }) => {
    const response = await request.get(`${API_BASE_URL}/api/v1/bot/status`, {
      headers: {
        'Authorization': `Bearer ${API_KEY}`,
      },
    });

    expect(response.ok()).toBeTruthy();
    expect(response.status()).toBe(200);

    const status = await response.json() as AgentStatus;

    // Verify required fields match AgentStatus interface
    expect(status).toHaveProperty('state');
    expect(status).toHaveProperty('total_trades');
    expect(status).toHaveProperty('active_positions');
    expect(status).toHaveProperty('config');

    // Verify field types
    expect(typeof status.state).toBe('string');
    expect(typeof status.total_trades).toBe('number');
    expect(typeof status.active_positions).toBe('number');
    expect(typeof status.config).toBe('object');

    // Log response for debugging
    console.log('Status response:', JSON.stringify(status, null, 2));
  });

  test('should reject requests without authentication', async ({ request }) => {
    const response = await request.get(`${API_BASE_URL}/api/v1/bot/status`);

    expect(response.ok()).toBeFalsy();
    expect(response.status()).toBe(401);

    const body = await response.json();
    expect(body).toHaveProperty('detail');
  });

  test('should reject requests with invalid API key', async ({ request }) => {
    const response = await request.get(`${API_BASE_URL}/api/v1/bot/status`, {
      headers: {
        'Authorization': 'Bearer invalid-key',
      },
    });

    expect(response.ok()).toBeFalsy();
    expect(response.status()).toBe(401);
  });

  test('should include development mode fields when available', async ({ request }) => {
    const response = await request.get(`${API_BASE_URL}/api/v1/bot/status`, {
      headers: {
        'Authorization': `Bearer ${API_KEY}`,
      },
    });

    expect(response.ok()).toBeTruthy();
    const status = await response.json() as AgentStatus & {
      balances?: Record<string, number>;
      portfolio?: Array<{ asset: string; quantity: number; value: number }>;
    };

    // Development mode fields are optional but should be present if backend is in dev mode
    // Just verify they're either undefined or have the correct type
    if (status.balances) {
      expect(typeof status.balances).toBe('object');
    }

    if (status.portfolio) {
      expect(Array.isArray(status.portfolio)).toBeTruthy();
    }
  });

  test('should handle portfolio_value inference correctly', async ({ request }) => {
    const response = await request.get(`${API_BASE_URL}/api/v1/bot/status`, {
      headers: {
        'Authorization': `Bearer ${API_KEY}`,
      },
    });

    expect(response.ok()).toBeTruthy();
    const status = await response.json() as AgentStatus;

    // portfolio_value can be null or a number
    if (status.portfolio_value !== null) {
      expect(typeof status.portfolio_value).toBe('number');
      expect(status.portfolio_value).toBeGreaterThanOrEqual(0);
    }
  });

  test('should return valid timestamp formats', async ({ request }) => {
    const response = await request.get(`${API_BASE_URL}/api/v1/bot/status`, {
      headers: {
        'Authorization': `Bearer ${API_KEY}`,
      },
    });

    expect(response.ok()).toBeTruthy();
    const status = await response.json() as AgentStatus;

    // If last_decision_time is present, it should be a valid ISO string
    if (status.last_decision_time) {
      const date = new Date(status.last_decision_time);
      expect(date.toString()).not.toBe('Invalid Date');
    }
  });
});
