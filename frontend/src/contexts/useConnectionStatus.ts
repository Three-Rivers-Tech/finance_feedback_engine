import { useContext } from 'react';
import { ConnectionContext } from './connectionContextState';

export function useConnectionStatus() {
  return useContext(ConnectionContext);
}
