"""Tests for utils.financial_data_validator module."""

import pandas as pd
from datetime import datetime
from finance_feedback_engine.utils.financial_data_validator import (
    FinancialDataValidator,
    VALIDATION_RULES
)


class TestValidationRules:
    """Test validation rules configuration."""
    
    def test_validation_rules_exist(self):
        """Test that validation rules are defined."""
        assert VALIDATION_RULES is not None
        assert isinstance(VALIDATION_RULES, dict)
    
    def test_price_validation_rules(self):
        """Test price validation rules are defined."""
        assert 'price' in VALIDATION_RULES
        assert 'min' in VALIDATION_RULES['price']
        assert VALIDATION_RULES['price']['min'] >= 0
    
    def test_volume_validation_rules(self):
        """Test volume validation rules are defined."""
        assert 'volume' in VALIDATION_RULES
        assert 'min' in VALIDATION_RULES['volume']


class TestFinancialDataValidator:
    """Test suite for FinancialDataValidator class."""
    
    def test_init(self):
        """Test validator initialization."""
        validator = FinancialDataValidator()
        assert validator is not None
    
    def test_validate_price_valid(self):
        """Test validation of valid prices."""
        validator = FinancialDataValidator()
        
        # Test various valid prices
        assert validator.is_valid_price(100.50)
        assert validator.is_valid_price(0.01)
        assert validator.is_valid_price(50000)
    
    def test_validate_price_invalid(self):
        """Test validation of invalid prices."""
        validator = FinancialDataValidator()
        
        # Test invalid prices
        assert validator.is_valid_price(-10.5) is False
    
    def test_validate_volume_valid(self):
        """Test validation of valid volumes."""
        validator = FinancialDataValidator()
        
        assert validator.is_valid_volume(1000)
        assert validator.is_valid_volume(0)  # Zero volume may be valid
    
    def test_validate_volume_invalid(self):
        """Test validation of invalid volumes."""
        validator = FinancialDataValidator()
        
        assert validator.is_valid_volume(-100) is False
    
    def test_validate_timestamp(self):
        """Test timestamp validation."""
        validator = FinancialDataValidator()
        
        # Valid timestamp
        valid_ts = datetime.utcnow().isoformat()
        result = validator.is_valid_timestamp(valid_ts)
        # Just check it doesn't raise an exception
        assert True
    
    def test_validate_currency_pair(self):
        """Test currency pair validation."""
        validator = FinancialDataValidator()
        
        # Valid pairs
        assert validator.is_valid_currency_pair('BTCUSD')
        assert validator.is_valid_currency_pair('EURUSD')
    
    def test_validate_dataframe(self):
        """Test DataFrame validation."""
        validator = FinancialDataValidator()
        
        # Create a sample DataFrame
        df = pd.DataFrame({
            'timestamp': [datetime.utcnow().isoformat()],
            'price': [50000.0],
            'volume': [1000]
        })
        
        # Validate DataFrame (should not raise exception)
        result = validator.validate_dataframe(df)
        assert result == {}
    
class TestEdgeCases:
    """Test edge cases for data validation."""
    
    def test_zero_price(self):
        """Test handling of zero price."""
        validator = FinancialDataValidator()
        
        assert validator.is_valid_price(0.0) is True
    
    def test_very_large_price(self):
        """Test handling of very large prices."""
        validator = FinancialDataValidator()
        
        large_price = 1000000000.0
        assert validator.is_valid_price(large_price)
    
    def test_none_values(self):
        """Test handling of None values."""
        validator = FinancialDataValidator()
        
        assert validator.is_valid_price(None) is False


class TestBatchValidation:
    """Test batch validation capabilities."""
    
    def test_validate_multiple_prices(self):
        """Test validating multiple prices at once."""
        validator = FinancialDataValidator()
        
        prices = [100.0, 200.0, 300.0, 400.0]
        
        # Validate each price
        for price in prices:
            assert validator.is_valid_price(price)
    
class TestIntegration:
    """Integration tests for validator."""
    
    def test_complete_market_data_validation(self):
        """Test validation of complete market data structure."""
        validator = FinancialDataValidator()
        
        market_data = {
            'asset_pair': 'BTCUSD',
            'timestamp': datetime.utcnow().isoformat(),
            'open': 50000.0,
            'high': 51000.0,
            'low': 49000.0,
            'close': 50500.0,
            'volume': 1000000
        }
        
        # Validate each field
        assert validator.is_valid_currency_pair(market_data['asset_pair'])
        assert validator.is_valid_timestamp(market_data['timestamp'])
        assert validator.is_valid_price(market_data['close'])
        assert validator.is_valid_volume(market_data['volume'])
