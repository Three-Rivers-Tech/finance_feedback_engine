import { usePolling } from './usePolling';
import apiClient from '../client';
import { Decision } from '../types';
import { POLL_INTERVALS } from '../../utils/constants';

export function useDecisions(limit: number = 10, enabled: boolean = true) {
  return usePolling<Decision[]>(
    async () => {
      const response = await apiClient.get(`/api/v1/decisions?limit=${limit}`);
      return response.data;
    },
    POLL_INTERVALS.MEDIUM,
    enabled
  );
}
