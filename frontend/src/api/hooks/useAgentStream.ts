import { useEffect, useRef, useState } from 'react';
import { API_BASE_URL } from '../../utils/constants';
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
}

export function useAgentStream(): AgentStreamState {
  const [status, setStatus] = useState<AgentStatus | null>(null);
  const [events, setEvents] = useState<AgentStreamEvent[]>([]);
  const [isConnected, setIsConnected] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const retryRef = useRef<number | null>(null);

  useEffect(() => {
    let isCancelled = false;
    const controller = new AbortController();

    const connect = async () => {
      // Clear any pending retry timers
      if (retryRef.current) {
        clearTimeout(retryRef.current);
        retryRef.current = null;
      }

      try {
        const apiKey = localStorage.getItem('api_key') || import.meta.env.VITE_API_KEY;
        const headers: Record<string, string> = {};
        if (apiKey) {
          headers.Authorization = `Bearer ${apiKey}`;
        }

        const response = await fetch(`${API_BASE_URL}/api/v1/bot/stream`, {
          method: 'GET',
          headers,
          signal: controller.signal,
        });

        if (!response.ok || !response.body) {
          throw new Error(`Stream error: ${response.status}`);
        }

        setIsConnected(true);
        setError(null);

        const reader = response.body.getReader();
        const decoder = new TextDecoder('utf-8');
        let buffer = '';

        while (!isCancelled) {
          const { value, done } = await reader.read();
          if (done) break;

          buffer += decoder.decode(value, { stream: true });
          const chunks = buffer.split('\n\n');
          buffer = chunks.pop() ?? '';

          for (const chunk of chunks) {
            const line = chunk.trim();
            if (!line.startsWith('data:')) continue;
            const payload = line.replace(/^data:\s*/, '');
            try {
              const parsed: AgentStreamEvent = JSON.parse(payload);
              if (parsed.event === 'status') {
                setStatus(parsed.data as AgentStatus);
                continue;
              }
              if (parsed.event === 'heartbeat') {
                continue;
              }
              setEvents((prev) => {
                const next = [...prev, parsed];
                // Keep a rolling window of the last 50 events
                return next.slice(-50);
              });
            } catch (err) {
              console.warn('Failed to parse stream payload', err);
            }
          }
        }
      } catch (err) {
        if (isCancelled || controller.signal.aborted) {
          return;
        }
        setIsConnected(false);
        setError((err as Error).message);
        // Retry with backoff
        retryRef.current = window.setTimeout(connect, 3000);
      }
    };

    connect();

    return () => {
      isCancelled = true;
      controller.abort();
      if (retryRef.current) {
        clearTimeout(retryRef.current);
        retryRef.current = null;
      }
    };
  }, []);

  return { status, events, isConnected, error };
}
