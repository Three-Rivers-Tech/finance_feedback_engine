/**
 * WebSocket Service
 * Handles connection management, reconnection logic, and message routing
 */

import { API_BASE_URL } from '../utils/constants';

export type WebSocketMessage<T = any> = {
  event: string;
  data: T;
  timestamp?: number;
};

export type WebSocketCallback<T = any> = (message: WebSocketMessage<T>) => void;

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
  private retryCount: number = 0;
  private retryTimer: number | null = null;
  private listeners: Map<string, Set<WebSocketCallback>> = new Map();
  private isIntentionallyClosed: boolean = false;
  private connectionPromise: Promise<void> | null = null;
  private resolveConnection: (() => void) | null = null;
  private heartbeatTimer: number | null = null;
  private lastMessageTime: number = Date.now();

  constructor(config: WebSocketConfig) {
    this.url = config.url;
    this.apiKey = config.apiKey;
    this.maxRetries = config.maxRetries ?? 10;
    this.initialDelay = config.initialDelay ?? 1000;
    this.maxDelay = config.maxDelay ?? 30000;
  }

  /**
   * Connect to WebSocket with automatic reconnection
   */
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

      // Normalize and upgrade to ws/wss
      const trimmed = wsUrl.replace(/\/+$/, '');
      const isAbsolute = /^https?:\/\//i.test(trimmed);
      const baseWithProtocol = isAbsolute ? trimmed : `${window.location.origin}${trimmed || ''}`;
      const wsBase = baseWithProtocol.replace(/^http/i, 'ws');
      wsUrl = wsBase;

      // Append API key as query parameter
      if (this.apiKey) {
        const separator = wsUrl.includes('?') ? '&' : '?';
        wsUrl = `${wsUrl}${separator}token=${encodeURIComponent(this.apiKey)}`;
      }

      this.socket = new WebSocket(wsUrl);

      this.socket.onopen = () => this._handleOpen();
      this.socket.onmessage = (event) => this._handleMessage(event);
      this.socket.onerror = () => this._handleError();
      this.socket.onclose = () => this._handleClose();
    } catch (err) {
      console.error('WebSocket connection error:', err);
      this._scheduleReconnect();
    }
  }

  private _handleOpen(): void {
    console.log('[WebSocket] Connected');
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
      const message: WebSocketMessage = JSON.parse(event.data);

      // Emit to specific event listeners
      this._emit(message.event, message);

      // Always emit raw message
      this._emit('message', message);
    } catch (err) {
      console.warn('Failed to parse WebSocket message:', err);
    }
  }

  private _handleError(): void {
    console.error('[WebSocket] Error encountered');
    console.error('[WebSocket] Connection state:', {
      readyState: this.socket?.readyState,
      url: this.socket?.url,
      retryCount: this.retryCount,
      maxRetries: this.maxRetries,
    });
    this._emit('error', { 
      message: 'WebSocket error', 
      timestamp: Date.now(),
      readyState: this.socket?.readyState,
    });
  }

  private _handleClose(): void {
    console.log('[WebSocket] Disconnected');
    this._stopHeartbeat();
    this._emit('disconnected', { timestamp: Date.now() });

    if (!this.isIntentionallyClosed) {
      this._scheduleReconnect();
    }
  }

  private _scheduleReconnect(): void {
    if (this.retryCount >= this.maxRetries) {
      console.error(`[WebSocket] Max retries (${this.maxRetries}) reached`);
      this._emit('connection_failed', { message: 'Max retries reached' });
      return;
    }

    const delay = Math.min(
      this.initialDelay * Math.pow(2, this.retryCount),
      this.maxDelay
    );
    this.retryCount++;

    console.log(`[WebSocket] Reconnecting in ${delay}ms (attempt ${this.retryCount}/${this.maxRetries})`);
    this.retryTimer = window.setTimeout(() => {
      this._internalConnect();
    }, delay);
  }

  private _startHeartbeat(): void {
    this._stopHeartbeat();
    this.heartbeatTimer = window.setInterval(() => {
      const timeSinceLastMessage = Date.now() - this.lastMessageTime;
      // Ping if no message for 30 seconds
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

  /**
   * Send a message over WebSocket
   * Note: Server expects { action, payload } format for commands
   */
  public send(event: string, data: any): void {
    if (this.socket?.readyState === WebSocket.OPEN) {
      // Server expects { action, payload } for commands like 'start', 'stop', etc.
      // but sends { event, data } for broadcasts
      const message = event === 'ping' 
        ? { event, data }  // Keep heartbeat as { event, data }
        : { action: event, payload: data };  // Commands use { action, payload }
      this.socket.send(JSON.stringify(message));
    } else {
      console.warn('[WebSocket] Cannot send - socket not open');
    }
  }

  /**
   * Subscribe to specific event type
   */
  public on<T = any>(event: string, callback: WebSocketCallback<T>): () => void {
    if (!this.listeners.has(event)) {
      this.listeners.set(event, new Set());
    }
    this.listeners.get(event)!.add(callback);

    // Return unsubscribe function
    return () => this.off(event, callback);
  }

  /**
   * Unsubscribe from event
   */
  public off(event: string, callback: WebSocketCallback): void {
    this.listeners.get(event)?.delete(callback);
  }

  /**
   * Emit event to all listeners
   */
  private _emit(event: string, data: any): void {
    const callbacks = this.listeners.get(event);
    if (callbacks) {
      callbacks.forEach((callback) => {
        try {
          callback({ event, data });
        } catch (err) {
          console.error(`Error in WebSocket listener for ${event}:`, err);
        }
      });
    }
  }

  /**
   * Get current connection state
   */
  public isConnected(): boolean {
    return this.socket?.readyState === WebSocket.OPEN;
  }

  /**
   * Disconnect and close all listeners
   */
  public disconnect(): void {
    this.isIntentionallyClosed = true;
    this._stopHeartbeat();

    if (this.retryTimer !== null) {
      clearTimeout(this.retryTimer);
      this.retryTimer = null;
    }

    if (this.socket) {
      this.socket.close();
      this.socket = null;
    }

    this.listeners.clear();
    this.connectionPromise = null;
  }
}

/**
 * Create singleton WebSocket instance
 */
let globalWebSocketService: WebSocketService | null = null;

export function getWebSocketService(): WebSocketService {
  if (!globalWebSocketService) {
    const apiKey = localStorage.getItem('api_key') || import.meta.env.VITE_API_KEY;
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

/**
 * Reset global WebSocket service (useful for testing)
 */
export function resetWebSocketService(): void {
  globalWebSocketService?.disconnect();
  globalWebSocketService = null;
}
