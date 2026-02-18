import { useEffect, useRef, useState } from 'react';
import { getWebSocketService, type WebSocketMessage } from '../../services/websocket';
import type { AgentStatus } from '../types';

export type AgentStreamEvent = {
  event: string;
  data: Record<string, unknown>;
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

    unsubscribersRef.current.forEach((unsub) => unsub());
    unsubscribersRef.current = [];

    service.connect().catch((err: Error) => {
      if (!isCancelled) {
        setError(err.message || 'Failed to connect');
      }
    });

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
      service.on<{ message?: string }>('error', (msg) => {
        if (!isCancelled) {
          setError(msg.data?.message || 'WebSocket error');
        }
      })
    );

    unsubscribersRef.current.push(
      service.on<{ message?: string }>('connection_failed', (msg) => {
        if (!isCancelled) {
          setError(msg.data?.message || 'Failed to connect after max retries');
        }
      })
    );

    unsubscribersRef.current.push(
      service.on('status', (msg: WebSocketMessage<AgentStatus>) => {
        if (!isCancelled) {
          setStatus(msg.data);
        }
      })
    );

    unsubscribersRef.current.push(
      service.on<Record<string, unknown>>('start_ack', (msg) => {
        if (!isCancelled) {
          setLastStartAck({ event: 'start_ack', data: msg.data });
          setStartInFlight(false);
        }
      })
    );

    const appendEvent = (eventName: string, msg: WebSocketMessage<Record<string, unknown>>) => {
      if (isCancelled) return;
      setEvents((prev) => [...prev, { event: eventName, data: msg.data }].slice(-50));
    };

    unsubscribersRef.current.push(service.on<Record<string, unknown>>('state_transition', (msg) => appendEvent('state_transition', msg)));
    unsubscribersRef.current.push(service.on<Record<string, unknown>>('decision_made', (msg) => appendEvent('decision_made', msg)));
    unsubscribersRef.current.push(service.on<Record<string, unknown>>('trade_executed', (msg) => appendEvent('trade_executed', msg)));
    unsubscribersRef.current.push(service.on<Record<string, unknown>>('position_closed', (msg) => appendEvent('position_closed', msg)));
    unsubscribersRef.current.push(service.on<Record<string, unknown>>('error', (msg) => appendEvent('error', msg)));

    return () => {
      isCancelled = true;
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
