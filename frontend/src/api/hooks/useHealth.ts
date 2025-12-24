import { usePolling } from './usePolling';
import apiClient from '../client';
import type { HealthStatus } from '../types';
import { POLL_INTERVALS } from '../../utils/constants';

export function useHealth(enabled: boolean = true) {
  return usePolling<HealthStatus>(
    async () => {
      const response = await apiClient.get('/health');
      return response.data;
    },
    POLL_INTERVALS.MEDIUM,
    enabled
  );
}
