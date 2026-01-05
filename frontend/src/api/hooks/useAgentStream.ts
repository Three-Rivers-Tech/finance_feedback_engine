import { useEffect, useRef, useState } from 'react';
import { getWebSocketService, type WebSocketMessage } from '../../services/websocket';
import type { AgentStatus } from '../types';

export type AgentStreamEvent = {
  event: string;
  data: any;
};

interface AgentStreamState {
  status: AgentStatus | null;
  events: AgentStreamEvent[];
  isConnected: boolean;
  error: string | null;
  canSendCommands: boolean;
  startInFlight: boolean;
  lastStartAck: AgentStreamEvent | null;
  sendStart?: (payload: { autonomous: boolean; asset_pairs: string[] }) => Promise<void>;
}

export function useAgentStream(): AgentStreamState {
  const [status, setStatus] = useState<AgentStatus | null>(null);
  const [events, setEvents] = useState<AgentStreamEvent[]>([]);
  const [isConnected, setIsConnected] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [canSendCommands, setCanSendCommands] = useState(false);
  const [startInFlight, setStartInFlight] = useState(false);
  const [lastStartAck, setLastStartAck] = useState<AgentStreamEvent | null>(null);
  const unsubscribersRef = useRef<(() => void)[]>([]);
  const wsServiceRef = useRef(getWebSocketService());

  useEffect(() => {
    let isCancelled = false;
    const service = wsServiceRef.current;

    // Clean up previous subscriptions
    unsubscribersRef.current.forEach((unsub) => unsub());
    unsubscribersRef.current = [];

    // Connect and set up event listeners
    service.connect().catch((err) => {
      if (!isCancelled) {
        console.error('Failed to connect:', err);
        setError(err.message || 'Failed to connect');
      }
    });

    // Subscribe to connection events
    unsubscribersRef.current.push(
      service.on('connected', () => {
        if (!isCancelled) {
          setIsConnected(true);
          setCanSendCommands(true);
          setError(null);
        }
      })
    );

    unsubscribersRef.current.push(
      service.on('disconnected', () => {
        if (!isCancelled) {
          setIsConnected(false);
          setCanSendCommands(false);
        }
      })
    );

    unsubscribersRef.current.push(
      service.on('error', (msg: WebSocketMessage) => {
        if (!isCancelled) {
          setError(msg.data?.message || 'WebSocket error');
        }
      })
    );

    unsubscribersRef.current.push(
      service.on('connection_failed', (msg: WebSocketMessage) => {
        if (!isCancelled) {
          setError(msg.data?.message || 'Failed to connect after max retries');
        }
      })
    );

    // Subscribe to agent-specific events
    unsubscribersRef.current.push(
      service.on('status', (msg: WebSocketMessage) => {
        if (!isCancelled) {
          setStatus(msg.data as AgentStatus);
        }
      })
    );

    unsubscribersRef.current.push(
      service.on('start_ack', (msg: WebSocketMessage) => {
        if (!isCancelled) {
          setLastStartAck({ event: 'start_ack', data: msg.data });
          setStartInFlight(false);
        }
      })
    );

    unsubscribersRef.current.push(
      service.on('state_transition', (msg: WebSocketMessage) => {
        if (!isCancelled) {
          setEvents((prev) => {
            const next = [...prev, { event: 'state_transition', data: msg.data }];
            return next.slice(-50);
          });
        }
      })
    );

    unsubscribersRef.current.push(
      service.on('decision_made', (msg: WebSocketMessage) => {
        if (!isCancelled) {
          setEvents((prev) => {
            const next = [...prev, { event: 'decision_made', data: msg.data }];
            return next.slice(-50);
          });
        }
      })
    );

    unsubscribersRef.current.push(
      service.on('trade_executed', (msg: WebSocketMessage) => {
        if (!isCancelled) {
          setEvents((prev) => {
            const next = [...prev, { event: 'trade_executed', data: msg.data }];
            return next.slice(-50);
          });
        }
      })
    );

    unsubscribersRef.current.push(
      service.on('position_closed', (msg: WebSocketMessage) => {
        if (!isCancelled) {
          setEvents((prev) => {
            const next = [...prev, { event: 'position_closed', data: msg.data }];
            return next.slice(-50);
          });
        }
      })
    );

    unsubscribersRef.current.push(
      service.on('error', (msg: WebSocketMessage) => {
        if (!isCancelled) {
          setEvents((prev) => {
            const next = [...prev, { event: 'error', data: msg.data }];
            return next.slice(-50);
          });
        }
      })
    );

    return () => {
      isCancelled = true;
      // Unsubscribe from all events but keep service alive
      unsubscribersRef.current.forEach((unsub) => unsub());
      unsubscribersRef.current = [];
    };
  }, []);

  const sendStart = async (payload: { autonomous: boolean; asset_pairs: string[] }) => {
    if (!isConnected) {
      throw new Error('WebSocket not connected');
    }
    setStartInFlight(true);
    wsServiceRef.current.send('start', payload);
  };

  return { status, events, isConnected, error, canSendCommands, startInFlight, lastStartAck, sendStart };
}
