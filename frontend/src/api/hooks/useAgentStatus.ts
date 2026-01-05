/**
 * @deprecated Use useAgentStream for real-time agent status via WebSocket
 * This maintains backward compatibility but delegates to real-time WebSocket stream
 */
import { useAgentStream } from './useAgentStream';

export function useAgentStatus(enabled: boolean = true) {
  const { status, isConnected, error } = useAgentStream();
  
  return {
    data: enabled ? status : null,
    isLoading: enabled && !status && !error,
    isFetching: false, // WebSocket is always fetching when connected
    error: error ? new Error(error) : null,
    isConnected,
    refetch: async () => {}, // No-op: WebSocket handles updates automatically
  };
}
