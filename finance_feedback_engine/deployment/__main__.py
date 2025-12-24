"""
Main entry point for deployment orchestrator.

Allows running as: python -m finance_feedback_engine.deployment
"""

from .cli import cli

if __name__ == "__main__":
    cli()
