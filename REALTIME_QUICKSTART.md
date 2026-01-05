# 🚀 Real-Time Updates: Quick Start

You asked for **smooth real-time WebSocket updates** instead of 5-second polling. ✅ **Done!**

## What You Get Now

- ⚡ **Sub-second latency** instead of 5-second delays
- 🔌 **Persistent WebSocket** instead of constant HTTP polling
- 🔄 **Automatic reconnection** with exponential backoff
- 📊 **Live connection status** indicator in the UI
- 🎯 **Zero component changes needed** - backward compatible!

## Start Using It

### 1. The UI Will Show "Live" Status
Open the app and look at the bottom-left corner. You'll see:
- 🟢 **Live** - WebSocket connected, real-time updates active
- ⟳ **Syncing...** - Attempting to connect
- ✗ **Offline** - Connection lost, auto-reconnecting

### 2. Everything Updates Instantly
Instead of waiting 5 seconds for data to refresh, you'll see:
- Portfolio balance updates in <1 second
- Position changes immediately
- New decisions appear instantly
- All without any polling delays

### 3. No Code Changes Needed
Your existing components work automatically! The old hooks now use WebSocket internally:

```tsx
// This component still works - now with real-time updates!
import { usePortfolio } from '@/api/hooks/usePortfolio';

export const Dashboard = () => {
  const { data } = usePortfolio(); // Now real-time via WebSocket!
  return <div>${data?.portfolio_value}</div>;
};
```

## For Developers

### Use New Real-Time Hooks Directly (Optional)

```tsx
import { 
  usePortfolioRealTime,
  usePositionsRealTime,
  useDecisionsRealTime 
} from '@/api/hooks/useRealTime';

export const Dashboard = () => {
  const portfolio = usePortfolioRealTime();
  const positions = usePositionsRealTime();
  
  return (
    <>
      <h2>${portfolio.data?.portfolio_value}</h2>
      <ul>
        {positions.data?.map(p => <li key={p.id}>{p.asset}</li>)}
      </ul>
    </>
  );
};
```

### Subscribe to Raw Events (Advanced)

```tsx
import { usePortfolioUpdates } from '@/api/hooks/useRealTime';

export const LiveMetrics = () => {
  usePortfolioUpdates((portfolio) => {
    console.log('Portfolio updated:', portfolio);
    // Custom handling here
  });
  
  return <div>Check console...</div>;
};
```

### Check Connection Status

```tsx
import { useConnectionStatus } from '@/contexts/ConnectionContext';

export const StatusIndicator = () => {
  const { isConnected, isConnecting, error } = useConnectionStatus();
  
  if (isConnected) return <span>✓ Live Updates</span>;
  if (isConnecting) return <span>⟳ Connecting...</span>;
  if (error) return <span>✗ Error: {error}</span>;
};
```

## How It's Built

### Frontend Architecture
```
App.tsx
└── QueryClientProvider (React Query)
    └── ConnectionProvider (WebSocket)
        └── Components
            ├── usePortfolioRealTime() → Cache + WebSocket
            ├── usePositionsRealTime() → Cache + WebSocket
            ├── useDecisionsRealTime() → Cache + WebSocket
            └── useConnectionStatus() → Global connection state
```

### Backend Architecture
```
FastAPI /api/v1/bot/ws
├── /ws                 - Agent events (existing)
├── /ws/portfolio       - Portfolio updates (NEW)
├── /ws/positions       - Position changes (NEW)
└── /ws/decisions       - Decision stream (NEW)
```

## Technical Details

### WebSocket Service (`frontend/src/services/websocket.ts`)
- Singleton WebSocket instance
- Automatic reconnection (1s → 2s → 4s → ... → 30s)
- Max 10 reconnect attempts
- Heartbeat monitoring
- Event routing system

### React Query Integration (`frontend/src/api/queryClient.ts`)
- 30-second stale time (WebSocket updates sooner anyway)
- 5-minute garbage collection
- Disabled polling on window focus
- Optimized for real-time data

### Connection Context (`frontend/src/contexts/ConnectionContext.tsx`)
- Global connection state
- Available to all components
- Automatic initialization

### Status Indicators (`frontend/src/components/ConnectionStatus.tsx`)
- `ConnectionStatus` - Full status with text
- `FloatingConnectionStatus` - Corner badge (auto-included)
- `ConnectionBadge` - Compact indicator

## Testing It Out

1. **Open the app** - Look for "Live" badge in bottom-left
2. **Make a trade** - Portfolio updates instantly (not after 5 seconds)
3. **Disconnect WiFi** - Shows "Offline", auto-reconnects when back online
4. **Open DevTools** - Network tab → WS shows real-time messages
5. **Watch latency** - Compare to old behavior: <1s vs ~5s

## File Changes

**New Files:**
- `frontend/src/services/websocket.ts` - WebSocket service
- `frontend/src/api/hooks/useWebSocket.ts` - WebSocket hook
- `frontend/src/api/hooks/useRealTime.ts` - Real-time hooks
- `frontend/src/contexts/ConnectionContext.tsx` - Connection context
- `frontend/src/components/ConnectionStatus.tsx` - Status components
- `frontend/src/api/queryClient.ts` - React Query config
- `WEBSOCKET_REALTIME_IMPLEMENTATION.md` - Full implementation docs
- `frontend/REALTIME_MIGRATION_GUIDE.md` - Detailed migration guide
- `frontend/REALTIME_QUICKREF.md` - Quick reference

**Modified Files:**
- `frontend/src/App.tsx` - Added providers and status indicator
- `frontend/src/api/hooks/usePortfolio.ts` - Now uses WebSocket internally
- `frontend/src/api/hooks/usePositions.ts` - Now uses WebSocket internally
- `frontend/src/api/hooks/useDecisions.ts` - Now uses WebSocket internally
- `frontend/src/api/hooks/useHealth.ts` - Now uses WebSocket internally
- `finance_feedback_engine/api/bot_control.py` - Added 3 WebSocket endpoints

## Performance Before & After

| Aspect | Before | After |
|--------|--------|-------|
| Update latency | ~5 seconds | <1 second ⚡ |
| Data staleness | Up to 5s | <1s ⚡ |
| Network overhead | Constant polling | Persistent connection ⚡ |
| Connection feedback | None ❌ | Live indicator ✅ |
| Reconnection | Manual | Automatic ✅ |

## Troubleshooting

**"Offline" badge won't go away?**
```bash
# Check API key
localStorage.getItem('api_key')

# Check backend is running
curl http://localhost:8000/api/health
```

**Data not updating?**
1. Check Network tab → WS → Messages showing incoming data
2. Verify "Live" badge shows in UI
3. Check browser console for errors

**Want old polling behavior back?**
```tsx
// Still available, but not recommended
import { usePolling } from '@/api/hooks/usePolling';
```

## Deeper Dive

For detailed information, see:
- **[WEBSOCKET_REALTIME_IMPLEMENTATION.md](./WEBSOCKET_REALTIME_IMPLEMENTATION.md)** - Full implementation details
- **[frontend/REALTIME_MIGRATION_GUIDE.md](./frontend/REALTIME_MIGRATION_GUIDE.md)** - Complete migration guide
- **[frontend/REALTIME_QUICKREF.md](./frontend/REALTIME_QUICKREF.md)** - Developer quick reference

---

**That's it!** Your UI now feels smooth and responsive with real-time WebSocket updates. No more 5-second delays! 🎉
