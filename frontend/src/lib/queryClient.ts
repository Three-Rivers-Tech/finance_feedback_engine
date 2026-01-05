/**
 * TanStack Query client configuration for Finance Feedback Engine
 *
 * Refetch intervals:
 * - CRITICAL (2s): Agent status (real-time state machine updates)
 * - MEDIUM (5s): Positions (active trade monitoring)
 * - LOW (10s): Portfolio, health (slower-changing data)
 * - MANUAL: Decisions (infinite scroll, user-triggered)
 */

import { QueryClient } from '@tanstack/react-query';

export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      // Default staleTime - will override per-query for different intervals
      staleTime: 10_000, // 10 seconds baseline

      // Cache time (how long unused data stays in memory)
      gcTime: 5 * 60 * 1000, // 5 minutes

      // Retry configuration
      retry: (failureCount, error: any) => {
        // Don't retry on 4xx errors (client errors)
        if (error?.response?.status >= 400 && error?.response?.status < 500) {
          return false;
        }
        // Retry up to 2 times for network errors
        return failureCount < 2;
      },
      retryDelay: (attemptIndex) => Math.min(1000 * 2 ** attemptIndex, 30000),

      // Automatic background refetching
      refetchOnWindowFocus: true,
      refetchOnReconnect: true,
      refetchOnMount: true,
    },
    mutations: {
      // Retry mutations once on network errors only
      retry: (failureCount, error: any) => {
        if (error?.response?.status >= 400 && error?.response?.status < 500) {
          return false;
        }
        return failureCount < 1;
      },
      retryDelay: 1000,

      // Global mutation error handler
      onError: (error: any) => {
        // Log mutation errors (can add toast notifications here)
        console.error('Mutation error:', error);

        // Handle auth token expiry globally
        if (error?.response?.status === 401) {
          // Clear auth and redirect handled by axios interceptor in authStore
          console.warn('Authentication expired - redirecting to login');
        }
      },
    },
  },
});
