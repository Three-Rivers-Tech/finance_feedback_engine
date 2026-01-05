/**
 * Connection Status Indicator
 * Visual feedback for WebSocket connection state
 */

import React from 'react';
import { useConnectionStatus } from '../contexts/ConnectionContext';
import { Spinner } from './common/Spinner';
import clsx from 'clsx';

interface ConnectionStatusProps {
  compact?: boolean;
}

export const ConnectionStatus: React.FC<ConnectionStatusProps> = ({ compact = false }) => {
  const { isConnected, isConnecting, error } = useConnectionStatus();

  if (isConnected) {
    return (
      <div
        className={clsx(
          'flex items-center gap-2 text-green-600',
          compact ? 'text-xs' : 'text-sm'
        )}
        title="WebSocket connected - real-time updates active"
      >
        <div className="w-2 h-2 bg-green-600 rounded-full animate-pulse" />
        {!compact && <span>Connected</span>}
      </div>
    );
  }

  if (isConnecting) {
    return (
      <div
        className={clsx(
          'flex items-center gap-2 text-yellow-600',
          compact ? 'text-xs' : 'text-sm'
        )}
        title="Connecting to WebSocket..."
      >
        <Spinner size="sm" />
        {!compact && <span>Connecting...</span>}
      </div>
    );
  }

  if (error) {
    return (
      <div
        className={clsx(
          'flex items-center gap-2 text-red-600',
          compact ? 'text-xs' : 'text-sm'
        )}
        title={`Connection error: ${error}`}
      >
        <div className="w-2 h-2 bg-red-600 rounded-full" />
        {!compact && <span className="truncate">Error: {error}</span>}
      </div>
    );
  }

  return null;
};

/**
 * Floating connection status indicator
 * Shows in corner of screen
 */
export const FloatingConnectionStatus: React.FC = () => {
  const { isConnected, isConnecting, error } = useConnectionStatus();

  return (
    <div className="fixed bottom-4 left-4 z-50 bg-white rounded-lg shadow-md p-3 border border-gray-200">
      <div className="flex items-center gap-2">
        {isConnected && (
          <>
            <div className="w-2.5 h-2.5 bg-green-600 rounded-full animate-pulse" />
            <span className="text-xs font-medium text-green-700">Live Updates</span>
          </>
        )}
        {isConnecting && (
          <>
            <Spinner size="sm" />
            <span className="text-xs font-medium text-yellow-700">Connecting...</span>
          </>
        )}
        {error && (
          <>
            <div className="w-2.5 h-2.5 bg-red-600 rounded-full" />
            <span className="text-xs font-medium text-red-700">Offline</span>
          </>
        )}
      </div>
    </div>
  );
};

/**
 * Minimalist indicator badge
 */
export const ConnectionBadge: React.FC = () => {
  const { isConnected, isConnecting, error } = useConnectionStatus();

  if (!isConnected && !isConnecting && !error) {
    return null;
  }

  const bgColor = isConnected ? 'bg-green-100' : isConnecting ? 'bg-yellow-100' : 'bg-red-100';
  const textColor = isConnected ? 'text-green-800' : isConnecting ? 'text-yellow-800' : 'text-red-800';
  const dotColor = isConnected ? 'bg-green-500' : isConnecting ? 'bg-yellow-500' : 'bg-red-500';

  return (
    <span className={clsx('inline-flex items-center gap-1.5 px-2 py-1 rounded-full text-xs font-medium', bgColor, textColor)}>
      <span className={clsx('inline-block w-1.5 h-1.5 rounded-full', dotColor)} />
      {isConnected && 'Live'}
      {isConnecting && 'Syncing'}
      {error && 'Offline'}
    </span>
  );
};
