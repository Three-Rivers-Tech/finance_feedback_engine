# Real-Time WebSocket Migration Guide

## Overview

This guide explains the new real-time WebSocket + React Query system that replaces the 5-second polling approach. The system provides smooth, responsive updates to all UI components.

## Key Changes

### 1. **WebSocket Service Layer** (`frontend/src/services/websocket.ts`)

Central singleton service managing WebSocket connections with:
- Automatic reconnection with exponential backoff
- Message routing to subscribed listeners
- Heartbeat monitoring
- Connection state tracking

**Features:**
- Exponential backoff: 1s → 2s → 4s → ... → 30s max
- Max 10 reconnect attempts
- Automatic heartbeat ping if no messages for 30s
- Thread-safe listener management

### 2. **Connection Context** (`frontend/src/contexts/ConnectionContext.tsx`)

Global connection status available to all components via React Context.

```tsx
import { useConnectionStatus } from '@/contexts/ConnectionContext';

function MyComponent() {
  const { isConnected, isConnecting, error } = useConnectionStatus();
  
  return (
    <div>
      {isConnected && <span>✓ Live Updates</span>}
      {isConnecting && <span>⟳ Syncing...</span>}
      {error && <span>✗ Offline: {error}</span>}
    </div>
  );
}
```

### 3. **Real-Time React Query Hooks** (`frontend/src/api/hooks/useRealTime.ts`)

New hooks for real-time data:

```tsx
import {
  usePortfolioRealTime,
  usePositionsRealTime,
  useDecisionsRealTime,
} from '@/api/hooks/useRealTime';

function Dashboard() {
  // Real-time portfolio with WebSocket push updates
  const portfolio = usePortfolioRealTime(true);
  
  // Real-time positions
  const positions = usePositionsRealTime(true);
  
  // Real-time decisions
  const decisions = useDecisionsRealTime(true, 20);
  
  return (
    <>
      {portfolio.data && <PortfolioCard data={portfolio.data} />}
      {positions.data && <PositionsTable data={positions.data} />}
      {decisions.data && <DecisionsList decisions={decisions.data} />}
    </>
  );
}
```

### 4. **Connection Status Indicators** (`frontend/src/components/ConnectionStatus.tsx`)

Three UI components for connection feedback:

```tsx
// Full status with text
import { ConnectionStatus } from '@/components/ConnectionStatus';
<ConnectionStatus />  // → "Connected" with green dot

// Floating indicator in corner
import { FloatingConnectionStatus } from '@/components/ConnectionStatus';
<FloatingConnectionStatus />

// Compact badge
import { ConnectionBadge } from '@/components/ConnectionStatus';
<ConnectionBadge />  // → "Live" badge
```

## Migration Steps for Components

### Step 1: Import Real-Time Hooks

Replace polling hooks with real-time versions:

```tsx
// Before (polling every 5s)
import { usePortfolio } from '@/api/hooks/usePortfolio';
const portfolio = usePortfolio(enabled);

// After (WebSocket-backed, instant updates)
import { usePortfolioRealTime } from '@/api/hooks/useRealTime';
const portfolio = usePortfolioRealTime(enabled);
```

### Step 2: Update Component Usage

The APIs are identical, so components work without changes:

```tsx
export const PortfolioCard: React.FC = () => {
  const { data, isLoading, error } = usePortfolioRealTime();
  
  if (isLoading) return <Spinner />;
  if (error) return <ErrorAlert error={error} />;
  if (!data) return null;
  
  return (
    <Card>
      <h3>Portfolio: ${data.portfolio_value.toFixed(2)}</h3>
      <p>Positions: {data.active_positions}</p>
    </Card>
  );
};
```

### Step 3: Add Connection Status Indicator

Include connection feedback in your layout:

```tsx
import { ConnectionBadge } from '@/components/ConnectionStatus';

export const AppLayout: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  return (
    <div className="app">
      <header className="flex justify-between items-center">
        <h1>Trading Dashboard</h1>
        <ConnectionBadge />
      </header>
      {children}
    </div>
  );
};
```

## Backend WebSocket Endpoints

New endpoints for real-time streaming:

```
ws://localhost:8000/api/v1/bot/ws
  └─ Primary agent event stream (already existed)
     → Emits: state_transition, decision_made, trade_executed, position_closed, etc.

ws://localhost:8000/api/v1/bot/ws/portfolio
  └─ Portfolio status updates (NEW)
     → Emits: portfolio_update every 2s

ws://localhost:8000/api/v1/bot/ws/positions
  └─ Position open/update/close events (NEW)
     → Emits: positions_update every 2s

ws://localhost:8000/api/v1/bot/ws/decisions
  └─ New decision events (NEW)
     → Emits: decision_made every 1s
```

All endpoints require Bearer token: `?token=YOUR_API_KEY`

## Event Types

The WebSocket service emits these events:

```tsx
// Connection lifecycle
service.on('connected', () => {})      // WS connected
service.on('disconnected', () => {})   // WS disconnected
service.on('error', (msg) => {})       // Connection error
service.on('connection_failed', () => {}) // Max retries exceeded

// Agent events (from agent WebSocket)
service.on('state_transition', (msg) => {})
service.on('decision_made', (msg) => {})
service.on('trade_executed', (msg) => {})
service.on('position_closed', (msg) => {})

// Real-time updates (from new streaming endpoints)
service.on('portfolio_update', (msg) => {})
service.on('positions_update', (msg) => {})
```

## Performance Characteristics

### Before (Polling)
- 5-second poll interval
- Fixed network overhead every 5s
- Stale data up to 5s old
- No connection feedback

### After (WebSocket)
- Instant updates (sub-second latency)
- Persistent connection, lower overhead
- Data always current
- Live connection status in UI
- Graceful offline fallback
- Automatic reconnection

## Manual WebSocket Subscription (Advanced)

For custom use cases, subscribe directly to events:

```tsx
import { getWebSocketService, type WebSocketMessage } from '@/services/websocket';
import { useEffect } from 'react';

function CustomComponent() {
  useEffect(() => {
    const service = getWebSocketService();
    
    // Subscribe to specific event
    const unsubscribe = service.on('decision_made', (msg: WebSocketMessage) => {
      console.log('New decision:', msg.data);
      // Update UI here
    });
    
    // Cleanup
    return unsubscribe;
  }, []);
  
  return <div>Check console</div>;
}
```

## Troubleshooting

### Connection not establishing
1. Check API key is valid: `localStorage.getItem('api_key')`
2. Verify backend WebSocket endpoint is running
3. Check browser console for detailed errors
4. Ensure `ENVIRONMENT=development` or valid API key in production

### Updates not arriving
1. Check connection status indicator shows "Live"
2. Verify component has `enabled={true}` on hooks
3. Look for console errors
4. Check Network tab → WS → Messages

### Stale data in cache
React Query keeps data for 30s before marking stale. To force refresh:
```tsx
const { refetch } = usePortfolioRealTime();
refetch(); // Force immediate refresh
```

## Configuration

Polling intervals are gone! But React Query cache times are configurable in `frontend/src/api/queryClient.ts`:

```tsx
export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 30 * 1000,    // Mark stale after 30s
      gcTime: 5 * 60 * 1000,   // Keep cache 5 minutes
      retry: 1,
      refetchOnWindowFocus: false,  // Don't poll on focus
    },
  },
});
```

## Backward Compatibility

Old polling hooks still work:
```tsx
import { usePolling } from '@/api/hooks/usePolling';

// Still functional, but deprecated
const { data } = usePolling(() => fetch(...), 5000);
```

## Next Steps

1. Update your components to import from `useRealTime.ts`
2. Add `<ConnectionProvider>` to your app (done in `App.tsx`)
3. Include `<FloatingConnectionStatus />` or `<ConnectionBadge />` in layout
4. Test with network throttling to see reconnection behavior
5. Monitor Chrome DevTools → Network → WS for real-time updates

## References

- [React Query Documentation](https://tanstack.com/query/latest)
- [WebSocket API](https://developer.mozilla.org/en-US/docs/Web/API/WebSocket)
- [Backend WebSocket Endpoint](../../finance_feedback_engine/api/bot_control.py#L770)
