import { usePolling } from './usePolling';
import apiClient from '../client';
import type { Position } from '../types';
import { POLL_INTERVALS } from '../../utils/constants';

export function usePositions(enabled: boolean = true) {
  return usePolling<Position[]>(
    async () => {
      const response = await apiClient.get('/v1/bot/positions');
      // API returns { positions: Position[], count: number, total_value: ..., timestamp: ... }
      // Extract the positions array
      return response.data.positions || [];
    },
    POLL_INTERVALS.CRITICAL,
    enabled
  );
}
