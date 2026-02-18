/**
 * WebSocket Connection Status Context Provider
 */

import React from 'react';
import { useWebSocket } from '../api/hooks/useWebSocket';
import { ConnectionContext, type ConnectionContextType } from './connectionContextState';

interface ConnectionProviderProps {
  children: React.ReactNode;
}

export function ConnectionProvider({ children }: ConnectionProviderProps) {
  const { isConnected, error } = useWebSocket({
    onConnect: () => console.log('Connected to WebSocket'),
    onDisconnect: () => console.log('Disconnected from WebSocket'),
    onError: (err) => {
      if (err && typeof err === 'object' && 'message' in err) {
        console.error('WebSocket error:', (err as { message?: string }).message || JSON.stringify(err));
      } else {
        console.error('WebSocket error:', err);
      }
    },
  });

  const value: ConnectionContextType = {
    isConnected,
    isConnecting: !isConnected && !error,
    error,
    retryCount: 0,
  };

  return <ConnectionContext.Provider value={value}>{children}</ConnectionContext.Provider>;
}
