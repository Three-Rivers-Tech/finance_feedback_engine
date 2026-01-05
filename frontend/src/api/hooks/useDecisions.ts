/**
 * @deprecated Use useDecisionsRealTime from useRealTime.ts instead
 * This maintains backward compatibility but uses WebSocket-backed real-time updates
 */

import { useDecisionsRealTime } from './useRealTime';

export function useDecisions(limit: number = 10, enabled: boolean = true) {
  return useDecisionsRealTime(enabled, limit);
}
