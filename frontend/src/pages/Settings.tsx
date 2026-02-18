import React, { useState } from 'react';
import apiClient, { handleApiError } from '../api/client';
import {
  clearStoredApiKey,
  getEffectiveApiKey,
  getEnvApiKey,
  getStoredApiKey,
  setStoredApiKey,
} from '../utils/auth';
import { resetWebSocketService } from '../services/websocket';

export const Settings: React.FC = () => {
  const [apiKeyInput, setApiKeyInput] = useState('');
  const [notice, setNotice] = useState<string | null>(null);
  const [testing, setTesting] = useState(false);

  const stored = getStoredApiKey();
  const env = getEnvApiKey();
  const effective = getEffectiveApiKey();
  const authStatus = {
    hasStored: Boolean(stored),
    hasEnv: Boolean(env),
    hasEffective: Boolean(effective),
    source: stored ? 'localStorage' : env ? 'environment' : 'none',
  };

  const saveApiKey = () => {
    try {
      setStoredApiKey(apiKeyInput);
      setApiKeyInput('');
      resetWebSocketService();
      setNotice('API key saved. Reconnect complete.');
    } catch (error) {
      setNotice(error instanceof Error ? error.message : 'Failed to save API key.');
    }
  };

  const clearApiKey = () => {
    clearStoredApiKey();
    resetWebSocketService();
    setNotice('Stored API key removed.');
  };

  const testAuth = async () => {
    setTesting(true);
    setNotice(null);
    try {
      await apiClient.get('/api/v1/bot/status');
      setNotice('Auth test passed. API access is working.');
    } catch (error) {
      setNotice(`Auth test failed: ${handleApiError(error)}`);
    } finally {
      setTesting(false);
    }
  };

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-mono font-bold text-accent-cyan uppercase">Settings</h1>

      <div className="border-3 border-border-primary bg-bg-secondary rounded p-4 space-y-3">
        <h2 className="font-mono text-sm text-text-primary">API Authentication</h2>
        <div className="text-xs font-mono text-text-secondary space-y-1">
          <p>Effective key: {authStatus.hasEffective ? 'YES' : 'NO'}</p>
          <p>Source: {authStatus.source}</p>
          <p>Stored key present: {authStatus.hasStored ? 'YES' : 'NO'}</p>
          <p>Environment key present: {authStatus.hasEnv ? 'YES' : 'NO'}</p>
        </div>

        <div className="flex flex-col md:flex-row gap-2 md:items-center">
          <input
            type="password"
            value={apiKeyInput}
            onChange={(e) => setApiKeyInput(e.target.value)}
            placeholder="Paste API key"
            className="px-3 py-2 bg-bg-primary border-3 border-border-primary rounded text-sm font-mono md:min-w-[360px]"
          />
          <button
            type="button"
            onClick={saveApiKey}
            disabled={!apiKeyInput.trim()}
            className="px-3 py-2 border-3 border-border-primary rounded font-mono text-xs hover:border-accent-cyan disabled:opacity-60"
          >
            Save API Key
          </button>
          <button
            type="button"
            onClick={clearApiKey}
            className="px-3 py-2 border-3 border-border-primary rounded font-mono text-xs hover:border-accent-red"
          >
            Clear Stored Key
          </button>
          <button
            type="button"
            onClick={testAuth}
            disabled={testing}
            className="px-3 py-2 border-3 border-border-primary rounded font-mono text-xs hover:border-accent-cyan disabled:opacity-60"
          >
            {testing ? 'Testing…' : 'Test API Access'}
          </button>
        </div>

        <p className="text-xs font-mono text-text-secondary">
          If auth fails, set a real API key here. Placeholder keys are ignored automatically.
        </p>
      </div>

      {notice && (
        <div className="border-3 border-border-primary bg-bg-secondary rounded p-3 text-xs font-mono text-text-primary">
          {notice}
        </div>
      )}
    </div>
  );
};
