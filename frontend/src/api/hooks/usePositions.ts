import { usePolling } from './usePolling';
import apiClient from '../client';
import type { Position } from '../types';
import { POLL_INTERVALS } from '../../utils/constants';

export function usePositions(enabled: boolean = true) {
  return usePolling<Position[]>(
    async () => {
      const response = await apiClient.get('/api/v1/bot/positions');
      return response.data;
    },
    POLL_INTERVALS.CRITICAL,
    enabled
  );
}
