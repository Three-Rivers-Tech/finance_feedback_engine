/**
 * useWebSocket Hook
 * Provides easy subscription to WebSocket events with automatic cleanup
 */

import { useEffect, useState, useRef, useCallback } from 'react';
import { getWebSocketService, type WebSocketMessage, type WebSocketService } from '../../services/websocket';

interface UseWebSocketOptions {
  enabled?: boolean;
  onConnect?: () => void;
  onDisconnect?: () => void;
  onError?: (error: unknown) => void;
}

export function useWebSocket(options: UseWebSocketOptions = {}) {
  const { enabled = true, onConnect, onDisconnect, onError } = options;
  const [isConnected, setIsConnected] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [service] = useState<WebSocketService>(() => getWebSocketService());
  const unsubscribeRef = useRef<(() => void)[]>([]);

  useEffect(() => {
    if (!enabled) return;

    let isMounted = true;

    const handleConnect = () => {
      if (!isMounted) return;
      setIsConnected(true);
      setError(null);
      onConnect?.();
    };

    const handleDisconnect = () => {
      if (!isMounted) return;
      setIsConnected(false);
      onDisconnect?.();
    };

    const handleError = (message: WebSocketMessage<{ message?: string }>) => {
      if (!isMounted) return;
      const errorMsg = message.data?.message || 'WebSocket error';
      setError(errorMsg);
      onError?.(message.data);
    };

    const handleConnectionFailed = (message: WebSocketMessage<{ message?: string }>) => {
      if (!isMounted) return;
      const errorMsg = message.data?.message || 'Failed to connect after max retries';
      setError(errorMsg);
      onError?.(message.data);
    };

    unsubscribeRef.current.push(service.on('connected', handleConnect));
    unsubscribeRef.current.push(service.on('disconnected', handleDisconnect));
    unsubscribeRef.current.push(service.on('error', handleError));
    unsubscribeRef.current.push(service.on('connection_failed', handleConnectionFailed));

    service.connect().catch((err: Error) => {
      if (!isMounted) return;
      setError(err.message || 'Failed to connect');
      onError?.(err);
    });

    return () => {
      isMounted = false;
      unsubscribeRef.current.forEach((unsub) => unsub());
      unsubscribeRef.current = [];
    };
  }, [enabled, onConnect, onDisconnect, onError, service]);

  const subscribe = useCallback(
    <T = unknown,>(event: string, callback: (message: WebSocketMessage<T>) => void) => service.on(event, callback),
    [service]
  );

  const send = useCallback((event: string, data: unknown) => {
    service.send(event, data);
  }, [service]);

  return {
    isConnected,
    error,
    subscribe,
    send,
    service,
  };
}
