/**
 * React Query Client Configuration
 * Centralized setup for all data fetching and caching
 */

import { QueryClient } from '@tanstack/react-query';

export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      // 30-second cache time (WebSocket updates arrive more frequently anyway)
      staleTime: 30 * 1000,
      // Keep cached data for 5 minutes before GC
      gcTime: 5 * 60 * 1000,
      // Don't retry failed queries by default (WebSocket will update)
      retry: 1,
      // Don't refetch on window focus (real-time updates via WebSocket)
      refetchOnWindowFocus: false,
      // Refetch on mount if data is stale
      refetchOnMount: true,
    },
    mutations: {
      retry: 1,
    },
  },
});
