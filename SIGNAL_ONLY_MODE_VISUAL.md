# Signal-Only Mode Decision Flow

```
┌─────────────────────────────────────────────────────────────────────┐
│                    DECISION ENGINE WORKFLOW                         │
└─────────────────────────────────────────────────────────────────────┘

                    ┌──────────────────────┐
                    │  Start: Analyze Asset │
                    └──────────┬───────────┘
                               │
                               ▼
                    ┌──────────────────────┐
                    │ Fetch Market Data    │
                    │ (Price, Volume, RSI) │
                    └──────────┬───────────┘
                               │
                               ▼
                    ┌──────────────────────┐
                    │ Get Portfolio/Balance│
                    │  from Trading Platform│
                    └──────────┬───────────┘
                               │
                               ▼
                ┌──────────────────────────────┐
                │  LOGIC GATE: Check Balance   │
                │  - Is it a dict?             │
                │  - Is it non-empty?          │
                │  - Is sum > 0?               │
                └──────────┬────────────┬──────┘
                           │            │
                  ✅ VALID │            │ ❌ INVALID
                           │            │
         ┌─────────────────▼─────┐     ▼────────────────────┐
         │   NORMAL MODE          │     │ SIGNAL-ONLY MODE   │
         │                        │     │                    │
         │ Calculate Position:    │     │ Skip Position:     │
         │ • position_size = f()  │     │ • position_size = ⊗│
         │ • stop_loss = 2.0%     │     │ • stop_loss = ⊗    │
         │ • risk = 1.0%          │     │ • risk = ⊗         │
         │ • signal_only = False  │     │ • signal_only = True│
         └──────────┬──────────────┘     └─────────┬──────────┘
                    │                              │
                    └──────────┬───────────────────┘
                               │
                               ▼
                    ┌──────────────────────┐
                    │  Generate AI Decision │
                    │  • Action: BUY/SELL/HOLD│
                    │  • Confidence: 0-100%   │
                    │  • Reasoning: Analysis  │
                    └──────────┬───────────┘
                               │
                               ▼
                    ┌──────────────────────┐
                    │  Create Decision Object│
                    │  with appropriate flags│
                    └──────────┬───────────┘
                               │
                               ▼
                    ┌──────────────────────┐
                    │   Persist Decision   │
                    │   (JSON file)        │
                    └──────────┬───────────┘
                               │
                               ▼
         ┌─────────────────────┴────────────────────┐
         │                                           │
    ▼────────────────────┐              ▼───────────────────┐
    │ NORMAL MODE OUTPUT │              │ SIGNAL-ONLY OUTPUT│
    │                    │              │                   │
    │ Action: BUY        │              │ Action: BUY       │
    │ Confidence: 75%    │              │ Confidence: 75%   │
    │ Reasoning: "..."   │              │ Reasoning: "..."  │
    │                    │              │                   │
    │ ✅ Position Details│              │ ⚠️  Signal Only   │
    │ Size: 0.052 BTC    │              │ No sizing data    │
    │ Stop: 2.0%         │              │                   │
    │ Risk: 1.0%         │              │ ⊗ Size: null      │
    │                    │              │ ⊗ Stop: null      │
    │ signal_only: false │              │ ⊗ Risk: null      │
    │                    │              │                   │
    │                    │              │ signal_only: true │
    └────────────────────┘              └───────────────────┘
```

## Balance Validation Logic

```
┌─────────────────────────────────────────┐
│         BALANCE VALIDATION              │
└─────────────────────────────────────────┘

Input: balance = ???

     ┌──────────────┐
     │ Is dict?     │──── NO ──► INVALID (signal-only)
     └───┬──────────┘
         │ YES
         ▼
     ┌──────────────┐
     │ Is non-empty?│──── NO ──► INVALID (signal-only)
     └───┬──────────┘
         │ YES
         ▼
     ┌──────────────┐
     │ Sum > 0?     │──── NO ──► INVALID (signal-only)
     └───┬──────────┘
         │ YES
         ▼
     ┌──────────────┐
     │   ✅ VALID   │──────────► Normal mode
     │   Calculate  │            (with position sizing)
     │   Positions  │
     └──────────────┘
```

## Example Scenarios

### Scenario 1: Valid Balance (Normal Mode)
```
Input:  balance = {'USD': 10000.0, 'BTC': 0.1}
Check:  dict? ✅  empty? ✅  sum>0? ✅
Result: NORMAL MODE
Output: {
  "signal_only": false,
  "recommended_position_size": 0.052,
  "stop_loss_percentage": 2.0,
  "risk_percentage": 1.0
}
```

### Scenario 2: Empty Balance (Signal-Only Mode)
```
Input:  balance = {}
Check:  dict? ✅  empty? ❌
Result: SIGNAL-ONLY MODE
Output: {
  "signal_only": true,
  "recommended_position_size": null,
  "stop_loss_percentage": null,
  "risk_percentage": null
}
```

### Scenario 3: Zero Balance (Signal-Only Mode)
```
Input:  balance = {'USD': 0.0, 'BTC': 0.0}
Check:  dict? ✅  empty? ✅  sum>0? ❌
Result: SIGNAL-ONLY MODE
Output: {
  "signal_only": true,
  "recommended_position_size": null,
  "stop_loss_percentage": null,
  "risk_percentage": null
}
```

### Scenario 4: None Balance (Signal-Only Mode)
```
Input:  balance = None
Check:  dict? ❌
Result: SIGNAL-ONLY MODE
Output: {
  "signal_only": true,
  "recommended_position_size": null,
  "stop_loss_percentage": null,
  "risk_percentage": null
}
```

## Position Sizing Formula (Normal Mode Only)

```
┌────────────────────────────────────────────────────┐
│         POSITION SIZE CALCULATION                  │
└────────────────────────────────────────────────────┘

Given:
  • Account Balance: $10,000
  • Entry Price: $96,200 (current BTC price)
  • Risk Percentage: 1.0% (default)
  • Stop Loss: 2.0% (default)

Calculate:
  1. Risk Amount = Balance × (Risk% / 100)
     = $10,000 × 0.01
     = $100

  2. Stop Loss Distance = Entry × (Stop% / 100)
     = $96,200 × 0.02
     = $1,924

  3. Position Size = Risk Amount / Stop Loss Distance
     = $100 / $1,924
     = 0.052 BTC

Result: Recommended position size = 0.052 BTC
```

## CLI Output Comparison

### Normal Mode
```
Trading Decision Generated
Decision ID: abc-123
Asset: BTCUSD
Action: BUY
Confidence: 75%

Position Details:
  Type: LONG
  Entry Price: $96,200.00
  Recommended Size: 0.051976 units
  Risk: 1.0% of account
  Stop Loss: 2.0% from entry
```

### Signal-Only Mode
```
Trading Decision Generated
Decision ID: def-456
Asset: BTCUSD
Action: BUY
Confidence: 75%

⚠ Signal-Only Mode: Portfolio data unavailable, no position sizing provided

(Position details not shown)
```
