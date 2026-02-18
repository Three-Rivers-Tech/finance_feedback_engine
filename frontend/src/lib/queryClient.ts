/**
 * TanStack Query client configuration for Finance Feedback Engine
 */

import { QueryClient } from '@tanstack/react-query';

type ApiErrorLike = {
  response?: {
    status?: number;
  };
};

function isClientError(error: unknown): boolean {
  const status = (error as ApiErrorLike)?.response?.status;
  return typeof status === 'number' && status >= 400 && status < 500;
}

export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 10_000,
      gcTime: 5 * 60 * 1000,
      retry: (failureCount, error) => {
        if (isClientError(error)) {
          return false;
        }
        return failureCount < 2;
      },
      retryDelay: (attemptIndex) => Math.min(1000 * 2 ** attemptIndex, 30000),
      refetchOnWindowFocus: true,
      refetchOnReconnect: true,
      refetchOnMount: true,
    },
    mutations: {
      retry: (failureCount, error) => {
        if (isClientError(error)) {
          return false;
        }
        return failureCount < 1;
      },
      retryDelay: 1000,
      onError: (error) => {
        console.error('Mutation error:', error);
        if (isClientError(error) && (error as ApiErrorLike)?.response?.status === 401) {
          console.warn('Authentication expired - update API key in Settings');
        }
      },
    },
  },
});
