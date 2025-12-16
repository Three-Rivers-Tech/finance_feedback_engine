# Asset Pair Input Validation

## Overview

The Finance Feedback Engine now automatically standardizes asset pair inputs to ensure compatibility with the Alpha Vantage API. Users can enter asset pairs in any format they prefer, and the system will automatically convert them to the correct format.

## Features

### Automatic Standardization

All asset pair inputs are automatically:
- **Converted to uppercase** - `btcusd` → `BTCUSD`
- **Stripped of separators** - Removes underscores, dashes, slashes, and spaces
- **Validated** - Ensures input contains valid alphanumeric characters

### Supported Input Formats

The system accepts and standardizes various common formats:

**Crypto Pairs:**
```bash
# All of these are equivalent and become 'BTCUSD':
python main.py analyze btcusd
python main.py analyze BTC-USD
python main.py analyze btc_usd
python main.py analyze BTC/USD
python main.py analyze "BTC USD"
```

**Forex Pairs:**
```bash
# All of these are equivalent and become 'EURUSD':
python main.py analyze eurusd
python main.py analyze EUR-USD
python main.py analyze eur_usd
python main.py analyze EUR/USD
python main.py analyze "EUR USD"
```

## Implementation Details

### Where Standardization Occurs

Input validation happens at two levels:

1. **CLI Layer** (`finance_feedback_engine/cli/main.py`)
   - Normalizes user input from command-line arguments
   - Applies before engine processing

2. **Core Engine** (`finance_feedback_engine/core.py`)
   - Normalizes input from Python API calls
   - Ensures consistency regardless of entry point

### Validation Function

The standardization is performed by the `standardize_asset_pair()` function in `finance_feedback_engine/utils/validation.py`:

```python
from finance_feedback_engine.utils.validation import standardize_asset_pair

# Examples
standardize_asset_pair('btc-usd')  # Returns: 'BTCUSD'
standardize_asset_pair('eur_usd')  # Returns: 'EURUSD'
standardize_asset_pair('ETH/USD')  # Returns: 'ETHUSD'
```

### Error Handling

Invalid inputs are rejected with clear error messages:

```python
# Empty string
standardize_asset_pair('')
# ValueError: Asset pair must be a non-empty string

# Only separators
standardize_asset_pair('___---')
# ValueError: Invalid asset pair '___---': must contain alphanumeric characters
```

## Usage Examples

### CLI Usage

```bash
# Crypto analysis (various formats)
python main.py analyze btcusd          # Simple lowercase
python main.py analyze BTC-USD         # Uppercase with dash
python main.py analyze btc_usd         # Lowercase with underscore
python main.py analyze "BTC USD"       # With space (needs quotes)

# Forex analysis (various formats)
python main.py analyze eurusd          # Simple lowercase
python main.py analyze EUR_USD         # Common forex format
python main.py analyze eur-usd         # Dash separator
python main.py analyze "EUR/USD"       # Slash separator (needs quotes)

# All variations work with providers
python main.py analyze btc-usd --provider ensemble
python main.py analyze eur_usd --provider local
```

### Python API Usage

```python
from finance_feedback_engine import FinanceFeedbackEngine

config = {...}  # Your configuration
engine = FinanceFeedbackEngine(config)

# All these formats work
decision1 = engine.analyze_asset('btc-usd')     # Returns asset_pair: 'BTCUSD'
decision2 = engine.analyze_asset('BTC_USD')     # Returns asset_pair: 'BTCUSD'
decision3 = engine.analyze_asset('eur/usd')     # Returns asset_pair: 'EURUSD'
decision4 = engine.analyze_asset('EURUSD')      # Returns asset_pair: 'EURUSD'
```

## Alpha Vantage API Compatibility

### Why Standardization Matters

Alpha Vantage API expects specific formats:

- **Crypto**: `DIGITAL_CURRENCY_DAILY` requires symbol + market (e.g., 'BTC' + 'USD')
  - Input: `BTCUSD` → Parsed as: `symbol='BTC'`, `market='USD'`

- **Forex**: `FX_DAILY` requires from_symbol + to_symbol (e.g., 'EUR' + 'USD')
  - Input: `EURUSD` → Parsed as: `from_symbol='EUR'`, `to_symbol='USD'`

### Parsing Logic

The provider parses standardized pairs by slicing:

```python
# For 'BTCUSD' or 'EURUSD' (6+ chars)
from_currency = asset_pair[:3]    # First 3 chars
to_currency = asset_pair[3:]      # Remaining chars
```

This is why separators must be removed - they would break the 3/3 split pattern.

## Testing

Run the comprehensive test suite:

```bash
python test_asset_pair_validation.py
```

Test coverage includes:
- ✅ Uppercase conversion
- ✅ Separator removal (underscore, dash, slash, space)
- ✅ Combined transformations
- ✅ Already standardized inputs
- ✅ Error handling
- ✅ Common forex pairs
- ✅ Common crypto pairs

## Benefits

1. **User Convenience** - Accept input in user's preferred format
2. **Error Prevention** - Eliminate formatting mistakes
3. **API Compatibility** - Ensure requests work with Alpha Vantage
4. **Consistency** - Uniform format throughout the system
5. **Validation** - Catch invalid inputs early

## Migration Notes

### Existing Code

No changes needed! Existing code continues to work:

```python
# This always worked and still works
engine.analyze_asset('BTCUSD')

# This now also works (previously might have failed)
engine.analyze_asset('btc-usd')
```

### Configuration Files

No configuration changes required. The standardization is automatic and transparent.

## Troubleshooting

### Common Issues

**Problem**: Asset pair with special characters
```bash
python main.py analyze BTC@USD
```
**Solution**: Only alphanumeric characters and common separators are accepted. Use standard format:
```bash
python main.py analyze BTC-USD
```

**Problem**: Very short asset pair
```bash
python main.py analyze BTC
```
**Solution**: Asset pairs must include both base and quote currencies (minimum 6 characters):
```bash
python main.py analyze BTCUSD
```

## Developer Notes

### Adding New Separators

To support additional separator characters, update the regex in `validation.py`:

```python
# Current pattern (removes: _ - / space)
standardized = re.sub(r'[^A-Za-z0-9]', '', asset_pair).upper()

# To allow dots but remove others:
standardized = re.sub(r'[^A-Za-z0-9.]', '', asset_pair).upper()
```

### Extending Validation

To add custom validation rules (e.g., minimum length check):

```python
def standardize_asset_pair(asset_pair: str) -> str:
    # ... existing code ...

    # Add custom validation
    if len(standardized) < 6:
        raise ValueError(f"Asset pair too short: {asset_pair}")

    return standardized
```

## Future Enhancements

Potential improvements:
- [ ] Asset pair type detection (crypto vs forex)
- [ ] Known pair validation (check against supported pairs)
- [ ] Fuzzy matching for typos
- [ ] Suggestions for invalid inputs
- [ ] Cached validation results

---

**Last Updated**: November 22, 2025
**Version**: 2.0
**Status**: ✅ Production Ready
