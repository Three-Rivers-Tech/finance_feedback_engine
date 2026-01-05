# Real-Time Updates Quick Reference

## TL;DR: From Polling to WebSocket

```tsx
// ❌ OLD (5-second polling)
import { usePolling } from '@/api/hooks/usePolling';
const { data } = usePolling(() => fetch('/api/status'), 5000);

// ✅ NEW (WebSocket real-time)
import { usePortfolioRealTime } from '@/api/hooks/useRealTime';
const { data } = usePortfolioRealTime();
```

**That's it!** The API is identical, just swap the import.

---

## Quick Start

### 1. App Setup (Already done in App.tsx)
```tsx
import { ConnectionProvider } from '@/contexts/ConnectionContext';
import { FloatingConnectionStatus } from '@/components/ConnectionStatus';

<QueryClientProvider client={queryClient}>
  <ConnectionProvider>
    <YourApp />
    <FloatingConnectionStatus />
  </ConnectionProvider>
</QueryClientProvider>
```

### 2. Use Real-Time Hooks
```tsx
import { usePortfolioRealTime, usePositionsRealTime } from '@/api/hooks/useRealTime';

function Dashboard() {
  const portfolio = usePortfolioRealTime();
  const positions = usePositionsRealTime();
  
  if (portfolio.isLoading) return <Spinner />;
  
  return (
    <>
      <h2>${portfolio.data?.portfolio_value}</h2>
      <ul>
        {positions.data?.map(p => <li key={p.id}>{p.asset}</li>)}
      </ul>
    </>
  );
}
```

### 3. Show Connection Status
```tsx
import { ConnectionStatus, ConnectionBadge } from '@/components/ConnectionStatus';

// Full status with text
<ConnectionStatus />

// Compact badge
<ConnectionBadge />

// Custom via context
const { isConnected, error } = useConnectionStatus();
```

---

## Available Hooks

| Hook | Updates Every | Event |
|------|---------------|-------|
| `usePortfolioRealTime()` | 2s | `portfolio_update` |
| `usePositionsRealTime()` | 2s | `positions_update` |
| `useDecisionsRealTime()` | 1s | `decision_made` |
| `useHealthStatusRealTime()` | 30s | `heartbeat` |

**Subscribe to raw events:**
```tsx
usePortfolioUpdates((portfolio) => console.log(portfolio));
usePositionUpdates((action, position) => console.log(action, position));
useDecisionUpdates((decision) => console.log(decision));
```

---

## Connection Status

```tsx
import { useConnectionStatus } from '@/contexts/ConnectionContext';

function MyComponent() {
  const { isConnected, isConnecting, error } = useConnectionStatus();
  
  if (isConnected) return <div>✓ Live</div>;
  if (isConnecting) return <div>⟳ Connecting...</div>;
  if (error) return <div>✗ {error}</div>;
}
```

---

## Manual WebSocket (Advanced)

```tsx
import { getWebSocketService } from '@/services/websocket';

const service = getWebSocketService();
await service.connect();

// Subscribe
const unsub = service.on('decision_made', (msg) => {
  console.log(msg.data);
});

// Send
service.send('start', { autonomous: true, asset_pairs: ['BTCUSD'] });

// Cleanup
unsub();
```

---

## What's Different?

| Aspect | Before | After |
|--------|--------|-------|
| Update Latency | 5s | <1s |
| Network Traffic | Constant polls | Persistent connection |
| Offline Behavior | Stale data | Automatic reconnect |
| Connection Feedback | None | Live indicator |
| Developer Experience | Manual polling | Hooks + context |

---

## Files to Update in Your Components

### PortfolioOverview.tsx
```tsx
-import { usePortfolio } from '@/api/hooks/usePortfolio';
+import { usePortfolioRealTime } from '@/api/hooks/useRealTime';

-const portfolio = usePortfolio(enabled);
+const portfolio = usePortfolioRealTime(enabled);
```

### PositionsTable.tsx
```tsx
-import { usePositions } from '@/api/hooks/usePositions';
+import { usePositionsRealTime } from '@/api/hooks/useRealTime';

-const positions = usePositions(enabled);
+const positions = usePositionsRealTime(enabled);
```

### RecentDecisions.tsx
```tsx
-import { useDecisions } from '@/api/hooks/useDecisions';
+import { useDecisionsRealTime } from '@/api/hooks/useRealTime';

-const decisions = useDecisions(enabled);
+const decisions = useDecisionsRealTime(enabled);
```

---

## Backend Endpoints

```
New WebSocket endpoints:
/api/v1/bot/ws/portfolio    → portfolio_update
/api/v1/bot/ws/positions    → positions_update  
/api/v1/bot/ws/decisions    → decision_made

Existing:
/api/v1/bot/ws              → agent stream (state, trades, errors)
```

All require: `?token=YOUR_API_KEY`

---

## Checking It Works

1. **Connection indicator**: Should show "Live" in bottom-left
2. **Network tab**: Open DevTools → Network → WS, should see WebSocket connections
3. **Messages**: Click WebSocket in Network tab, see real-time messages
4. **React DevTools**: Check component re-renders happen smoothly

---

## Troubleshooting

**"Offline" indicator won't go away**
```tsx
// Check API key
console.log(localStorage.getItem('api_key'));

// Check backend WebSocket is running
curl http://localhost:8000/api/v1/bot/ws
```

**No data showing**
```tsx
// Verify hook is enabled
const portfolio = usePortfolioRealTime(true); // enabled=true

// Check browser console for errors
```

**Data not updating**
```tsx
// Force refetch
const { refetch } = usePortfolioRealTime();
refetch();

// Or check Network tab for WebSocket messages
```

---

## See Also

- **Full Guide**: [REALTIME_MIGRATION_GUIDE.md](./REALTIME_MIGRATION_GUIDE.md)
- **Service Code**: [frontend/src/services/websocket.ts](./src/services/websocket.ts)
- **Hooks Code**: [frontend/src/api/hooks/useRealTime.ts](./src/api/hooks/useRealTime.ts)
- **Backend Code**: [finance_feedback_engine/api/bot_control.py](../finance_feedback_engine/api/bot_control.py)
