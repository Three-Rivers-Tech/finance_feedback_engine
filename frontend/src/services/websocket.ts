/**
 * WebSocket Service
 * Handles connection management, reconnection logic, and message routing
 */

import { API_BASE_URL } from '../utils/constants';
import { getEffectiveApiKey } from '../utils/auth';

export type WebSocketMessage<T = unknown> = {
  event: string;
  data: T;
  timestamp?: number;
};

export type WebSocketCallback<T = unknown> = (message: WebSocketMessage<T>) => void;

type ListenerMap = Map<string, Set<WebSocketCallback<unknown>>>;

interface WebSocketConfig {
  url: string;
  apiKey?: string;
  maxRetries?: number;
  initialDelay?: number;
  maxDelay?: number;
}

export class WebSocketService {
  private socket: WebSocket | null = null;
  private url: string;
  private apiKey?: string;
  private maxRetries: number;
  private initialDelay: number;
  private maxDelay: number;
  private retryCount = 0;
  private retryTimer: number | null = null;
  private listeners: ListenerMap = new Map();
  private isIntentionallyClosed = false;
  private connectionPromise: Promise<void> | null = null;
  private resolveConnection: (() => void) | null = null;
  private heartbeatTimer: number | null = null;
  private lastMessageTime = Date.now();

  constructor(config: WebSocketConfig) {
    this.url = config.url;
    this.apiKey = config.apiKey;
    this.maxRetries = config.maxRetries ?? 10;
    this.initialDelay = config.initialDelay ?? 1000;
    this.maxDelay = config.maxDelay ?? 30000;
  }

  public connect(): Promise<void> {
    if (this.socket?.readyState === WebSocket.OPEN || this.connectionPromise) {
      return this.connectionPromise || Promise.resolve();
    }

    this.isIntentionallyClosed = false;
    this.connectionPromise = new Promise((resolve) => {
      this.resolveConnection = resolve;
    });

    this._internalConnect();
    return this.connectionPromise;
  }

  private _internalConnect(): void {
    try {
      let wsUrl = this.url;

      const trimmed = wsUrl.replace(/\/+$/, '');
      const isAbsolute = /^https?:\/\//i.test(trimmed);
      const baseWithProtocol = isAbsolute ? trimmed : `${window.location.origin}${trimmed || ''}`;
      const wsBase = baseWithProtocol.replace(/^http/i, 'ws');
      wsUrl = wsBase;

      if (this.apiKey) {
        const separator = wsUrl.includes('?') ? '&' : '?';
        wsUrl = `${wsUrl}${separator}token=${encodeURIComponent(this.apiKey)}`;
      }

      this.socket = new WebSocket(wsUrl);

      this.socket.onopen = () => this._handleOpen();
      this.socket.onmessage = (event) => this._handleMessage(event);
      this.socket.onerror = () => this._handleError();
      this.socket.onclose = (event) => this._handleClose(event);
    } catch (err) {
      console.error('WebSocket connection error:', err);
      this._scheduleReconnect();
    }
  }

  private _handleOpen(): void {
    this.retryCount = 0;
    this.lastMessageTime = Date.now();
    this._startHeartbeat();

    if (this.resolveConnection) {
      this.resolveConnection();
      this.resolveConnection = null;
    }
    this.connectionPromise = null;

    this._emit('connected', { timestamp: Date.now() });
  }

  private _handleMessage(event: MessageEvent<string>): void {
    try {
      this.lastMessageTime = Date.now();
      const message = JSON.parse(event.data) as WebSocketMessage<unknown>;
      this._emit(message.event, message);
      this._emit('message', message);
    } catch (err) {
      console.warn('Failed to parse WebSocket message:', err);
    }
  }

  private _handleError(): void {
    this._emit('error', {
      message: 'WebSocket error',
      timestamp: Date.now(),
      readyState: this.socket?.readyState,
    });
  }

  private _handleClose(event?: CloseEvent): void {
    this._stopHeartbeat();

    if (event?.code === 4001) {
      this._emit('auth_failed', {
        message: event.reason || 'Unauthorized',
        code: event.code,
        timestamp: Date.now(),
      });
      this.isIntentionallyClosed = true;
    }

    this._emit('disconnected', {
      timestamp: Date.now(),
      code: event?.code,
      reason: event?.reason,
    });

    if (!this.isIntentionallyClosed) {
      this._scheduleReconnect();
    }
  }

  private _scheduleReconnect(): void {
    if (this.retryCount >= this.maxRetries) {
      this._emit('connection_failed', { message: 'Max retries reached' });
      return;
    }

    const delay = Math.min(this.initialDelay * 2 ** this.retryCount, this.maxDelay);
    this.retryCount += 1;

    this.retryTimer = window.setTimeout(() => {
      this._internalConnect();
    }, delay);
  }

  private _startHeartbeat(): void {
    this._stopHeartbeat();
    this.heartbeatTimer = window.setInterval(() => {
      const timeSinceLastMessage = Date.now() - this.lastMessageTime;
      if (timeSinceLastMessage > 30000 && this.socket?.readyState === WebSocket.OPEN) {
        this.send('ping', {});
      }
    }, 10000);
  }

  private _stopHeartbeat(): void {
    if (this.heartbeatTimer !== null) {
      clearInterval(this.heartbeatTimer);
      this.heartbeatTimer = null;
    }
  }

  public send(event: string, data: unknown): void {
    if (this.socket?.readyState === WebSocket.OPEN) {
      const message = event === 'ping' ? { event, data } : { action: event, payload: data };
      this.socket.send(JSON.stringify(message));
    }
  }

  public on<T = unknown>(event: string, callback: WebSocketCallback<T>): () => void {
    if (!this.listeners.has(event)) {
      this.listeners.set(event, new Set());
    }
    this.listeners.get(event)?.add(callback as WebSocketCallback<unknown>);
    return () => this.off(event, callback);
  }

  public off<T = unknown>(event: string, callback: WebSocketCallback<T>): void {
    this.listeners.get(event)?.delete(callback as WebSocketCallback<unknown>);
  }

  private _emit(event: string, data: unknown): void {
    const callbacks = this.listeners.get(event);
    callbacks?.forEach((callback) => {
      try {
        callback({ event, data });
      } catch (err) {
        console.error(`Error in WebSocket listener for ${event}:`, err);
      }
    });
  }

  public isConnected(): boolean {
    return this.socket?.readyState === WebSocket.OPEN;
  }

  public disconnect(): void {
    this.isIntentionallyClosed = true;
    this._stopHeartbeat();

    if (this.retryTimer !== null) {
      clearTimeout(this.retryTimer);
      this.retryTimer = null;
    }

    this.socket?.close();
    this.socket = null;
    this.listeners.clear();
    this.connectionPromise = null;
  }
}

let globalWebSocketService: WebSocketService | null = null;

export function getWebSocketService(): WebSocketService {
  if (!globalWebSocketService) {
    const apiKey = getEffectiveApiKey() ?? undefined;
    const baseUrl = (import.meta.env.VITE_API_BASE_URL || API_BASE_URL || '/api').replace(/\/+$/, '');
    const wsUrl = `${baseUrl}/api/v1/bot/ws`;

    globalWebSocketService = new WebSocketService({
      url: wsUrl,
      apiKey,
      maxRetries: 10,
      initialDelay: 1000,
      maxDelay: 30000,
    });
  }
  return globalWebSocketService;
}

export function resetWebSocketService(): void {
  globalWebSocketService?.disconnect();
  globalWebSocketService = null;
}
