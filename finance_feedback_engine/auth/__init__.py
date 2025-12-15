"""
Authentication module for Finance Feedback Engine API.

Provides secure API key management with:
- Constant-time comparison
- Rate limiting
- Audit logging
- Database persistence
"""

from .auth_manager import AuthManager, AuthAttempt, RateLimiter

__all__ = ["AuthManager", "AuthAttempt", "RateLimiter"]
