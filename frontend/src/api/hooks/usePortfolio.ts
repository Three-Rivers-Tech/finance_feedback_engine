import { usePolling } from './usePolling';
import apiClient from '../client';
import type { PortfolioStatus } from '../types';
import { POLL_INTERVALS } from '../../utils/constants';

export function usePortfolio(enabled: boolean = true) {
  return usePolling<PortfolioStatus>(
    async () => {
      const response = await apiClient.get('/v1/status');
      return response.data;
    },
    POLL_INTERVALS.MEDIUM,
    enabled
  );
}
