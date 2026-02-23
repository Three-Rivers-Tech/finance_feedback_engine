"""
FFE Plane Ticketing Integration
Provides simple interface to create, update, and query Plane issues for FFE
"""

import os
import requests
from typing import Dict, List, Optional
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class PlaneClient:
    """Simple Plane API client for FFE ticketing integration"""
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        workspace_slug: Optional[str] = None,
        project_id: Optional[str] = None
    ):
        self.api_key = api_key or os.getenv('PLANE_API_KEY')
        self.base_url = base_url or os.getenv('PLANE_API_BASE', 'http://192.168.1.177:8088')
        self.workspace_slug = workspace_slug or os.getenv('PLANE_WORKSPACE_SLUG', 'three-rivers-tech-llc')
        self.project_id = project_id or os.getenv('PLANE_PROJECT_ID', 'a751111c-fa00-4004-b725-d1174e488fe0')
        
        if not self.api_key:
            raise ValueError("PLANE_API_KEY not found in environment or constructor")
        
        self.headers = {
            'X-Api-Key': self.api_key,
            'Content-Type': 'application/json'
        }
        self.session = requests.Session()
        self.session.headers.update(self.headers)
    
    def _make_request(self, method: str, endpoint: str, **kwargs) -> Dict:
        """Make authenticated request to Plane API"""
        url = f"{self.base_url}/api/v1/{endpoint}"
        try:
            response = self.session.request(method, url, **kwargs)
            response.raise_for_status()
            return response.json() if response.content else {}
        except requests.exceptions.RequestException as e:
            logger.error(f"Plane API request failed: {e}")
            if hasattr(e, 'response') and e.response is not None:
                logger.error(f"Response body: {e.response.text}")
            raise
    
    def create_issue(
        self,
        name: str,
        description: Optional[str] = None,
        priority: str = 'medium',
        labels: Optional[List[str]] = None,
        **kwargs
    ) -> Dict:
        """
        Create a new Plane issue
        
        Args:
            name: Issue title/name
            description: Issue description (markdown supported)
            priority: Priority level (urgent, high, medium, low, none)
            labels: List of label names (currently not used - needs label UUID lookup)
            **kwargs: Additional Plane issue fields
        
        Returns:
            Created issue data with id, url, etc.
        """
        endpoint = f"workspaces/{self.workspace_slug}/projects/{self.project_id}/issues/"
        
        payload = {
            "name": name,
            "project_id": self.project_id,
            **kwargs
        }
        
        if description:
            payload["description_html"] = description
        
        if priority:
            payload["priority"] = priority
        
        # Note: labels require UUIDs, not names - skipping for now
        # if labels:
        #     payload["labels"] = labels
        
        result = self._make_request('POST', endpoint, json=payload)
        logger.info(f"Created Plane issue: {result.get('id')} - {name}")
        return result
    
    def update_issue(
        self,
        issue_id: str,
        **kwargs
    ) -> Dict:
        """
        Update an existing Plane issue
        
        Args:
            issue_id: Plane issue UUID
            **kwargs: Fields to update (name, description_html, priority, state, etc.)
        
        Returns:
            Updated issue data
        """
        endpoint = f"workspaces/{self.workspace_slug}/projects/{self.project_id}/issues/{issue_id}/"
        
        result = self._make_request('PATCH', endpoint, json=kwargs)
        logger.info(f"Updated Plane issue: {issue_id}")
        return result
    
    def get_issue(self, issue_id: str) -> Dict:
        """Get issue details by ID"""
        endpoint = f"workspaces/{self.workspace_slug}/projects/{self.project_id}/issues/{issue_id}/"
        return self._make_request('GET', endpoint)
    
    def list_issues(
        self,
        state: Optional[str] = None,
        priority: Optional[str] = None,
        labels: Optional[List[str]] = None,
        limit: int = 100
    ) -> List[Dict]:
        """
        List issues with optional filters
        
        Args:
            state: Filter by state name
            priority: Filter by priority
            labels: Filter by label names
            limit: Maximum number of results
        
        Returns:
            List of issue dicts
        """
        endpoint = f"workspaces/{self.workspace_slug}/projects/{self.project_id}/issues/"
        
        params = {}
        if state:
            params['state'] = state
        if priority:
            params['priority'] = priority
        if labels:
            params['labels'] = ','.join(labels)
        
        result = self._make_request('GET', endpoint, params=params)
        issues = result.get('results', [])[:limit]
        return issues
    
    def add_comment(self, issue_id: str, comment: str) -> Dict:
        """Add a comment to an issue"""
        endpoint = f"workspaces/{self.workspace_slug}/projects/{self.project_id}/issues/{issue_id}/comments/"
        
        payload = {
            "comment_html": comment,
            "issue": issue_id
        }
        
        result = self._make_request('POST', endpoint, json=payload)
        logger.info(f"Added comment to issue {issue_id}")
        return result
    
    def create_execution_issue(
        self,
        decision_id: str,
        symbol: str,
        direction: str,
        confidence: float,
        error: Optional[str] = None
    ) -> Dict:
        """
        Create FFE execution-related issue
        
        Args:
            decision_id: FFE decision UUID
            symbol: Trading symbol (e.g. BTC/USD)
            direction: Trade direction (LONG, SHORT, HOLD)
            confidence: Model confidence (0-1)
            error: Error message if execution failed
        
        Returns:
            Created issue data
        """
        status = "⚠️ EXECUTION FAILED" if error else "✅ EXECUTED"
        name = f"[FFE {status}] {symbol} {direction} @ {confidence:.1%}"
        
        description = f"""
## Trade Decision
- **Symbol:** {symbol}
- **Direction:** {direction}
- **Confidence:** {confidence:.1%}
- **Decision ID:** `{decision_id}`
- **Timestamp:** {datetime.now().isoformat()}

"""
        
        if error:
            description += f"""
## Error
```
{error}
```
"""
        
        labels = ['ffe', 'trading', 'execution']
        if error:
            labels.append('error')
            priority = 'high'
        else:
            priority = 'medium'
        
        return self.create_issue(
            name=name,
            description=description,
            priority=priority,
            labels=labels
        )
    
    def create_risk_issue(
        self,
        decision_id: str,
        symbol: str,
        risk_reason: str,
        details: Optional[Dict] = None
    ) -> Dict:
        """
        Create FFE risk-blocked issue
        
        Args:
            decision_id: FFE decision UUID
            symbol: Trading symbol
            risk_reason: Why trade was blocked
            details: Additional risk details
        
        Returns:
            Created issue data
        """
        name = f"[FFE RISK BLOCKED] {symbol} - {risk_reason}"
        
        description = f"""
## Risk Block
- **Symbol:** {symbol}
- **Reason:** {risk_reason}
- **Decision ID:** `{decision_id}`
- **Timestamp:** {datetime.now().isoformat()}

"""
        
        if details:
            description += "\n## Details\n```json\n"
            import json
            description += json.dumps(details, indent=2)
            description += "\n```\n"
        
        return self.create_issue(
            name=name,
            description=description,
            priority='high',
            labels=['ffe', 'risk', 'blocked']
        )


# Convenience functions for FFE integration

def create_execution_ticket(
    decision_id: str,
    symbol: str,
    direction: str,
    confidence: float,
    error: Optional[str] = None
) -> Optional[str]:
    """Create execution ticket and return issue ID"""
    try:
        client = PlaneClient()
        issue = client.create_execution_issue(
            decision_id=decision_id,
            symbol=symbol,
            direction=direction,
            confidence=confidence,
            error=error
        )
        return issue.get('id')
    except Exception as e:
        logger.error(f"Failed to create execution ticket: {e}")
        return None


def create_risk_ticket(
    decision_id: str,
    symbol: str,
    risk_reason: str,
    details: Optional[Dict] = None
) -> Optional[str]:
    """Create risk-blocked ticket and return issue ID"""
    try:
        client = PlaneClient()
        issue = client.create_risk_issue(
            decision_id=decision_id,
            symbol=symbol,
            risk_reason=risk_reason,
            details=details
        )
        return issue.get('id')
    except Exception as e:
        logger.error(f"Failed to create risk ticket: {e}")
        return None


if __name__ == "__main__":
    # Test the integration
    import sys
    
    logging.basicConfig(level=logging.INFO)
    
    client = PlaneClient()
    
    # List recent FFE issues
    print("\n=== Recent FFE Issues ===")
    issues = client.list_issues(labels=['ffe'], limit=10)
    for issue in issues:
        print(f"- {issue['name']} [{issue.get('state_detail', {}).get('name', 'No State')}]")
    
    # Test creating an issue (if --test flag provided)
    if '--test' in sys.argv:
        print("\n=== Creating Test Issue ===")
        test_issue = client.create_execution_issue(
            decision_id="test-decision-123",
            symbol="BTC/USD",
            direction="LONG",
            confidence=0.85,
            error=None
        )
        print(f"Created test issue: {test_issue['id']}")
        print(f"URL: {client.base_url}/workspaces/{client.workspace_slug}/projects/{client.project_id}/issues/{test_issue['id']}")
