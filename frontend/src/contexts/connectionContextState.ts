import { createContext } from 'react';

export interface ConnectionContextType {
  isConnected: boolean;
  isConnecting: boolean;
  error: string | null;
  retryCount: number;
}

export const connectionContextDefault: ConnectionContextType = {
  isConnected: false,
  isConnecting: false,
  error: null,
  retryCount: 0,
};

export const ConnectionContext = createContext<ConnectionContextType>(connectionContextDefault);
