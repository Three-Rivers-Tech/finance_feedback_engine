/**
 * @deprecated Use usePositionsRealTime from useRealTime.ts instead
 * This maintains backward compatibility but uses WebSocket-backed real-time updates
 */

import { usePositionsRealTime } from './useRealTime';

export function usePositions(enabled: boolean = true) {
  return usePositionsRealTime(enabled);
}
