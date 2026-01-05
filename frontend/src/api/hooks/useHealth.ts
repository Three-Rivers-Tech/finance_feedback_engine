/**
 * @deprecated Use useHealthStatusRealTime from useRealTime.ts instead
 * This maintains backward compatibility but uses WebSocket-backed real-time updates
 */

import { useHealthStatusRealTime } from './useRealTime';

export function useHealth(enabled: boolean = true) {
  return useHealthStatusRealTime(enabled);
}
