/**
 * React Query mutations for Ollama model management
 */

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { queryKeys } from '../queryKeys';
import { listOllamaModels, pullOllamaModel, deleteOllamaModel, type OllamaModelTag, type PullProgress } from '../ollama';

/**
 * Query hook to fetch installed Ollama models
 * No auto-refetch - manual refresh only
 */
export function useOllamaModels() {
  return useQuery({
    queryKey: queryKeys.ollama.models(),
    queryFn: async () => {
      const models = await listOllamaModels();
      return models;
    },
    staleTime: Infinity, // Don't auto-refetch - manual refresh via mutation
    gcTime: 10 * 60 * 1000, // Keep in cache for 10 minutes
  });
}

/**
 * Query hook to fetch Ollama health and debate config status
 * Refetches every 10 seconds
 */
export function useOllamaStatus() {
  return useQuery({
    queryKey: queryKeys.ollama.config(),
    queryFn: async () => {
      const res = await fetch('/api/health');
      if (!res.ok) throw new Error(`Health check failed: ${res.status}`);
      const health = await res.json();

      const ollama = (health.components?.ollama ?? health.ollama) || {};
      const statusFlag = typeof ollama.available === 'boolean'
        ? ollama.available
        : ollama.status !== 'unavailable';
      const models = ollama.models_loaded || ollama.models || [];
      const missing = ollama.models_missing || ollama.missing_debate_models || ollama.missing || [];

      return {
        available: Boolean(statusFlag),
        error: ollama.error,
        models,
        debateConfig: ollama.debate_config,
        missing
      };
    },
    refetchInterval: 10_000, // Refetch every 10 seconds
    staleTime: 5_000,
  });
}

/**
 * Mutation hook to pull an Ollama model with retry logic
 *
 * After pulling, retries fetching models list up to 5 times with exponential backoff
 * until the pulled model appears (Ollama needs time to index)
 */
export function usePullOllamaModel() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async ({
      name,
      onProgress,
    }: {
      name: string;
      onProgress?: (progress: PullProgress) => void;
    }) => {
      await pullOllamaModel(name, onProgress);
      return name;
    },
    onSuccess: async (pulledModel) => {
      // Retry logic: Poll for model to appear in list (Ollama registry lag)
      const maxRetries = 8;
      let delay = 500; // Start with 500ms
      let found = false;
      let latestModels: OllamaModelTag[] = [];

      const normalize = (name: string) => name.toLowerCase().split(':')[0];
      const pulledBase = normalize(pulledModel);

      for (let attempt = 0; attempt < maxRetries; attempt++) {
        // Wait before checking
        await new Promise(resolve => setTimeout(resolve, delay));

        // Fetch fresh models list
        try {
          latestModels = await listOllamaModels();

          // Check if pulled model appears (case-insensitive substring match)
          const modelLower = pulledModel.toLowerCase();
          found = latestModels.some(m => {
            const nameLower = m.name.toLowerCase();
            const base = normalize(m.name);
            return (
              nameLower.includes(modelLower) ||
              modelLower.includes(nameLower) ||
              base === pulledBase ||
              modelLower.includes(base)
            );
          });

          if (found) {
            // Model found - update cache and break
            queryClient.setQueryData<OllamaModelTag[]>(
              queryKeys.ollama.models(),
              latestModels
            );
            // Also invalidate status to update debate config
            await queryClient.invalidateQueries({ queryKey: queryKeys.ollama.config() });
            await queryClient.invalidateQueries({ queryKey: queryKeys.ollama.models() });
            break;
          }
        } catch (error) {
          console.warn(`Retry ${attempt + 1}/${maxRetries} failed:`, error);
        }

        // Exponential backoff (500ms → 750ms → 1125ms → 1687ms → 2531ms)
        delay = Math.min(delay * 1.5, 3000); // Cap at 3 seconds
      }

      if (!found) {
        // Final refresh attempt even if not found
        await queryClient.invalidateQueries({ queryKey: queryKeys.ollama.models() });
        await queryClient.invalidateQueries({ queryKey: queryKeys.ollama.config() });

        // Throw error to trigger onError in component
        throw new Error(`Model "${pulledModel}" not found in registry after ${maxRetries} attempts. Try manual refresh.`);
      }
    },
    onError: (error) => {
      console.error('Pull model error:', error);
    },
  });
}

/**
 * Mutation hook to delete an Ollama model
 */
export function useDeleteOllamaModel() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (name: string) => {
      await deleteOllamaModel(name);
      return name;
    },
    onSuccess: () => {
      // Invalidate models list to refetch
      queryClient.invalidateQueries({ queryKey: queryKeys.ollama.models() });
      queryClient.invalidateQueries({ queryKey: queryKeys.ollama.config() });
    },
  });
}

/**
 * Mutation hook to update debate providers (bull/bear/judge) and persist to config.local.yaml
 */
export function useUpdateDebateProviders() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async ({ bull, bear, judge }: { bull: string; bear: string; judge: string }) => {
      const res = await fetch('/api/v1/debate/providers', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ bull, bear, judge }),
      });

      if (!res.ok) {
        const errText = await res.text();
        throw new Error(`Failed to update debate providers: ${res.status} ${errText}`);
      }

      return res.json();
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.ollama.config() });
      queryClient.invalidateQueries({ queryKey: queryKeys.ollama.models() });
    },
  });
}
