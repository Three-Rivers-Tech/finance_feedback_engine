import React from 'react';
import { AlertTriangle, AlertCircle, CheckCircle } from 'lucide-react';
import type { OllamaComponent } from '../../api/types';

interface OllamaStatusAlertProps {
  ollama: OllamaComponent;
}

export const OllamaStatusAlert: React.FC<OllamaStatusAlertProps> = ({ ollama }) => {
  // Don't show anything if Ollama is healthy
  if (ollama.status === 'healthy') {
    return null;
  }

  const getAlertConfig = () => {
    if (ollama.status === 'unavailable' || ollama.error) {
      return {
        icon: AlertCircle,
        bgColor: 'bg-red-900/20',
        borderColor: 'border-red-500',
        iconColor: 'text-red-400',
        title: 'Ollama Not Available',
        message: ollama.error || 'Cannot connect to Ollama service',
        action: 'Run ./scripts/setup-ollama.sh to install',
        severity: 'error' as const,
      };
    }

    if (ollama.status === 'degraded' || (ollama.models_missing && ollama.models_missing.length > 0)) {
      return {
        icon: AlertTriangle,
        bgColor: 'bg-yellow-900/20',
        borderColor: 'border-yellow-500',
        iconColor: 'text-yellow-400',
        title: 'Missing Required Models',
        message: `Models not installed: ${ollama.models_missing.join(', ')}`,
        action: 'Run ./scripts/pull-ollama-models.sh to download',
        severity: 'warning' as const,
      };
    }

    return null;
  };

  const config = getAlertConfig();

  if (!config) return null;

  const Icon = config.icon;

  return (
    <div
      className={`${config.bgColor} border ${config.borderColor} rounded-lg p-4 mb-6`}
      role="alert"
      aria-live="polite"
    >
      <div className="flex items-start gap-3">
        <Icon className={`w-5 h-5 ${config.iconColor} flex-shrink-0 mt-0.5`} />
        <div className="flex-1">
          <h3 className="font-mono font-bold text-sm mb-1 text-white">
            {config.title}
          </h3>
          <p className="text-sm text-gray-300 mb-2">
            {config.message}
          </p>
          <div className="flex flex-col gap-2">
            <code className="text-xs bg-black/30 px-3 py-2 rounded font-mono text-accent-cyan">
              {config.action}
            </code>
            {ollama.models_loaded && ollama.models_loaded.length > 0 && (
              <div className="text-xs text-gray-400 flex items-center gap-2">
                <CheckCircle className="w-3 h-3 text-green-400" />
                <span>Models loaded: {ollama.models_loaded.join(', ')}</span>
              </div>
            )}
            {ollama.warning && (
              <p className="text-xs text-gray-400 mt-1">
                {ollama.warning}
              </p>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};
