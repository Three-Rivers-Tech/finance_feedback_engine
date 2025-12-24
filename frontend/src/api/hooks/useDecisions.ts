import { usePolling } from './usePolling';
import apiClient from '../client';
import type { Decision } from '../types';
import { POLL_INTERVALS } from '../../utils/constants';

export function useDecisions(limit: number = 10, enabled: boolean = true) {
  return usePolling<Decision[]>(
    async () => {
      const response = await apiClient.get(`/api/v1/decisions?limit=${limit}`);
      // API returns { decisions: Decision[], count: number }
      // Extract the decisions array
      return response.data.decisions || [];
    },
    POLL_INTERVALS.MEDIUM,
    enabled
  );
}
