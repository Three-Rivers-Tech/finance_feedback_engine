/**
 * Centralized query key factory for React Query
 *
 * Hierarchical structure ensures proper cache invalidation:
 * - Invalidating ['agent'] clears all agent-related queries
 * - Invalidating ['agent', 'status'] only clears agent status
 *
 * Pattern: ['domain', 'resource', ...filters]
 */

export const queryKeys = {
  // Agent control & status
  agent: {
    all: ['agent'] as const,
    status: () => [...queryKeys.agent.all, 'status'] as const,
    positions: () => [...queryKeys.agent.all, 'positions'] as const,
    position: (id: string) => [...queryKeys.agent.positions(), id] as const,
  },

  // Portfolio metrics
  portfolio: {
    all: ['portfolio'] as const,
    status: () => [...queryKeys.portfolio.all, 'status'] as const,
    balance: () => [...queryKeys.portfolio.all, 'balance'] as const,
  },

  // Trading decisions
  decisions: {
    all: ['decisions'] as const,
    infinite: () => [...queryKeys.decisions.all, 'infinite'] as const,
    list: (limit: number) => [...queryKeys.decisions.all, 'list', limit] as const,
    detail: (id: string) => [...queryKeys.decisions.all, 'detail', id] as const,
  },

  // System health
  health: {
    all: ['health'] as const,
    status: () => [...queryKeys.health.all, 'status'] as const,
  },

  // Ollama models
  ollama: {
    all: ['ollama'] as const,
    models: () => [...queryKeys.ollama.all, 'models'] as const,
    model: (name: string) => [...queryKeys.ollama.all, 'model', name] as const,
    config: () => [...queryKeys.ollama.all, 'config'] as const,
  },

  // Optimization experiments
  optimization: {
    all: ['optimization'] as const,
    results: (experimentId: string) => [...queryKeys.optimization.all, 'results', experimentId] as const,
  },
} as const;
