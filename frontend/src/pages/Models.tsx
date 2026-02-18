import React, { useMemo, useState } from 'react';
import { type PullProgress } from '../api/ollama';
import { useOllamaModels, useOllamaStatus, usePullOllamaModel, useUpdateDebateProviders } from '../api/mutations/useOllamaModels';

export const Models: React.FC = () => {
  // React Query hooks
  const { data: modelsData = [], isLoading, refetch } = useOllamaModels();
  const { data: ollamaStatus, isLoading: configLoading } = useOllamaStatus();
  const pullModel = usePullOllamaModel();
  const updateDebate = useUpdateDebateProviders();

  // Local state for UI
  const [modelName, setModelName] = useState('');
  const [logs, setLogs] = useState<string[]>([]);
  const [pullError, setPullError] = useState<string | null>(null);
  const [debateProviders, setDebateProviders] = useState({ bull: '', bear: '', judge: '' });
  const [saveNotice, setSaveNotice] = useState<string | null>(null);

  // Extract model names from query data
  const models = modelsData.map((m) => m.name);
  const canSaveDebate = Object.values(debateProviders).every((v) => v.trim().length > 0);

  const updateSeat = (seat: 'bull' | 'bear' | 'judge', value: string) => {
    setDebateProviders((prev) => ({ ...prev, [seat]: value }));
  };

  const statusDebateProviders = useMemo(() => ({
    bull: ollamaStatus?.debateConfig?.bull || '',
    bear: ollamaStatus?.debateConfig?.bear || '',
    judge: ollamaStatus?.debateConfig?.judge || '',
  }), [ollamaStatus?.debateConfig]);

const onPull = async (e?: React.FormEvent) => {
    e?.preventDefault();
    const name = modelName.trim();
    if (!name) return;

    setLogs([]);
    setPullError(null);

    pullModel.mutate(
      {
        name,
        onProgress: (p: PullProgress) => {
          const pct = p.total && p.completed ? ` (${Math.floor((p.completed / p.total) * 100)}%)` : '';
          const line = p.error ? `ERROR: ${p.error}` : `${p.status || 'update'}${pct}`;
          setLogs(prev => [...prev, line].slice(-200));
        },
      },
      {
        onSuccess: () => {
          setLogs(prev => [...prev, 'Done - model installed successfully']);
          setModelName(''); // Clear input on success
        },
        onError: (error: unknown) => {
          const errorMsg = error instanceof Error ? error.message : String(error);
          setLogs(prev => [...prev, `Failed: ${errorMsg}`]);
          setPullError(errorMsg);
        },
      }
    );
  };

  const quickPull = async (model: string) => {
    setModelName(model);
    setLogs([`Pulling ${model}...`]);
    setPullError(null);

    pullModel.mutate(
      {
        name: model,
        onProgress: (p: PullProgress) => {
          const pct = p.total && p.completed ? ` (${Math.floor((p.completed / p.total) * 100)}%)` : '';
          const line = p.error ? `ERROR: ${p.error}` : `${p.status || 'update'}${pct}`;
          setLogs(prev => [...prev, line].slice(-200));
        },
      },
      {
        onSuccess: () => {
          setLogs(prev => [...prev, 'Done - model installed successfully']);
        },
        onError: (error: unknown) => {
          const errorMsg = error instanceof Error ? error.message : String(error);
          setLogs(prev => [...prev, `Failed: ${errorMsg}`]);
          setPullError(errorMsg);
        },
      }
    );
  };

  const onSaveDebateProviders = async () => {
    setSaveNotice(null);
    updateDebate.mutate(
      {
        bull: debateProviders.bull,
        bear: debateProviders.bear,
        judge: debateProviders.judge,
      },
      {
        onSuccess: () => {
          setSaveNotice('Saved to config.local.yaml. In production, restart the backend to ensure the new models are active.');
        },
        onError: (error: unknown) => {
          const msg = error instanceof Error ? error.message : 'Failed to save debate providers';
          setSaveNotice(msg);
        },
      }
    );
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-mono font-bold text-accent-cyan uppercase">Ollama Models</h1>
        {!configLoading && (
          <div className="flex items-center gap-2">
            <span className={`w-3 h-3 rounded-full ${ollamaStatus?.available ? 'bg-green-500' : 'bg-red-500'}`}></span>
            <span className="text-sm font-mono text-text-secondary">
              {ollamaStatus?.available ? 'Connected' : 'Disconnected'}
            </span>
          </div>
        )}
      </div>

      {!configLoading && !ollamaStatus?.available && (
        <div className="border-3 border-red-600 bg-red-900/20 rounded p-4">
          <h3 className="text-red-400 font-mono font-bold mb-2">⚠ Ollama Service Unavailable</h3>
          <p className="text-sm text-text-secondary mb-2">
            {ollamaStatus?.error || 'Unable to connect to Ollama service'}
          </p>
          <p className="text-xs text-gray-400">
            Start Ollama with: <code className="bg-black/30 px-2 py-1 rounded">ollama serve</code>
          </p>
        </div>
      )}

      {/* Debate Configuration Status */}
      {!configLoading && ollamaStatus?.debateConfig && (
        <div className="border-3 border-border-primary rounded p-4">
          <h2 className="font-mono font-bold text-accent-cyan mb-3">Debate Mode Configuration</h2>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            {(['bull', 'bear', 'judge'] as const).map((seat) => {
              const provider = ollamaStatus.debateConfig![seat];
              const isMissing = ollamaStatus.missing.includes(provider);
              const isInstalled = Boolean(provider) && !isMissing;

              return (
                <div key={seat} className="border-2 border-border-secondary rounded p-3">
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-xs uppercase font-mono text-text-secondary">{seat}</span>
                    <span className={`text-xs font-mono ${isInstalled ? 'text-green-400' : 'text-red-400'}`}>
                      {isInstalled ? '✓' : '✗'}
                    </span>
                  </div>
                  <div className="text-sm font-mono text-text-primary mb-2">{provider}</div>
                  {isMissing && (
                    <button
                      onClick={() => quickPull(provider)}
                      disabled={pullModel.isPending}
                      className="text-xs px-2 py-1 border-2 border-accent-cyan rounded hover:bg-accent-cyan/20 disabled:opacity-50"
                    >
                      Pull Model
                    </button>
                  )}

                </div>
              );
            })}
          </div>
          {ollamaStatus.missing.length > 0 && (
            <div className="mt-3 p-3 bg-yellow-900/20 border-2 border-yellow-600 rounded">
              <p className="text-sm text-yellow-400 font-mono">
                ⚠ Missing models: {ollamaStatus.missing.join(', ')}
              </p>
              <p className="text-xs text-text-secondary mt-1">
                Agent will not start until these models are installed
              </p>
            </div>
          )}

          <div className="mt-4 border-2 border-border-secondary rounded p-3 bg-bg-secondary/50">
            <div className="flex items-center justify-between mb-2">
              <h3 className="text-sm font-mono font-bold text-accent-cyan">Override Debate Providers</h3>
              <span className="text-[10px] uppercase text-text-secondary">Writes to config.local.yaml</span>
            </div>
            <p className="text-xs text-text-secondary mb-3">
              Choose any installed model tag (or type a custom one). Changes persist to config.local.yaml; in production, restart the backend to apply.
            </p>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
              {(['bull', 'bear', 'judge'] as const).map((seat) => (
                <div key={seat} className="flex flex-col gap-2">
                  <label className="text-[11px] uppercase font-mono text-text-secondary">{seat}</label>
                  <input
                    list="ollama-model-options"
                    value={debateProviders[seat]}
                    onChange={(e) => updateSeat(seat, e.target.value)}
                    placeholder="e.g. mistral:latest"
                    className="px-2 py-2 bg-bg-secondary border-2 border-border-primary rounded text-xs font-mono"
                  />
                </div>
              ))}
            </div>
            <datalist id="ollama-model-options">
              {models.map((m) => (
                <option key={m} value={m} />
              ))}
            </datalist>
            <div className="mt-3 flex items-center gap-3">
              <button
                type="button"
                onClick={() => setDebateProviders(statusDebateProviders)}
                className="px-4 py-2 border-3 rounded font-mono text-xs border-border-primary text-text-primary hover:border-accent-cyan"
              >
                Reset to Current Config
              </button>
            </div>
            <div className="mt-3 flex items-center gap-3">
              <button
                type="button"
                onClick={onSaveDebateProviders}
                disabled={!canSaveDebate || updateDebate.isPending}
                className={`px-4 py-2 border-3 rounded font-mono text-xs ${
                  updateDebate.isPending ? 'opacity-60 cursor-not-allowed' : 'hover:border-accent-cyan'
                } border-border-primary text-text-primary`}
              >
                {updateDebate.isPending ? 'Saving…' : 'Save Debate Providers'}
              </button>
              <p className="text-[11px] text-text-secondary">
                Dev note: writing to config.local.yaml from the UI is intended for development; secure this endpoint for production.
              </p>
            </div>
            {saveNotice && (
              <div className="mt-2 text-xs text-text-secondary">
                {saveNotice}
              </div>
            )}
          </div>
        </div>
      )}

      {/* Error Toast */}
      {pullError && (
        <div className="border-3 border-red-600 bg-red-900/20 rounded p-4">
          <h3 className="text-red-400 font-mono font-bold mb-2">⚠ Pull Failed</h3>
          <p className="text-sm text-text-secondary">{pullError}</p>
          <button
            onClick={() => refetch()}
            className="mt-2 text-xs px-3 py-1 border-2 border-accent-cyan rounded hover:bg-accent-cyan/20"
          >
            Try Manual Refresh
          </button>
        </div>
      )}

      <form onSubmit={onPull} className="flex flex-wrap items-center gap-2">
        <input
          className="px-3 py-2 bg-bg-secondary border-3 border-border-primary rounded text-sm font-mono w-80"
          placeholder="e.g. mistral:latest, llama2:13b"
          value={modelName}
          onChange={(e) => setModelName(e.target.value)}
        />
        <button
          type="submit"
          disabled={pullModel.isPending}
          className={`px-4 py-2 border-3 rounded font-mono text-sm ${
            pullModel.isPending ? 'opacity-60 cursor-not-allowed' : 'hover:border-accent-cyan'
          } border-border-primary text-text-primary`}
        >
          {pullModel.isPending ? 'Pulling…' : 'Pull Model'}
        </button>
        <button
          type="button"
          onClick={() => void refetch()}
          disabled={isLoading}
          className="px-3 py-2 border-3 rounded font-mono text-sm border-border-primary hover:border-accent-cyan"
        >
          {isLoading ? 'Refreshing…' : 'Refresh'}
        </button>
      </form>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <div>
          <h2 className="font-mono text-sm mb-2 text-text-secondary">Installed Models ({models.length})</h2>
          <div className="border-3 border-border-primary rounded p-3 min-h-[120px] max-h-96 overflow-auto">
            {models.length === 0 ? (
              <div className="text-center py-8">
                <p className="text-sm text-gray-400 mb-3">No models found.</p>
                <p className="text-xs text-text-secondary">
                  Pull recommended models:
                </p>
                <div className="mt-2 space-x-2">
                  <button
                    onClick={() => quickPull('llama3.2:3b-instruct-fp16')}
                    disabled={pullModel.isPending}
                    className="text-xs px-2 py-1 border-2 border-border-primary rounded hover:border-accent-cyan disabled:opacity-50"
                  >
                    llama3.2:3b
                  </button>
                  <button
                    onClick={() => quickPull('mistral:latest')}
                    disabled={pullModel.isPending}
                    className="text-xs px-2 py-1 border-2 border-border-primary rounded hover:border-accent-cyan disabled:opacity-50"
                  >
                    mistral
                  </button>
                </div>
              </div>
            ) : (
              <ul className="space-y-1 text-sm">
                {models.map((m) => (
                  <li key={m} className="font-mono flex items-center justify-between py-1 px-2 hover:bg-bg-tertiary rounded">
                    <span>{m}</span>
                    <span className="text-xs text-green-400">✓</span>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </div>
        <div>
          <h2 className="font-mono text-sm mb-2 text-text-secondary">Pull Progress</h2>
          <pre className="border-3 border-border-primary rounded p-3 text-xs font-mono whitespace-pre-wrap min-h-[120px] max-h-96 overflow-auto bg-black/30">
            {logs.length > 0 ? logs.join('\n') : 'No activity'}
          </pre>
        </div>
      </div>

      <div className="border-3 border-border-secondary rounded p-4 bg-bg-secondary">
        <h3 className="text-sm font-mono font-bold text-accent-cyan mb-2">BYOM (Bring Your Own Model)</h3>
        <p className="text-xs text-text-secondary mb-3">
          Assign specific Ollama models to debate seats (bull/bear/judge) by editing <code>config/config.yaml</code>:
        </p>
        <pre className="text-xs font-mono bg-black/50 p-3 rounded overflow-x-auto">
{`debate_providers:
  bull: "mistral:7b-instruct"   # Fast, aggressive
  bear: "llama2:13b"             # Larger, conservative
  judge: "deepseek-r1:8b"        # Balanced reasoning`}
        </pre>
        <p className="text-xs text-gray-400 mt-2">
          Models must be installed before the agent starts. Use the form above to pull models.
        </p>
      </div>

      <p className="text-xs text-gray-400">
        Note: This uses the local Ollama API via /ollama proxy. Ensure Ollama is running and accessible.
      </p>
    </div>
  );
};
