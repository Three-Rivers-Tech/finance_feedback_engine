/**
 * useWebSocket Hook
 * Provides easy subscription to WebSocket events with automatic cleanup
 */

import { useEffect, useState, useRef, useCallback } from 'react';
import { getWebSocketService, type WebSocketMessage } from '../../services/websocket';

interface UseWebSocketOptions {
  enabled?: boolean;
  onConnect?: () => void;
  onDisconnect?: () => void;
  onError?: (error: any) => void;
}

export function useWebSocket(options: UseWebSocketOptions = {}) {
  const { enabled = true, onConnect, onDisconnect, onError } = options;
  const [isConnected, setIsConnected] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const onErrorCallback = useRef<((err: any) => void) | undefined>(onError);
  const serviceRef = useRef(getWebSocketService());

  // Update callback ref when onError changes
  useEffect(() => {
    onErrorCallback.current = onError;
  }, [onError]);
  const unsubscribeRef = useRef<(() => void)[]>([]);

  // Connect on mount
  useEffect(() => {
    if (!enabled) return;

    const service = serviceRef.current;
    let isMounted = true;

    const handleConnect = () => {
      if (isMounted) {
        setIsConnected(true);
        setError(null);
        onConnect?.();
      }
    };

    const handleDisconnect = () => {
      if (isMounted) {
        setIsConnected(false);
        onDisconnect?.();
      }
    };

    const handleError = (message: WebSocketMessage) => {
      if (isMounted) {
        const errorMsg = message.data?.message || 'WebSocket error';
        setError(errorMsg);
        onError?.(message.data);
      }
    };

    const handleConnectionFailed = (message: WebSocketMessage) => {
      if (isMounted) {
        const errorMsg = message.data?.message || 'Failed to connect after max retries';
        setError(errorMsg);
        onError?.(message.data);
      }
    };

    // Subscribe to connection events
    unsubscribeRef.current.push(service.on('connected', handleConnect));
    unsubscribeRef.current.push(service.on('disconnected', handleDisconnect));
    unsubscribeRef.current.push(service.on('error', handleError));
    unsubscribeRef.current.push(service.on('connection_failed', handleConnectionFailed));

    // Initialize connection
    service.connect().catch((err) => {
      if (isMounted) {
        setError(err.message || 'Failed to connect');
        onError?.(err);
      }
    });

    return () => {
      isMounted = false;
      // Clean up subscriptions but keep service alive
      unsubscribeRef.current.forEach((unsub) => unsub());
      unsubscribeRef.current = [];
    };
  }, [enabled, onConnect, onDisconnect, onError]);

  // Subscribe to specific event
  const subscribe = useCallback(
    <T = any,>(event: string, callback: (message: WebSocketMessage<T>) => void) => {
      const service = serviceRef.current;
      return service.on(event, callback);
    },
    []
  );

  // Send message
  const send = useCallback((event: string, data: any) => {
    serviceRef.current.send(event, data);
  }, []);

  return {
    isConnected,
    error,
    subscribe,
    send,
    service: serviceRef.current,
  };
}
