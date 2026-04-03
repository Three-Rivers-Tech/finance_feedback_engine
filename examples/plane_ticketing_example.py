#!/usr/bin/env python3
"""
Example: Using Plane ticketing integration in FFE

This shows how to create tickets for:
1. Trade executions (successful or failed)
2. Risk blocks
3. System errors
"""

import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ffe_plane_client import PlaneClient, create_execution_ticket, create_risk_ticket


def example_successful_trade():
    """Example: Create ticket for successful trade"""
    print("\n=== Example 1: Successful Trade Execution ===")
    
    issue_id = create_execution_ticket(
        decision_id="a88a49f6-553f-44f7-b980-ada8e1433533",
        symbol="BTC/USD",
        direction="LONG",
        confidence=0.85,
        error=None  # No error = successful execution
    )
    
    if issue_id:
        print(f"✅ Created execution ticket: {issue_id}")
        print(f"   View at: http://192.168.1.177:8088/workspaces/grovex-tech-solutions/projects/a751111c-fa00-4004-b725-d1174e488fe0/issues/{issue_id}")
    else:
        print("❌ Failed to create ticket")


def example_failed_trade():
    """Example: Create ticket for failed trade execution"""
    print("\n=== Example 2: Failed Trade Execution ===")
    
    issue_id = create_execution_ticket(
        decision_id="b88a49f6-553f-44f7-b980-ada8e1433534",
        symbol="ETH/USD",
        direction="SHORT",
        confidence=0.72,
        error="ConnectionError: Failed to connect to Coinbase API - timeout after 30s"
    )
    
    if issue_id:
        print(f"✅ Created execution ticket: {issue_id}")
    else:
        print("❌ Failed to create ticket")


def example_risk_block():
    """Example: Create ticket for risk-blocked trade"""
    print("\n=== Example 3: Risk Block ===")
    
    issue_id = create_risk_ticket(
        decision_id="c88a49f6-553f-44f7-b980-ada8e1433535",
        symbol="BTC/USD",
        risk_reason="Position size exceeds max_position_size limit",
        details={
            "requested_size": 1.5,
            "max_allowed": 1.0,
            "current_exposure": 0.8,
            "risk_level": "HIGH"
        }
    )
    
    if issue_id:
        print(f"✅ Created risk ticket: {issue_id}")
    else:
        print("❌ Failed to create ticket")


def example_advanced_usage():
    """Example: Advanced usage with PlaneClient directly"""
    print("\n=== Example 4: Advanced Usage ===")
    
    client = PlaneClient()
    
    # Create custom issue
    issue = client.create_issue(
        name="[FFE ALERT] Unusual market volatility detected",
        description="""
## Alert Details
- **Timestamp:** 2026-02-19 22:45:00
- **Symbol:** BTC/USD
- **Volatility:** 15.2% (24h)
- **Threshold:** 10.0%

## Recommended Action
Review risk parameters before next trade decision.
""",
        priority="high"
    )
    
    print(f"✅ Created custom issue: {issue['id']}")
    
    # Add a comment to the issue
    comment = client.add_comment(
        issue_id=issue['id'],
        comment="Automated volatility check completed. All systems nominal."
    )
    
    print(f"✅ Added comment to issue")
    
    # Update issue state (if you know the state ID)
    # client.update_issue(issue['id'], state="in_progress_state_id")


def example_list_ffe_issues():
    """Example: List existing FFE-related issues"""
    print("\n=== Example 5: List FFE Issues ===")
    
    client = PlaneClient()
    
    # Get all issues (basic list)
    issues = client.list_issues(limit=20)
    
    # Filter for FFE-related issues by name
    ffe_issues = [i for i in issues if 'FFE' in i['name'] or 'ffe' in i['name'].lower()]
    
    print(f"Found {len(ffe_issues)} FFE-related issues:")
    for issue in ffe_issues:
        state = issue.get('state_detail', {}).get('name', 'No State')
        print(f"  - {issue['name'][:60]}... [{state}]")


# Integration point for FFE core.py
def log_trade_to_plane(decision_id, symbol, direction, confidence, error=None):
    """
    Call this from core.py after trade execution
    
    Example integration in core.py:
    
    ```python
    from ffe_plane_client import create_execution_ticket
    
    # After executing trade
    try:
        result = platform.execute_trade(...)
        create_execution_ticket(
            decision_id=decision.id,
            symbol=decision.symbol,
            direction=decision.direction,
            confidence=decision.confidence,
            error=None
        )
    except Exception as e:
        create_execution_ticket(
            decision_id=decision.id,
            symbol=decision.symbol,
            direction=decision.direction,
            confidence=decision.confidence,
            error=str(e)
        )
    ```
    """
    return create_execution_ticket(
        decision_id=decision_id,
        symbol=symbol,
        direction=direction,
        confidence=confidence,
        error=error
    )


if __name__ == "__main__":
    # Run all examples
    print("=" * 60)
    print("FFE Plane Ticketing Integration Examples")
    print("=" * 60)
    
    # Check if API key is set
    if not os.getenv('PLANE_API_KEY'):
        print("\n⚠️  WARNING: PLANE_API_KEY not set in environment")
        print("Set it with: export PLANE_API_KEY='your_key_here'")
        sys.exit(1)
    
    try:
        # List existing issues first
        example_list_ffe_issues()
        
        # Uncomment to create test tickets:
        # example_successful_trade()
        # example_failed_trade()
        # example_risk_block()
        # example_advanced_usage()
        
        print("\n✅ All examples completed successfully!")
        print("\nTo create test tickets, uncomment the example calls in __main__")
        
    except Exception as e:
        print(f"\n❌ Error running examples: {e}")
        import traceback
        traceback.print_exc()
