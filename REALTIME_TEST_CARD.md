# Real-Time WebSocket - Quick Test Card

## 🚀 Quick Start (Copy-Paste Ready)

### 1. Start the Application
```bash
npm run dev:all
# or separately:
# Terminal 1: npm run dev
# Terminal 2: python main.py serve --port 8000
```

### 2. Verify in Browser
```javascript
// Open browser DevTools console (F12) and paste:
getWebSocketService().isConnected()  // Should return: true
```

### 3. Look for "Live" Badge
- Bottom-left corner of screen
- Green with pulse animation
- "Live" text or just icon

---

## 📊 DevTools Network Inspection (30 seconds)

### Step 1: Open Network Tab
1. Press `F12` to open DevTools
2. Click `Network` tab
3. Refresh page (Cmd+R / Ctrl+R)

### Step 2: Filter for WebSocket
1. In Network tab, type "ws" in filter box
2. You should see connections named:
   - `ws/portfolio`
   - `ws/positions`  
   - `ws/decisions`

### Step 3: Watch Messages
1. Click on any WebSocket connection
2. Click `Messages` sub-tab
3. You'll see messages flowing:
   ```
   ← {"type":"portfolio_update","data":{...}}
   ← {"type":"positions_update","data":{...}}
   ← {"type":"decision_made","data":{...}}
   ```

### Step 4: Verify Update Frequency
- Portfolio: ~2 messages per second
- Positions: ~2 messages per second
- Decisions: ~1 message per second (or less if no trades)

---

## 🧪 Manual Test Scenarios (5 minutes each)

### Test 1: Initial Connection
```
✅ Open app
✅ Look for "Live" badge (should appear immediately or after 1-2 seconds)
✅ Badge should be green with animation
✅ DevTools Network tab shows 3 WebSocket connections
Expected: All pass
```

### Test 2: Real-Time Updates
```
✅ Have Network tab open with WebSocket filter
✅ Watch Messages sub-tab
✅ You should see messages appearing every 1-2 seconds
Expected: Constant message flow
```

### Test 3: Auto-Reconnection
```
✅ Open DevTools Network tab
✅ Disable internet (airplane mode) or:
  - DevTools → Network tab → Throttling → Offline
✅ Badge should change to "Offline" (red)
✅ Re-enable internet/online
✅ Badge should change to "Connecting..." then "Live"
Expected: Auto-reconnect within 5 seconds
```

### Test 4: Force Disconnect
```
✅ Open browser console (F12 → Console)
✅ Paste: getWebSocketService().disconnect()
✅ Badge should show "Offline"
✅ Wait 2 seconds
✅ Badge should show "Connecting..." then "Live"
Expected: Auto-reconnects automatically
```

### Test 5: Trade Execution (if available)
```
✅ Make a trade through the app
✅ Watch DevTools Network → WebSocket → Messages
✅ You should see a `decision_made` message appear
✅ Portfolio should update within 1 second
Expected: <1 second update latency
```

### Test 6: Portfolio Update
```
✅ With Network tab open, watching WebSocket messages
✅ Look at portfolio display
✅ You should see portfolio_update messages every 1-2 seconds
✅ Portfolio numbers should be updating smoothly
Expected: Smooth, real-time updates
```

### Test 7: Position Tracking
```
✅ Open Positions view
✅ Watch WebSocket messages for `positions_update` 
✅ Open a position (make a trade)
✅ Position should appear in list within 1 second
Expected: Real-time position visibility
```

### Test 8: Connection Badge Behavior
```
✅ "Live" badge (green, pulsing):
   - Should see this most of the time
✅ "Connecting..." badge (yellow, spinning):
   - Briefly appears when reconnecting
   - Should not last more than 5 seconds
✅ "Offline" badge (red, static):
   - Only appears if network is down
   - Disappears when connection restored
Expected: Badge matches actual connection state
```

---

## 🔍 Advanced Debugging (Copy-Paste Console Commands)

### Check Connection Status
```javascript
getWebSocketService().isConnected()
// Returns: true | false
```

### View Current Connection Error
```javascript
const svc = getWebSocketService();
console.log(svc.error);
// Shows: null (if connected) | Error object (if disconnected)
```

### Check Reconnection Progress
```javascript
const svc = getWebSocketService();
console.log({
  isConnected: svc.isConnected(),
  retryCount: svc.retryCount,
  isConnecting: svc.isConnecting
});
```

### View React Query Cache (Portfolio)
```javascript
queryClient.getQueryData(['portfolio', 'status'])
// Shows: { balance, positions, total_value, ... } or undefined
```

### View React Query Cache (Positions)
```javascript
queryClient.getQueryData(['positions', 'list'])
// Shows: [{ position... }, ...] or undefined
```

### Force Real-Time Hook Update
```javascript
// In component using usePortfolioRealTime():
queryClient.invalidateQueries({ queryKey: ['portfolio', 'status'] })
// Forces refetch from server (cache-busting)
```

### Subscribe to Raw WebSocket Events (Terminal Style)
```javascript
const unsubscribe = getWebSocketService().on('portfolio_update', (data) => {
  console.log('📊 Portfolio Update:', data);
});
// All future portfolio updates will log to console
// Call unsubscribe() to stop listening
```

---

## 🎯 Expected Behavior Checklist

### On Page Load
- [ ] Page renders normally
- [ ] "Live" badge appears (or "Connecting..." briefly)
- [ ] No JavaScript errors in console
- [ ] Network tab shows 3 WebSocket connections opening

### During Normal Use
- [ ] Badge stays "Live" (green, pulsing)
- [ ] Portfolio updates appear smoothly
- [ ] No lag when viewing different pages
- [ ] WebSocket messages flow steadily in Network tab

### On Network Disconnect
- [ ] Badge changes to "Offline" (red)
- [ ] App continues to work with cached data
- [ ] No error messages (graceful degradation)

### On Network Reconnect
- [ ] Badge shows "Connecting..." (yellow) briefly
- [ ] Badge returns to "Live" within 5 seconds
- [ ] Data updates resume automatically
- [ ] No page refresh needed

### On Browser Tab Inactive
- [ ] WebSocket connection stays alive (heartbeat)
- [ ] Badge remains "Live"
- [ ] Connection resumes when tab becomes active

---

## 📈 Performance Benchmarking

### Before (5-Second Polling)
```
Latency: ~5 seconds (up to)
Freshness: Data up to 5 seconds old
Network: 12 HTTP calls per minute per hook
Update Pattern: Visible delay between action and UI update
```

### After (WebSocket Real-Time)
```
Latency: <1 second (typical)
Freshness: <1 second old (typical)
Network: Single persistent connection + incremental updates
Update Pattern: Immediate feedback, smooth scrolling
```

### Test Latency Yourself
```javascript
// In browser console, paste this in component using real-time data:
const start = Date.now();
const unsubscribe = getWebSocketService().on('portfolio_update', (data) => {
  const latency = Date.now() - start;
  console.log(`⚡ Update latency: ${latency}ms`);
  unsubscribe();
});
// Make a trade and watch the console
// Should see latency < 1000ms typically
```

---

## 🐛 Troubleshooting Checklist

### Issue: Badge Shows "Offline" or "Connecting..."
**Fix**:
1. Check internet connection (ping google.com)
2. Check if backend is running: `curl http://localhost:8000/health`
3. Check browser console for errors (F12)
4. Check if auth token is valid
5. Try: `getWebSocketService().disconnect(); getWebSocketService().connect();`

### Issue: No Messages in WebSocket Network Tab
**Fix**:
1. Verify backend is running
2. Check if you're watching the right WebSocket (ws/portfolio, ws/positions, ws/decisions)
3. Portfolio updates only send if portfolio changed, so make a trade first
4. Check browser console for errors
5. Try refreshing page

### Issue: "Connection refused" in Console
**Fix**:
1. Backend must be running: `python main.py serve --port 8000`
2. Frontend must be at: `http://localhost:5173` (Vite dev)
3. Both must be on same machine for localhost
4. Check firewall isn't blocking port 8000

### Issue: High Message Traffic (too many updates)
**Fix**:
1. This is normal - each WebSocket sends 1-2 messages per second
2. This is much less than 5-second HTTP polling
3. Messages only include changes (not full data every time)
4. Normal total bandwidth is lower than before

### Issue: Reconnection Stuck in "Connecting..."
**Fix**:
1. Check internet connection
2. Check backend health: `curl http://localhost:8000/health`
3. Force disconnect and reconnect:
   ```javascript
   getWebSocketService().disconnect();
   await new Promise(r => setTimeout(r, 1000));
   getWebSocketService().connect();
   ```

---

## ✅ Final Verification

Run through this in ~5 minutes to confirm everything works:

1. **Start App**
   ```bash
   npm run dev:all
   ```
   ✅ Expected: Both backend and frontend start

2. **Check Badge**
   ✅ Expected: "Live" badge in bottom-left within 2 seconds

3. **Check WebSocket**
   - F12 → Network → Filter "ws"
   ✅ Expected: 3 WebSocket connections listed

4. **Watch Messages**
   - Click one WebSocket → Messages tab
   ✅ Expected: Messages appearing every 1-2 seconds

5. **Test Update**
   - Make a trade or wait for data change
   ✅ Expected: Update appears in <1 second, no visible delay

6. **Test Reconnect**
   - Toggle offline in Network tab
   ✅ Expected: Badge → "Offline" → "Connecting..." → "Live" (~5 sec)

7. **Verify No Errors**
   - F12 → Console
   ✅ Expected: No red error messages

---

## 📞 Need Help?

| Issue | Solution |
|-------|----------|
| App not starting | See `npm run dev:all` in repo README |
| Badge not showing | Check backend health endpoint |
| WebSocket not connecting | Verify backend port 8000 is accessible |
| Messages not flowing | Make a trade to trigger portfolio update |
| Connection keeps dropping | Check network, try browser refresh |
| Performance still slow | Check that polling hooks aren't running (deprecated versions) |

---

**Last Updated**: January 5, 2026  
**Status**: ✅ Ready to Test  
**Estimated Time**: ~10 minutes for full verification  

Happy testing! 🎉
