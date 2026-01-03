import { usePolling } from './usePolling';
import apiClient from '../client';
import type { AgentStatus } from '../types';
import { POLL_INTERVALS } from '../../utils/constants';

export function useAgentStatus(enabled: boolean = true) {
  return usePolling<AgentStatus>(
    async () => {
      const response = await apiClient.get('/api/v1/bot/status');
      return response.data;
    },
    POLL_INTERVALS.CRITICAL,
    enabled
  );
}
