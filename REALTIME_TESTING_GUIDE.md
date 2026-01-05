# Testing the Real-Time WebSocket Implementation

## Pre-Flight Checks

### 1. Verify Backend WebSocket Endpoints Exist

```bash
# Check if the new endpoints are registered
# (Open DevTools Network tab → filter by "ws")

# In browser console:
fetch('http://localhost:8000/api/v1/bot/status')
  .then(r => r.json())
  .then(console.log)
```

### 2. Check Frontend TypeScript Compilation

```bash
cd frontend
npm run type-check
# Should show no errors
```

### 3. Verify API Key Configuration

```bash
# In browser console:
localStorage.getItem('api_key')
# Should return your API key
```

---

## Manual Testing Steps

### Test 1: Connection Status Indicator

**Steps:**
1. Start the app
2. Look at bottom-left corner
3. Should show "Live" with green dot

**What to look for:**
- ✅ Green dot visible
- ✅ Shows "Live Updates"
- ✅ No error messages

**If fails:**
- Check `ENVIRONMENT=development` or valid API key
- Check backend is running on port 8000

---

### Test 2: Real-Time Portfolio Updates

**Setup:**
```bash
# Terminal 1: Start backend
python main.py serve --port 8000

# Terminal 2: Start frontend
cd frontend && npm run dev

# Terminal 3: Make a trade (in another tab or via API)
python main.py execute <decision_uuid>
```

**Steps:**
1. Open Dashboard
2. Note the portfolio value
3. Execute a trade in another terminal
4. Watch portfolio update in Dashboard
5. Should update in <1 second (not 5 seconds!)

**What to look for:**
- ✅ Portfolio value changes instantly
- ✅ No 5-second delay
- ✅ Connection status stays "Live"

**If fails:**
- Open DevTools Network tab
- Click on WebSocket connection in Network tab
- Go to Messages tab
- Should see `portfolio_update` messages
- Check timestamps to verify <1s updates

---

### Test 3: Position Updates in Real-Time

**Setup:**
1. Have an open position
2. Open Dashboard → Positions Table

**Steps:**
1. Note current position details
2. Place a new trade
3. Watch Position Table update
4. Should appear instantly

**What to look for:**
- ✅ New position appears in table
- ✅ P&L updates in real-time
- ✅ No page refresh needed

---

### Test 4: Connection Resilience

**Steps:**
1. Open DevTools
2. Go to Network tab
3. Throttle network (Slow 3G)
4. Navigate around app
5. Should still see "Live" (may say "Syncing..." briefly)

**What to look for:**
- ✅ Connection status updates appropriately
- ✅ Data still streams (slower but still updating)
- ✅ Auto-reconnect works

---

### Test 5: Offline Handling

**Steps:**
1. Open Network tab in DevTools
2. Check "Offline" checkbox
3. App should show "Offline" indicator
4. Uncheck "Offline"
5. App should auto-reconnect in ~5 seconds

**What to look for:**
- ✅ Shows "Offline" or "Connecting..." 
- ✅ Data doesn't error out
- ✅ Auto-reconnects without user action
- ✅ Goes back to "Live" after reconnect

---

### Test 6: WebSocket Message Rate

**Steps:**
1. Open DevTools Network tab
2. Filter by "ws"
3. Click on WebSocket connection
4. Go to Messages tab
5. Watch message rate for 10 seconds

**Expected behavior:**
```
Portfolio stream:   ~1 message every 2 seconds (+ heartbeats)
Positions stream:   ~1 message every 2 seconds (if changed)
Decisions stream:   ~1 message every 1 second (if new decision)
Agent stream:       Event-driven + status every 5 seconds
```

**What to look for:**
- ✅ Messages are coming through
- ✅ Regular intervals (not burst then nothing)
- ✅ No error messages in frames
- ✅ Total <10 messages/second (reasonable bandwidth)

---

### Test 7: Multiple Tabs/Windows

**Steps:**
1. Open two browser tabs with Dashboard
2. Make a trade
3. Both tabs should update simultaneously
4. Check Network tab - should see single shared WebSocket

**What to look for:**
- ✅ Both tabs show same data
- ✅ Both update at same time
- ✅ Only one WebSocket connection (singleton pattern works)

---

### Test 8: Component Re-Render Performance

**Steps:**
1. Open DevTools → React DevTools (install if needed)
2. Go to Profiler tab
3. Record 10 seconds of normal usage
4. Check re-render timeline

**What to look for:**
- ✅ Components re-render on new data (not every frame)
- ✅ No excessive re-renders (one per data update)
- ✅ Render times <100ms
- ✅ Smooth 60 FPS (if browser can maintain)

**Bonus**: Compare with old polling behavior if you have a backup branch

---

## Automated Testing (For Developers)

### Test WebSocket Service Directly

```tsx
// In browser console:
import { getWebSocketService } from '@/services/websocket';

const service = getWebSocketService();

// Subscribe to portfolio updates
service.on('portfolio_update', (msg) => {
  console.log('Portfolio update:', msg.data);
});

// Subscribe to connection events
service.on('connected', () => console.log('Connected!'));
service.on('disconnected', () => console.log('Disconnected!'));

// Check connection status
console.log('Connected:', service.isConnected());
```

### Test React Query Cache

```tsx
// In browser console:
import { queryClient } from '@/api/queryClient';

// Check what's in cache
console.log('Cached data:', queryClient.getQueryData(['portfolio', 'status']));

// Invalidate cache (force refresh)
queryClient.invalidateQueries({ queryKey: ['portfolio', 'status'] });

// Clear all cache
queryClient.clear();
```

### Test Connection Context

```tsx
// Create a test component:
import { useConnectionStatus } from '@/contexts/ConnectionContext';

export const ConnectionTest = () => {
  const { isConnected, isConnecting, error } = useConnectionStatus();
  
  return (
    <pre>
      {JSON.stringify({ isConnected, isConnecting, error }, null, 2)}
    </pre>
  );
};

// Mount it in your app and watch values change
```

---

## Performance Baseline Testing

### Before (Polling - 5 second interval)

```
# Measure baseline in old version
Network traffic over 60 seconds:
  - 12 REST API calls × 5KB = 60KB
  - ~1 KB/second baseline

DOM updates:
  - Every 5 seconds (1 per 5s = 0.2/sec)
  
User perception:
  - Data refreshes visibly every 5 seconds
```

### After (WebSocket - Real-time)

```
# Measure improvement in new version  
Network traffic over 60 seconds:
  - 1 WebSocket connection + ~120 messages
  - ~30KB (compressed) = 0.5 KB/second (lower!)
  
DOM updates:
  - Every 1-2 seconds (2-5 per minute)
  - Only when data actually changes
  
User perception:
  - Updates appear instantly
  - Smooth scrolling/interaction
  - Connection status always visible
```

---

## Common Test Scenarios

### Scenario 1: High-Frequency Trading

**Setup**: Run multiple trade executions in rapid succession

```bash
for i in {1..5}; do
  python main.py execute <decision_uuid> &
done
wait
```

**Expected**: 
- Portfolio updates show all 5 trades
- No missed updates
- UI remains responsive

---

### Scenario 2: Network Jitter

**Setup**: Use Network tab throttling
1. Select "Slow 3G"
2. Navigate around app
3. Make trades

**Expected**:
- Data still flows (slow but continuous)
- No data loss
- App doesn't freeze

---

### Scenario 3: Backend Restart

**Setup**:
1. App running normally
2. Kill backend (Ctrl+C)
3. Restart backend

**Expected**:
- Shows "Offline" immediately
- Auto-reconnects when backend restarts
- Data refetches automatically
- No manual refresh needed

---

### Scenario 4: Long-Running Session

**Setup**:
1. Open app
2. Let run for 1 hour
3. Make occasional trades

**Expected**:
- Connection stays stable
- No memory leaks
- Browser doesn't slow down
- Data remains current

---

## Browser DevTools Tips

### Network Tab
```
1. Filter by "ws" to show only WebSocket
2. Click connection
3. Messages tab shows incoming/outgoing
4. Frames tab shows structured data
5. Each message shows timestamp
```

### Performance Tab
```
1. Go to Performance tab
2. Click record
3. Interact with app for 10 seconds
4. Stop recording
5. Look for:
   - JavaScript main thread usage
   - Long tasks (>50ms)
   - Rendering time
```

### React DevTools
```
1. Go to Profiler tab
2. Record interactions
3. Check re-render counts
4. Identify unnecessary re-renders
5. Check component render times
```

### Console Tab
```
// Enable debug logging
localStorage.setItem('debug', 'websocket');

// Check connection
console.log('Connected:', getWebSocketService().isConnected());

// View incoming messages
getWebSocketService().on('*', (msg) => console.log(msg));
```

---

## Known Issues & Workarounds

### Issue: "Offline" stuck on first load

**Cause**: API key not set or invalid  
**Fix**:
```tsx
localStorage.setItem('api_key', 'your-valid-api-key');
location.reload();
```

### Issue: WebSocket connects but no data

**Cause**: Backend endpoint not implemented  
**Fix**: Verify backend has new WebSocket routes (check bot_control.py)

### Issue: High network usage with 1000+ positions

**Cause**: Large position updates over WebSocket  
**Fix**: Use delta compression (future enhancement)

### Issue: Multiple connections in Network tab

**Cause**: Multiple useWebSocket() hooks  
**Fix**: Already fixed - uses singleton service

---

## Metrics to Track

### Latency
- **Before**: 5 seconds average
- **After**: <1 second average (target: 200ms-800ms)

### Throughput
- **Messages/second**: Should be steady (5-20 msg/s depending on activity)
- **Bandwidth**: Should be lower than polling (shared connection)

### Reliability
- **Uptime**: 99%+ connection stability
- **Reconnect time**: <10 seconds
- **Data loss**: 0 updates lost

### User Experience
- **Visual smoothness**: 60 FPS
- **Responsiveness**: <100ms interaction delay
- **Battery usage**: Reduced (fewer network calls)

---

## Reporting Issues

If something isn't working:

1. **Gather information**:
   ```bash
   # Save Network tab as HAR
   # Right-click Network tab → Save as HAR with content
   
   # Get browser console
   # Copy console logs
   
   # Get app state
   localStorage.getItem('api_key')  # (sanitize!)
   ```

2. **Check these files**:
   - `frontend/src/services/websocket.ts` - Service
   - `frontend/src/api/hooks/useRealTime.ts` - Hooks
   - `finance_feedback_engine/api/bot_control.py` - Backend endpoints

3. **Common fixes**:
   - Clear cache: `queryClient.clear()`
   - Restart WebSocket: `getWebSocketService().disconnect(); location.reload();`
   - Check API key: `localStorage.getItem('api_key')`

---

## See Also

- [REALTIME_QUICKSTART.md](./REALTIME_QUICKSTART.md) - Quick start guide
- [WEBSOCKET_REALTIME_IMPLEMENTATION.md](./WEBSOCKET_REALTIME_IMPLEMENTATION.md) - Full implementation
- [frontend/REALTIME_MIGRATION_GUIDE.md](./frontend/REALTIME_MIGRATION_GUIDE.md) - Migration details
