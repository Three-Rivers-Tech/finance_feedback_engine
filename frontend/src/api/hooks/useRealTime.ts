/**
 * Real-Time React Query Hooks
 * Provides smooth real-time updates via WebSocket instead of polling
 */

import { useEffect } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { getWebSocketService, type WebSocketMessage } from '../../services/websocket';
import apiClient from '../client';
import type { PortfolioStatus, Decision, Position, HealthStatus } from '../types';

type DecisionEventPayload = Partial<Decision> & { id?: string; decision_id?: string };

/**
 * Real-time portfolio status hook
 * Replaces polling with WebSocket updates
 */
export function usePortfolioRealTime(enabled = true) {
  const queryClient = useQueryClient();

  // Initial fetch
  const query = useQuery<PortfolioStatus>({
    queryKey: ['portfolio', 'status'],
    queryFn: async () => {
      const response = await apiClient.get('/api/v1/bot/status');
      return response.data as PortfolioStatus;
    },
    enabled,
    refetchOnWindowFocus: false,
    staleTime: 30000, // Keep data fresh for 30s even with WebSocket updates
  });

  // Set up WebSocket listener for portfolio updates
  useEffect(() => {
    if (!enabled) return;

    const service = getWebSocketService();
    const unsubscribe = service.on('portfolio_update', (msg: WebSocketMessage<PortfolioStatus>) => {
      // Update cache with WebSocket data
      queryClient.setQueryData(['portfolio', 'status'], msg.data);
    });

    return unsubscribe;
  }, [enabled, queryClient]);

  return query;
}

/**
 * Real-time positions hook
 * Replaces polling with WebSocket updates
 */
export function usePositionsRealTime(enabled = true) {
  const queryClient = useQueryClient();

  const query = useQuery<Position[]>({
    queryKey: ['positions'],
    queryFn: async () => {
      const response = await apiClient.get('/api/v1/bot/positions');
      return response.data as Position[];
    },
    enabled,
    refetchOnWindowFocus: false,
    staleTime: 30000,
  });

  // Set up WebSocket listeners for position updates
  useEffect(() => {
    if (!enabled) return;

    const service = getWebSocketService();
    const unsubscribers: (() => void)[] = [];

    // Listen for position open/close/update events
    unsubscribers.push(
      service.on<Position>('position_opened', (msg) => {
        queryClient.setQueryData(['positions'], (prev: Position[] | undefined) => {
          return prev ? [...prev, msg.data] : [msg.data];
        });
      })
    );

    unsubscribers.push(
      service.on<Position>('position_updated', (msg) => {
        queryClient.setQueryData(['positions'], (prev: Position[] | undefined) => {
          if (!prev) return [msg.data];
          return prev.map((p) => (p.id === msg.data.id ? msg.data : p));
        });
      })
    );

    unsubscribers.push(
      service.on<Position>('position_closed', (msg) => {
        queryClient.setQueryData(['positions'], (prev: Position[] | undefined) => {
          return prev ? prev.filter((p) => p.id !== msg.data.id) : [];
        });
      })
    );

    return () => {
      unsubscribers.forEach((unsub) => unsub());
    };
  }, [enabled, queryClient]);

  return query;
}

/**
 * Real-time decisions hook
 * Replaces polling with WebSocket updates
 */
export function useDecisionsRealTime(enabled = true, limit = 20) {
  const queryClient = useQueryClient();

  const query = useQuery<Decision[]>({
    queryKey: ['decisions', limit],
    queryFn: async () => {
      const response = await apiClient.get('/api/v1/decisions', {
        params: { limit },
      });
      return response.data as Decision[];
    },
    enabled,
    refetchOnWindowFocus: false,
    staleTime: 30000,
  });

  // Set up WebSocket listener for new decisions
  useEffect(() => {
    if (!enabled) return;

    const service = getWebSocketService();
    const unsubscribe = service.on<DecisionEventPayload>('decision_made', (msg) => {
      queryClient.setQueryData(['decisions', limit], (prev: Decision[] | undefined) => {
        const newDecision: Decision = {
          decision_id: msg.data.id ?? msg.data.decision_id ?? 'decision-realtime',
          asset_pair: msg.data.asset_pair ?? 'UNKNOWN',
          action: (msg.data.action as Decision['action']) ?? 'HOLD',
          confidence: typeof msg.data.confidence === 'number' ? msg.data.confidence : 0,
          reasoning: msg.data.reasoning ?? 'Realtime decision event',
          timestamp: msg.data.timestamp ?? new Date().toISOString(),
        };

        const updated = [newDecision, ...(prev || [])];
        return updated.slice(0, limit);
      });
    });

    return unsubscribe;
  }, [enabled, limit, queryClient]);

  return query;
}

/**
 * Real-time health status hook
 * Monitors backend health via WebSocket heartbeats
 */
export function useHealthStatusRealTime(enabled = true) {
  const queryClient = useQueryClient();

  const query = useQuery<HealthStatus>({
    queryKey: ['health'],
    queryFn: async () => {
      const response = await apiClient.get('/health');
      return response.data;
    },
    enabled,
    refetchInterval: 30000, // Fallback to polling every 30s
    staleTime: 15000,
  });

  // Listen for heartbeats as health indicator
  useEffect(() => {
    if (!enabled) return;

    const service = getWebSocketService();
    const unsubscribe = service.on('heartbeat', () => {
      // Service is alive, invalidate health query to refetch if stale
      queryClient.invalidateQueries({ queryKey: ['health'] });
    });

    return unsubscribe;
  }, [enabled, queryClient]);

  return query;
}

/**
 * Subscribe to portfolio updates without using query
 * Useful for live data in custom components
 */
export function usePortfolioUpdates(callback: (data: PortfolioStatus) => void, enabled = true) {
  useEffect(() => {
    if (!enabled) return;

    const service = getWebSocketService();
    return service.on('portfolio_update', (msg: WebSocketMessage<PortfolioStatus>) => {
      callback(msg.data);
    });
  }, [callback, enabled]);
}

/**
 * Subscribe to position updates without using query
 */
export function usePositionUpdates(
  callback: (action: 'opened' | 'updated' | 'closed', data: Position) => void,
  enabled = true
) {
  useEffect(() => {
    if (!enabled) return;

    const service = getWebSocketService();
    const unsubscribers: (() => void)[] = [];

    unsubscribers.push(
      service.on<Position>('position_opened', (msg) => {
        callback('opened', msg.data);
      })
    );

    unsubscribers.push(
      service.on<Position>('position_updated', (msg) => {
        callback('updated', msg.data);
      })
    );

    unsubscribers.push(
      service.on<Position>('position_closed', (msg) => {
        callback('closed', msg.data);
      })
    );

    return () => {
      unsubscribers.forEach((unsub) => unsub());
    };
  }, [callback, enabled]);
}

/**
 * Subscribe to decision events
 */
export function useDecisionUpdates(
  callback: (decision: Decision) => void,
  enabled = true
) {
  useEffect(() => {
    if (!enabled) return;

    const service = getWebSocketService();
    return service.on<Decision>('decision_made', (msg) => {
      callback(msg.data);
    });
  }, [callback, enabled]);
}
