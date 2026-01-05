import { useMutation, useQuery, useQueryClient, type UseQueryResult } from '@tanstack/react-query';
import { useEffect } from 'react';
import apiClient, { handleApiError } from '../client';
import { queryKeys } from '../queryKeys';
import type { AgentStatus } from '../types';
import { getWebSocketService, type WebSocketMessage } from '../../services/websocket';

/**
 * Real-time agent status hook using WebSocket
 * Replaces polling with live updates from agent stream
 */
export function useAgentStatusQuery(enabled: boolean = true): UseQueryResult<AgentStatus, Error> {
  const queryClient = useQueryClient();
  
  // Initial fetch
  const query = useQuery<AgentStatus>({
    queryKey: queryKeys.agent.status(),
    queryFn: async () => {
      const response = await apiClient.get('/api/v1/bot/status');
      return response.data as AgentStatus;
    },
    enabled,
    refetchOnWindowFocus: false,
    staleTime: 30000, // Keep cache fresh for 30s
  });

  // Set up WebSocket listener for real-time agent status updates
  useEffect(() => {
    if (!enabled) return;

    const service = getWebSocketService();
    const unsubscribe = service.on('agent_status_update', (msg: WebSocketMessage<AgentStatus>) => {
      // Update React Query cache with WebSocket data
      queryClient.setQueryData(queryKeys.agent.status(), msg.data);
    });

    return unsubscribe;
  }, [enabled, queryClient]);

  return query;
}

function useInvalidateAgent() {
  const queryClient = useQueryClient();
  return async () => {
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: queryKeys.agent.status() }),
      queryClient.invalidateQueries({ queryKey: queryKeys.agent.positions() }),
      queryClient.invalidateQueries({ queryKey: queryKeys.portfolio.status() }),
      queryClient.invalidateQueries({ queryKey: queryKeys.decisions.all }),
    ]);
  };
}

export function useStartAgent() {
  const invalidate = useInvalidateAgent();
  return useMutation({
    mutationFn: async ({ autonomous, asset_pairs }: { autonomous: boolean; asset_pairs: string[] }) => {
      const response = await apiClient.post('/api/v1/bot/start', { autonomous, asset_pairs });
      return response.data;
    },
    onSuccess: invalidate,
  });
}

export function useStopAgent() {
  const invalidate = useInvalidateAgent();
  return useMutation({
    mutationFn: async () => {
      const response = await apiClient.post('/api/v1/bot/stop');
      return response.data;
    },
    onSuccess: invalidate,
  });
}

export function usePauseAgent() {
  const invalidate = useInvalidateAgent();
  return useMutation({
    mutationFn: async () => {
      const response = await apiClient.post('/api/v1/bot/pause');
      return response.data;
    },
    onSuccess: invalidate,
  });
}

export function useResumeAgent() {
  const invalidate = useInvalidateAgent();
  return useMutation({
    mutationFn: async () => {
      const response = await apiClient.post('/api/v1/bot/resume');
      return response.data;
    },
    onSuccess: invalidate,
  });
}

export function useEmergencyStopAgent() {
  const invalidate = useInvalidateAgent();
  return useMutation({
    mutationFn: async () => {
      const response = await apiClient.post('/api/v1/bot/emergency-stop?close_positions=true');
      return response.data;
    },
    onSuccess: invalidate,
  });
}

export function useUpdateAgentConfig() {
  const invalidate = useInvalidateAgent();
  return useMutation({
    mutationFn: async (payload: { stop_loss_pct?: number; position_size_pct?: number; confidence_threshold?: number }) => {
      const response = await apiClient.patch('/api/v1/bot/config', payload);
      return response.data;
    },
    onSuccess: invalidate,
  });
}

export function useManualTrade() {
  const invalidate = useInvalidateAgent();
  return useMutation({
    mutationFn: async (payload: { asset_pair: string; action: string; size?: number; price?: number }) => {
      const response = await apiClient.post('/api/v1/bot/manual-trade', payload);
      return response.data;
    },
    onSuccess: invalidate,
  });
}

export function useClosePosition() {
  const invalidate = useInvalidateAgent();
  return useMutation({
    mutationFn: async (positionId: string) => {
      const response = await apiClient.post(`/api/v1/bot/positions/${positionId}/close`);
      return response.data;
    },
    onSuccess: invalidate,
  });
}

export function mapMutationError(err: unknown): string {
  return handleApiError(err);
}
