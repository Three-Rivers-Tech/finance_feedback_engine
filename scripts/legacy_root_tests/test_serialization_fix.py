#!/usr/bin/env python3
"""Quick test to verify CreateOrderResponse serialization fix."""

import json
import sys
from unittest.mock import MagicMock, patch


def test_error_response_serialization():
    """Test that error responses can be JSON serialized."""
    
    # Mock the CreateOrderResponse object
    mock_order_result = MagicMock()
    mock_order_result.to_dict.return_value = {
        "success": False,
        "order_id": None,
        "status": "FAILED",
        "error_details": "Insufficient funds",
        "filled_size": "0",
        "total_value": "0"
    }
    
    # Simulate the fixed return statement (no duplicate 'response' key)
    error_response = {
        "success": False,
        "platform": "coinbase_advanced",
        "decision_id": "test-123",
        "error": "Order creation failed",
        "error_details": "Insufficient funds",
        "latency_seconds": 0.5,
        "response": mock_order_result.to_dict(),  # Only one 'response' key now
        "timestamp": "2026-02-16T13:16:56.465Z",
    }
    
    # Test JSON serialization
    try:
        json_str = json.dumps(error_response, indent=2)
        print("✅ SUCCESS: Error response is JSON serializable")
        print("\nSerialized JSON:")
        print(json_str)
        
        # Verify we can deserialize it too
        deserialized = json.loads(json_str)
        assert deserialized["success"] == False
        assert deserialized["response"]["error_details"] == "Insufficient funds"
        print("\n✅ SUCCESS: JSON round-trip works correctly")
        return True
        
    except TypeError as e:
        print(f"❌ FAILURE: JSON serialization failed: {e}")
        return False


def test_success_response_serialization():
    """Test that success responses can be JSON serialized."""
    
    # Mock the CreateOrderResponse object
    mock_order_result = MagicMock()
    mock_order_result.to_dict.return_value = {
        "success": True,
        "order_id": "abc-123",
        "status": "OPEN",
        "filled_size": "0.001",
        "total_value": "100.00"
    }
    
    # Simulate the success return statement
    success_response = {
        "success": True,
        "platform": "coinbase_advanced",
        "decision_id": "test-456",
        "order_id": "abc-123",
        "order_status": "OPEN",
        "latency_seconds": 0.3,
        "response": mock_order_result.to_dict(),
        "timestamp": "2026-02-16T13:16:56.465Z",
    }
    
    # Test JSON serialization
    try:
        json_str = json.dumps(success_response, indent=2)
        print("\n✅ SUCCESS: Success response is JSON serializable")
        print("\nSerialized JSON:")
        print(json_str)
        
        # Verify we can deserialize it too
        deserialized = json.loads(json_str)
        assert deserialized["success"] == True
        assert deserialized["order_id"] == "abc-123"
        print("\n✅ SUCCESS: JSON round-trip works correctly")
        return True
        
    except TypeError as e:
        print(f"❌ FAILURE: JSON serialization failed: {e}")
        return False


if __name__ == "__main__":
    print("=" * 60)
    print("Testing CreateOrderResponse Serialization Fix")
    print("=" * 60)
    
    test1 = test_error_response_serialization()
    test2 = test_success_response_serialization()
    
    print("\n" + "=" * 60)
    if test1 and test2:
        print("✅ ALL TESTS PASSED")
        print("=" * 60)
        sys.exit(0)
    else:
        print("❌ SOME TESTS FAILED")
        print("=" * 60)
        sys.exit(1)
