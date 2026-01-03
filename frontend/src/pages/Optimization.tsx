import React, { useState } from 'react';
import { Card } from '../components/common/Card';
import { Button } from '../components/common/Button';
import { Spinner } from '../components/common/Spinner';
import apiClient, { handleApiError } from '../api/client';
import type { ExperimentRequest, ExperimentResponse } from '../api/types';
import { formatPercent, formatDate } from '../services/formatters';
import { useAgentStatus } from '../api/hooks/useAgentStatus';

export const Optimization: React.FC = () => {
  const [assetPairs, setAssetPairs] = useState('BTCUSD,ETHUSD');
  const [startDate, setStartDate] = useState('2024-01-01');
  const [endDate, setEndDate] = useState('2024-02-01');
  const [nTrials, setNTrials] = useState(50);
  const [optimizeWeights, setOptimizeWeights] = useState(false);
  const [multiObjective, setMultiObjective] = useState(false);
  const [isRunning, setIsRunning] = useState(false);
  const [result, setResult] = useState<ExperimentResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const { data: agentStatus } = useAgentStatus();
  const agentIsRunning = agentStatus?.state === 'running';

  const handleRunExperiment = async () => {
    // Validate inputs
    const pairs = assetPairs.split(',').map(p => p.trim()).filter(p => p.length > 0);
    if (pairs.length === 0) {
      setError('Please enter at least one asset pair');
      return;
    }
    if (startDate >= endDate) {
      setError('Start date must be before end date');
      return;
    }

    setIsRunning(true);
    setError(null);
    setResult(null);

    try {
      const request: ExperimentRequest = {
        asset_pairs: pairs,
        start_date: startDate,
        end_date: endDate,
        n_trials: nTrials,
        optimize_weights: optimizeWeights,
        multi_objective: multiObjective,
      };

      const response = await apiClient.post('/api/v1/optimization/experiment', request);
      setResult(response.data);
    } catch (err) {
      setError(handleApiError(err));
    } finally {
      setIsRunning(false);
    }
  };

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-mono font-bold text-accent-cyan uppercase">
        Optuna Optimization
      </h1>

      <Card>
        <h2 className="text-lg font-mono font-bold text-accent-cyan mb-4 uppercase">
          Run Experiment
        </h2>

        <div className="space-y-4">
          <div>
            <label className="block text-sm text-text-secondary mb-2 font-mono">
              Asset Pairs (comma-separated)
            </label>
            <input
              type="text"
              value={assetPairs}
              onChange={(e) => setAssetPairs(e.target.value)}
              className="w-full px-4 py-3 bg-bg-primary border-3 border-border-primary text-text-primary font-mono focus:border-accent-cyan outline-none"
              placeholder="BTCUSD,ETHUSD,EURUSD"
            />
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-sm text-text-secondary mb-2 font-mono">
                Start Date
              </label>
              <input
                type="date"
                value={startDate}
                onChange={(e) => setStartDate(e.target.value)}
                className="w-full px-4 py-3 bg-bg-primary border-3 border-border-primary text-text-primary font-mono focus:border-accent-cyan outline-none"
              />
            </div>
            <div>
              <label className="block text-sm text-text-secondary mb-2 font-mono">
                End Date
              </label>
              <input
                type="date"
                value={endDate}
                onChange={(e) => setEndDate(e.target.value)}
                className="w-full px-4 py-3 bg-bg-primary border-3 border-border-primary text-text-primary font-mono focus:border-accent-cyan outline-none"
              />
            </div>
          </div>

          <div>
            <label className="block text-sm text-text-secondary mb-2 font-mono">
              Number of Trials: {nTrials}
            </label>
            <input
              type="range"
              min="10"
              max="200"
              value={nTrials}
              onChange={(e) => setNTrials(Number(e.target.value))}
              className="w-full"
            />
          </div>

          <div className="flex gap-6">
            <label className="flex items-center gap-3 cursor-pointer">
              <input
                type="checkbox"
                checked={optimizeWeights}
                onChange={(e) => setOptimizeWeights(e.target.checked)}
                className="w-5 h-5"
              />
              <span className="text-sm text-text-primary font-mono">
                Optimize Ensemble Weights
              </span>
            </label>

            <label className="flex items-center gap-3 cursor-pointer">
              <input
                type="checkbox"
                checked={multiObjective}
                onChange={(e) => setMultiObjective(e.target.checked)}
                className="w-5 h-5"
              />
              <span className="text-sm text-text-primary font-mono">
                Multi-Objective (Sharpe + Drawdown)
              </span>
            </label>
          </div>

          {error && (
            <div className="p-4 bg-accent-red bg-opacity-20 border-3 border-accent-red">
              <p className="text-xs text-accent-red font-mono">{error}</p>
            </div>
          )}

          {agentIsRunning && (
            <div className="p-4 bg-accent-yellow bg-opacity-20 border-3 border-accent-yellow mb-2">
              <p className="text-xs text-accent-yellow font-mono">
                Trading agent is currently running. Stop the agent to run optimization.
              </p>
            </div>
          )}

          <Button
            onClick={handleRunExperiment}
            disabled={isRunning || agentIsRunning}
            className="w-full"
          >
            {isRunning ? 'Running Experiment...' : 'Run Experiment'}
          </Button>

          {isRunning && (
            <div className="text-center py-8">
              <Spinner size="lg" />
              <p className="mt-4 text-text-secondary font-mono">
                Optimizing parameters... This may take several minutes.
              </p>
            </div>
          )}
        </div>
      </Card>

      {result && (
        <Card>
          <h2 className="text-lg font-mono font-bold text-accent-cyan mb-4 uppercase">
            Experiment Results
          </h2>

          <div className="mb-4 pb-4 border-b-3 border-border-primary">
            <p className="text-sm text-text-secondary font-mono">
              Experiment ID: <span className="text-text-primary">{result.experiment_id}</span>
            </p>
            <p className="text-sm text-text-secondary font-mono">
              Created: <span className="text-text-primary">{formatDate(result.created_at)}</span>
            </p>
            <p className="text-sm text-text-secondary font-mono">
              Period: <span className="text-text-primary">{result.start_date} to {result.end_date}</span>
            </p>
          </div>

          <div className="space-y-6">
            {result.results.map((assetResult) => (
              <div key={assetResult.asset_pair} className="border-l-3 border-accent-cyan pl-4">
                <h3 className="text-lg font-mono font-bold mb-3">{assetResult.asset_pair}</h3>

                <div className="grid grid-cols-3 gap-4 mb-4">
                  <div>
                    <p className="text-xs text-text-secondary mb-1">Best Sharpe Ratio</p>
                    <p className="text-2xl font-mono font-bold text-accent-green">
                      {assetResult.best_sharpe_ratio?.toFixed(3) || 'N/A'}
                    </p>
                  </div>
                  {assetResult.best_drawdown_pct !== null && (
                    <div>
                      <p className="text-xs text-text-secondary mb-1">Max Drawdown</p>
                      <p className="text-2xl font-mono font-bold text-accent-red">
                        {formatPercent(assetResult.best_drawdown_pct)}
                      </p>
                    </div>
                  )}
                  <div>
                    <p className="text-xs text-text-secondary mb-1">Trials</p>
                    <p className="text-2xl font-mono font-bold">{assetResult.n_trials}</p>
                  </div>
                </div>

                <div>
                  <p className="text-xs text-text-secondary mb-2">Best Parameters:</p>
                  <pre className="bg-bg-primary p-3 border-3 border-border-primary overflow-x-auto text-xs font-mono">
                    {JSON.stringify(assetResult.best_params, null, 2)}
                  </pre>
                </div>
              </div>
            ))}
          </div>
        </Card>
      )}
    </div>
  );
};
