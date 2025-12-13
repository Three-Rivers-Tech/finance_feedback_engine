import pandas as pd
from typing import Union, List, Dict, Any

# Define common financial data validation rules and error messages
VALIDATION_RULES = {
    "price": {
        "min": 0.0,
        "type": (int, float),
        "error_msg": "Price must be a non-negative numerical value."
    },
    "volume": {
        "min": 0,
        "type": int,
        "error_msg": "Volume must be a non-negative integer."
    },
    "timestamp": {
        "format": "ISO_8601", # Expecting ISO 8601 string or datetime objects
        "timezone": "UTC",
        "error_msg": "Timestamp must be a valid UTC ISO 8601 string or datetime object."
    },
    "currency_pair": {
        "format": "UPPERCASE_ALPHANUMERIC", # e.g., "BTCUSD", "EURUSD"
        "length": 6, # Assuming 3 for base and 3 for quote currency
        "error_msg": "Currency pair must be a 6-character uppercase alphanumeric string."
    },
    # TODO: Add more specific validation rules for other financial data types
    # e.g., 'stop_loss', 'take_profit', 'order_type', 'account_balance'.
    # These rules should be extensible and easily configurable, perhaps loaded from YAML.
}

class FinancialDataValidator:
    """
    A utility class for validating financial market data.

    This class provides methods to validate various aspects of financial data, 
    such as prices, volumes, timestamps, and currency pairs, ensuring data 
    quality before processing or storage.

    Implementation Notes:
    - **Robustness:** Aims to catch common data quality issues early in the
      data pipeline, preventing errors in downstream analytical or trading
      logic.
    - **Extensibility:** The `VALIDATION_RULES` dictionary can be easily
      extended or even loaded from an external configuration file (e.g., YAML)
      to support new data types or modify existing validation logic without
      code changes.
    - **Pandas Integration:** Designed to work efficiently with pandas DataFrames
      for batch validation, which is common in financial data processing.
    - **Granularity:** Provides validation at both individual value level and
      batch (DataFrame) level.
    - **Error Reporting:** Collects and reports all validation errors, rather
      than stopping at the first error, providing a comprehensive overview
      of data quality issues.

    TODO:
    - **Customizable Error Handling:** Allow callers to specify how errors are
      handled (e.g., raise an exception, return a boolean, return a detailed
      list of errors).
    - **Schema Validation:** Implement a method to validate entire DataFrame
      schemas (column names, dtypes) against a predefined financial data schema.
    - **Time Series Gaps/Duplicates:** Add checks for gaps, duplicates, or
      irregularities in time-series data.
    - **Cross-Field Validation:** Implement logic for validating relationships
      between different fields (e.g., `open < high`, `low < close`).
    """

    def __init__(self, rules: Dict = None):
        self.rules = rules if rules is not None else VALIDATION_RULES

    def _validate_value(self, value: Any, rule_name: str) -> List[str]:
        """Validates a single value against a specified rule."""
        errors = []
        rule = self.rules.get(rule_name)
        if not rule:
            # TODO: Consider if unknown rule names should raise an error or just skip validation.
            # For now, it silently passes.
            return errors

        expected_type = rule.get("type")
        if expected_type and not isinstance(value, expected_type):
            errors.append(rule["error_msg"] + f" (Expected type: {expected_type}, Got: {type(value)})")
            return errors # Type mismatch usually means other checks will fail

        if "min" in rule and isinstance(value, (int, float)) and value < rule["min"]:
            errors.append(rule["error_msg"] + f" (Value {value} is less than min {rule['min']})")

        if rule_name == "timestamp":
            # TODO: Implement robust timestamp validation using a library like dateutil or pandas.to_datetime
            # For now, a basic check.
            try:
                pd.to_datetime(value, utc=True)
            except (ValueError, TypeError):
                errors.append(rule["error_msg"] + f" (Invalid timestamp format or timezone for: {value})")
        
        if rule_name == "currency_pair":
            if not (isinstance(value, str) and value.isupper() and value.isalnum() and len(value) == rule.get("length")):
                errors.append(rule["error_msg"] + f" (Invalid currency pair format: {value})")

        # TODO: Add more specific format checks based on rule["format"]

        return errors

    def is_valid_price(self, price: Union[int, float]) -> bool:
        """Validates a single price value."""
        return not self._validate_value(price, "price")

    def is_valid_volume(self, volume: Union[int, float]) -> bool:
        """Validates a single volume value."""
        return not self._validate_value(volume, "volume")

    def is_valid_timestamp(self, timestamp: Any) -> bool:
        """Validates a single timestamp value."""
        return not self._validate_value(timestamp, "timestamp")

    def is_valid_currency_pair(self, currency_pair: str) -> bool:
        """Validates a single currency pair string."""
        return not self._validate_value(currency_pair, "currency_pair")

    def validate_single_entry(self, data: Dict[str, Any]) -> List[str]:
        """
        Validates a single dictionary entry (e.g., a single tick or candle).
        """
        all_errors = []
        for field, value in data.items():
            if field in self.rules:
                all_errors.extend(self._validate_value(value, field))
        return all_errors

    def validate_dataframe(self, df: pd.DataFrame) -> Dict[str, List[str]]:
        """
        Validates an entire pandas DataFrame, reporting errors per column.
        """
        column_errors: Dict[str, List[str]] = {}
        for column, rule in self.rules.items():
            if column in df.columns:
                col_errors = []
                for index, value in df[column].items():
                    # TODO: Optimize this loop for large DataFrames.
                    # Vectorized operations or `df.apply` with custom logic would be more performant.
                    errors = self._validate_value(value, column)
                    if errors:
                        col_errors.append(f"Row {index}: {'; '.join(errors)}")
                if col_errors:
                    column_errors[column] = col_errors
        return column_errors

# Example Usage (for demonstration within this stub)
if __name__ == "__main__":
    validator = FinancialDataValidator()

    # Test single entry validation
    valid_data = {
        "price": 123.45,
        "volume": 100,
        "timestamp": "2023-01-01T12:00:00Z",
        "currency_pair": "BTCUSD"
    }
    invalid_data = {
        "price": -10.0,
        "volume": "abc",
        "timestamp": "not-a-date",
        "currency_pair": "btcusd"
    }
    
    print("Validating single entry:")
    errors_valid = validator.validate_single_entry(valid_data)
    if not errors_valid:
        print("  Valid data is clean.")
    else:
        print("  Errors in valid data:", errors_valid)

    errors_invalid = validator.validate_single_entry(invalid_data)
    if errors_invalid:
        print("  Errors in invalid data:")
        for error in errors_invalid:
            print(f"    - {error}")
    else:
        print("  Invalid data unexpectedly clean.")

    # Test DataFrame validation
    df_data = {
        "price": [100.0, 200.5, -50.0, 300.0],
        "volume": [10, 20, 30, "forty"],
        "timestamp": ["2023-01-01T00:00:00Z", "2023-01-01T01:00:00Z", "invalid-time", "2023-01-01T03:00:00Z"],
        "currency_pair": ["BTCUSD", "ETHUSD", "INVALID", "EURUSD"]
    }
    test_df = pd.DataFrame(df_data)

    print("\nValidating DataFrame:")
    df_errors = validator.validate_dataframe(test_df)
    if df_errors:
        for column, errs in df_errors.items():
            print(f"  Column '{column}' errors:")
            for err in errs:
                print(f"    - {err}")
    else:
        print("  DataFrame is clean.")
