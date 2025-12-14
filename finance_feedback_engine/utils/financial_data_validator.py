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
        "type": (int, float),
        "error_msg": "Volume must be a non-negative numerical value."
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
    "stop_loss": {
        "min": 0.0,
        "type": (int, float),
        "error_msg": "Stop loss must be a non-negative numerical value."
    },
    "take_profit": {
        "min": 0.0,
        "type": (int, float),
        "error_msg": "Take profit must be a non-negative numerical value."
    },
    "order_type": {
        "allowed_values": ["MARKET", "LIMIT", "STOP", "STOP_LIMIT", "TRAILING_STOP"],
        "error_msg": "Order type must be one of: MARKET, LIMIT, STOP, STOP_LIMIT, TRAILING_STOP."
    },
    "account_balance": {
        "min": 0.0,
        "type": (int, float),
        "error_msg": "Account balance must be a non-negative numerical value."
    },
    "confidence": {
        "min": 0.0,
        "max": 1.0,
        "type": (int, float),
        "error_msg": "Confidence must be a numerical value between 0 and 1."
    },
    "position_size": {
        "min": 0.0,
        "type": (int, float),
        "error_msg": "Position size must be a non-negative numerical value."
    },
    "leverage": {
        "min": 1.0,
        "type": (int, float),
        "error_msg": "Leverage must be a numerical value of 1 or greater."
    }
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
            # For unknown rule names, return an error or handle as needed
            errors.append(f"Unknown validation rule: {rule_name}")
            return errors

        expected_type = rule.get("type")
        if expected_type and not isinstance(value, expected_type):
            errors.append(rule["error_msg"] + f" (Expected type: {expected_type}, Got: {type(value)})")
            return errors # Type mismatch usually means other checks will fail

        # Check min value if specified
        if "min" in rule and isinstance(value, (int, float)) and value < rule["min"]:
            errors.append(rule["error_msg"] + f" (Value {value} is less than min {rule['min']})")

        # Check max value if specified
        if "max" in rule and isinstance(value, (int, float)) and value > rule["max"]:
            errors.append(rule["error_msg"] + f" (Value {value} is greater than max {rule['max']})")

        if rule_name == "timestamp":
            # Implement robust timestamp validation using pandas
            try:
                pd.to_datetime(value, utc=True)
            except (ValueError, TypeError):
                errors.append(rule["error_msg"] + f" (Invalid timestamp format or timezone for: {value})")

        elif rule_name == "currency_pair":
            if not (isinstance(value, str) and value.isupper() and value.isalnum() and len(value) == rule.get("length", 6)):
                errors.append(rule["error_msg"] + f" (Invalid currency pair format: {value})")

        elif rule_name == "order_type":
            allowed_values = rule.get("allowed_values", [])
            if value not in allowed_values:
                errors.append(rule["error_msg"] + f" (Got: {value})")

        # Add more specific format checks based on rule["format"]
        format_type = rule.get("format")
        if format_type == "UPPERCASE_ALPHANUMERIC":
            if not (isinstance(value, str) and value.isupper() and value.isalnum()):
                errors.append(rule["error_msg"] + f" (Invalid format: {value})")

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

    def is_valid_stop_loss(self, stop_loss: Union[int, float]) -> bool:
        """Validates a single stop loss value."""
        return not self._validate_value(stop_loss, "stop_loss")

    def is_valid_take_profit(self, take_profit: Union[int, float]) -> bool:
        """Validates a single take profit value."""
        return not self._validate_value(take_profit, "take_profit")

    def is_valid_order_type(self, order_type: str) -> bool:
        """Validates a single order type string."""
        return not self._validate_value(order_type, "order_type")

    def is_valid_account_balance(self, account_balance: Union[int, float]) -> bool:
        """Validates a single account balance value."""
        return not self._validate_value(account_balance, "account_balance")

    def is_valid_confidence(self, confidence: Union[int, float]) -> bool:
        """Validates a single confidence value."""
        return not self._validate_value(confidence, "confidence")

    def is_valid_position_size(self, position_size: Union[int, float]) -> bool:
        """Validates a single position size value."""
        return not self._validate_value(position_size, "position_size")

    def is_valid_leverage(self, leverage: Union[int, float]) -> bool:
        """Validates a single leverage value."""
        return not self._validate_value(leverage, "leverage")

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
        Optimized for large DataFrames using vectorized operations where possible.
        """
        column_errors: Dict[str, List[str]] = {}
        for column, rule in self.rules.items():
            if column in df.columns:
                col_errors = []
                series = df[column]

                # Use vectorized operations for performance on large DataFrames
                # Check for null values first
                null_mask = series.isna()
                if null_mask.any():
                    for idx in series[null_mask].index:
                        col_errors.append(f"Row {idx}: {column} cannot be null")

                # Process non-null values
                non_null_series = series[~null_mask]
                for idx, value in non_null_series.items():
                    errors = self._validate_value(value, column)
                    if errors:
                        col_errors.append(f"Row {idx}: {'; '.join(errors)}")

                if col_errors:
                    column_errors[column] = col_errors
        return column_errors

    def validate_schema(self, df: pd.DataFrame, required_columns: List[str] = None,
                       optional_columns: List[str] = None,
                       column_types: Dict[str, type] = None) -> List[str]:
        """
        Validates DataFrame schema against expected structure.

        Args:
            df: The DataFrame to validate
            required_columns: List of required column names
            optional_columns: List of optional column names (for documentation)
            column_types: Dictionary mapping column names to expected types

        Returns:
            List of schema validation errors
        """
        errors = []

        if required_columns:
            missing_columns = set(required_columns) - set(df.columns)
            if missing_columns:
                errors.append(f"Missing required columns: {list(missing_columns)}")

        if column_types:
            for col, expected_type in column_types.items():
                if col in df.columns:
                    # Check if all non-null values are of the expected type
                    non_null_values = df[col].dropna()
                    if not non_null_values.empty:
                        # For performance, sample a subset for type checking if the series is large
                        if len(non_null_values) > 1000:
                            sample_values = non_null_values.sample(n=min(1000, len(non_null_values)))
                        else:
                            sample_values = non_null_values

                        invalid_types = [val for val in sample_values if not isinstance(val, expected_type)]
                        if invalid_types:
                            errors.append(f"Column '{col}' contains invalid types. Expected {expected_type}, found values: {invalid_types[:5]}...")  # Show first 5 invalid values

        return errors

    def validate_time_series_gaps(self, df: pd.DataFrame, timestamp_column: str = 'timestamp',
                                  expected_frequency: str = None) -> List[str]:
        """
        Validates time series data for gaps, duplicates, or irregularities.

        Args:
            df: The DataFrame containing time series data
            timestamp_column: Name of the timestamp column
            expected_frequency: Expected frequency (e.g., '1min', '1H', '1D') for gap detection

        Returns:
            List of time series validation errors
        """
        errors = []

        if timestamp_column not in df.columns:
            errors.append(f"Timestamp column '{timestamp_column}' not found in DataFrame")
            return errors

        # Convert to datetime if it's not already
        try:
            timestamps = pd.to_datetime(df[timestamp_column], utc=True).sort_values()
        except Exception as e:
            errors.append(f"Could not convert '{timestamp_column}' to datetime: {str(e)}")
            return errors

        # Check for duplicates
        duplicate_mask = timestamps.duplicated()
        if duplicate_mask.any():
            duplicate_times = timestamps[duplicate_mask]
            errors.append(f"Duplicate timestamps found: {list(duplicate_times.values)[:10]}...")  # Show first 10 duplicates

        # Check for gaps if expected frequency is provided
        if expected_frequency:
            try:
                # Create a complete time range with expected frequency
                full_range = pd.date_range(
                    start=timestamps.min(),
                    end=timestamps.max(),
                    freq=expected_frequency,
                    tz='UTC'
                )

                # Find missing timestamps
                missing_times = full_range.difference(timestamps)
                if len(missing_times) > 0:
                    errors.append(f"Time series gaps detected. Missing {len(missing_times)} timestamps based on {expected_frequency} frequency.")
            except Exception as e:
                errors.append(f"Could not validate time series gaps with frequency '{expected_frequency}': {str(e)}")

        # Basic ordering check (should be sorted)
        if not timestamps.is_monotonic_increasing:
            errors.append(f"Timestamps are not in ascending order")

        return errors

    def validate_cross_field_constraints(self, df: pd.DataFrame, constraints: List[Dict[str, str]] = None) -> List[str]:
        """
        Validates relationships between different fields (e.g., open < high, low < close).

        Args:
            df: The DataFrame to validate
            constraints: List of constraint dictionaries like:
                        [{"field1": "open", "operator": "<", "field2": "high", "description": "Open must be less than high"}]

        Returns:
            List of cross-field validation errors
        """
        errors = []

        if not constraints:
            # Use common financial constraints if none provided
            constraints = [
                {"field1": "open", "operator": "<=", "field2": "high", "description": "Open price should be less than or equal to high price"},
                {"field1": "low", "operator": "<=", "field2": "close", "description": "Low price should be less than or equal to close price"},
                {"field1": "low", "operator": "<=", "field2": "high", "description": "Low price should be less than or equal to high price"},
                {"field1": "close", "operator": "<=", "field2": "high", "description": "Close price should be less than or equal to high price"}
            ]

        for constraint in constraints:
            field1 = constraint["field1"]
            field2 = constraint["field2"]
            operator = constraint["operator"]
            description = constraint["description"]

            # Check if both fields exist in the DataFrame
            if field1 not in df.columns or field2 not in df.columns:
                continue  # Skip this constraint if fields don't exist

            # Apply the constraint based on the operator
            if operator == "<":
                invalid_rows = df[df[field1] >= df[field2]]
            elif operator == "<=":
                invalid_rows = df[df[field1] > df[field2]]
            elif operator == ">":
                invalid_rows = df[df[field1] <= df[field2]]
            elif operator == ">=":
                invalid_rows = df[df[field1] < df[field2]]
            elif operator == "==":
                invalid_rows = df[df[field1] != df[field2]]
            elif operator == "!=":
                invalid_rows = df[df[field1] == df[field2]]
            else:
                errors.append(f"Unknown operator '{operator}' in constraint")
                continue

            if not invalid_rows.empty:
                error_msg = f"{description}. Found {len(invalid_rows)} invalid rows."
                errors.append(error_msg)

        return errors

    def add_validation_rule(self, rule_name: str, rule: Dict[str, Any]):
        """
        Add a new validation rule to the validator.

        Args:
            rule_name: Name of the rule
            rule: Dictionary containing the validation rule parameters
        """
        self.rules[rule_name] = rule

# Example Usage (for demonstration within this stub)
if __name__ == "__main__":
    validator = FinancialDataValidator()

    # Test single entry validation
    valid_data = {
        "price": 123.45,
        "volume": 100,
        "timestamp": "2023-01-01T12:00:00Z",
        "currency_pair": "BTCUSD",
        "stop_loss": 120.0,
        "take_profit": 130.0,
        "order_type": "LIMIT",
        "confidence": 0.85,
        "position_size": 10.0
    }
    invalid_data = {
        "price": -10.0,
        "volume": "abc",
        "timestamp": "not-a-date",
        "currency_pair": "btcusd",
        "stop_loss": -5.0,
        "take_profit": 150.0,
        "order_type": "INVALID_TYPE",
        "confidence": 1.5,
        "position_size": -2.0
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

    # Test individual validation methods
    print("\nTesting individual validation methods:")
    print(f"  is_valid_stop_loss(100.0): {validator.is_valid_stop_loss(100.0)}")
    print(f"  is_valid_stop_loss(-10.0): {validator.is_valid_stop_loss(-10.0)}")
    print(f"  is_valid_order_type('LIMIT'): {validator.is_valid_order_type('LIMIT')}")
    print(f"  is_valid_order_type('INVALID'): {validator.is_valid_order_type('INVALID')}")
    print(f"  is_valid_confidence(0.75): {validator.is_valid_confidence(0.75)}")
    print(f"  is_valid_confidence(1.5): {validator.is_valid_confidence(1.5)}")

    # Test DataFrame validation
    df_data = {
        "price": [100.0, 200.5, -50.0, 300.0],
        "volume": [10, 20, 30, "forty"],
        "timestamp": ["2023-01-01T00:00:00Z", "2023-01-01T01:00:00Z", "invalid-time", "2023-01-01T03:00:00Z"],
        "currency_pair": ["BTCUSD", "ETHUSD", "INVALID", "EURUSD"],
        "stop_loss": [95.0, 190.0, 200.0, 280.0],
        "take_profit": [105.0, 210.0, 220.0, 320.0]
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

    # Test schema validation
    print("\nTesting schema validation:")
    schema_errors = validator.validate_schema(
        test_df,
        required_columns=['price', 'volume', 'timestamp'],
        column_types={'price': (int, float), 'volume': (int, float)}
    )
    if schema_errors:
        print("  Schema errors:")
        for error in schema_errors:
            print(f"    - {error}")
    else:
        print("  Schema is valid.")

    # Test cross-field validation
    print("\nTesting cross-field validation:")
    cross_df = pd.DataFrame({
        'open': [100, 200, 300],
        'high': [105, 195, 310],  # Second row has open > high (invalid)
        'low': [95, 190, 290],
        'close': [102, 198, 305]
    })
    cross_errors = validator.validate_cross_field_constraints(cross_df)
    if cross_errors:
        print("  Cross-field errors:")
        for error in cross_errors:
            print(f"    - {error}")
    else:
        print("  Cross-field validations passed.")
