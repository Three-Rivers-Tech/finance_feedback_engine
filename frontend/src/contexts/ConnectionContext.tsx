/**
 * WebSocket Connection Status Context
 * Provides connection state and visual feedback to all components
 */

import React, { createContext, useContext } from 'react';
import { useWebSocket } from '../api/hooks/useWebSocket';

interface ConnectionContextType {
  isConnected: boolean;
  isConnecting: boolean;
  error: string | null;
  retryCount: number;
}

const ConnectionContext = createContext<ConnectionContextType>({
  isConnected: false,
  isConnecting: false,
  error: null,
  retryCount: 0,
});

export function useConnectionStatus() {
  const context = useContext(ConnectionContext);
  if (!context) {
    throw new Error('useConnectionStatus must be used within ConnectionProvider');
  }
  return context;
}

interface ConnectionProviderProps {
  children: React.ReactNode;
}

export function ConnectionProvider({ children }: ConnectionProviderProps) {
  const { isConnected, error } = useWebSocket({
    onConnect: () => console.log('Connected to WebSocket'),
    onDisconnect: () => console.log('Disconnected from WebSocket'),
    onError: (err) => {
      if (err && typeof err === 'object') {
        console.error('WebSocket error:', err.message || JSON.stringify(err), '| Full error:', err);
      } else {
        console.error('WebSocket error:', err);
      }
    },
  });

  const value: ConnectionContextType = {
    isConnected,
    isConnecting: !isConnected && !error,
    error,
    retryCount: 0, // Could track from service if needed
  };

  return <ConnectionContext.Provider value={value}>{children}</ConnectionContext.Provider>;
}
