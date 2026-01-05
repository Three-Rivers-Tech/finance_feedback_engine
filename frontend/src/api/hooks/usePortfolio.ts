/**
 * @deprecated Use usePortfolioRealTime from useRealTime.ts instead
 * This maintains backward compatibility but uses WebSocket-backed real-time updates
 */

import { usePortfolioRealTime } from './useRealTime';

export function usePortfolio(enabled: boolean = true) {
  return usePortfolioRealTime(enabled);
}
