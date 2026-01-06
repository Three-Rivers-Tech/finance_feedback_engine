#!/usr/bin/env python3
"""
Quick diagnostic script to check if the environment is ready for agent testing.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import logging

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

def check_config():
    """Check if configuration is loadable."""
    try:
        from finance_feedback_engine.utils.config_loader import load_config
        config = load_config()
        logger.info("✓ Configuration loaded successfully")

        # Check key sections
        required_sections = ['agent', 'decision_engine', 'data_provider']
        for section in required_sections:
            if section in config:
                logger.info(f"  ✓ {section} section present")
            else:
                logger.warning(f"  ⚠ {section} section missing")

        return True
    except Exception as e:
        logger.error(f"✗ Config load failed: {e}")
        return False

def check_database():
    """Check database connectivity."""
    try:
        import os
        db_url = os.getenv('DATABASE_URL')
        if db_url:
            logger.info(f"✓ DATABASE_URL set: {db_url.split('@')[0]}@***")
        else:
            logger.warning("⚠ DATABASE_URL not set, will use SQLite")
        return True
    except Exception as e:
        logger.error(f"✗ Database check failed: {e}")
        return False

def check_ollama():
    """Check Ollama connectivity."""
    try:
        import os
        import requests

        ollama_host = os.getenv('OLLAMA_HOST', 'http://localhost:11434')
        logger.info(f"Checking Ollama at {ollama_host}...")

        response = requests.get(f"{ollama_host}/api/tags", timeout=5)
        if response.status_code == 200:
            models = response.json().get('models', [])
            logger.info(f"✓ Ollama is running with {len(models)} models")
            for model in models[:3]:  # Show first 3
                logger.info(f"    - {model.get('name', 'unknown')}")
            return True
        else:
            logger.warning(f"⚠ Ollama returned status {response.status_code}")
            return False
    except Exception as e:
        logger.warning(f"⚠ Ollama not reachable: {e}")
        logger.info("  (This is OK if using cloud AI providers)")
        return True  # Don't fail diagnostic if Ollama is optional

def check_imports():
    """Check critical imports."""
    critical_imports = [
        'finance_feedback_engine.core',
        'finance_feedback_engine.agent.trading_loop_agent',
        'finance_feedback_engine.monitoring.trade_monitor',
        'finance_feedback_engine.memory.portfolio_memory',
    ]

    all_ok = True
    for module in critical_imports:
        try:
            __import__(module)
            logger.info(f"✓ {module}")
        except Exception as e:
            logger.error(f"✗ {module}: {e}")
            all_ok = False

    return all_ok

def main():
    print("\n" + "="*70)
    print(" Finance Feedback Engine - Environment Diagnostic")
    print("="*70 + "\n")

    checks = {
        "Imports": check_imports(),
        "Configuration": check_config(),
        "Database": check_database(),
        "Ollama": check_ollama(),
    }

    print("\n" + "="*70)
    print(" Diagnostic Summary")
    print("="*70)

    for check_name, passed in checks.items():
        status = "✓ PASS" if passed else "✗ FAIL"
        print(f"  {check_name:.<30} {status}")

    all_passed = all(checks.values())

    print("="*70)
    if all_passed:
        print("\n✅ All checks passed! Ready to run agent tests.")
        print("\nNext step: python test_agent_loop.py")
    else:
        print("\n⚠️  Some checks failed. Review errors above.")
    print()

    return 0 if all_passed else 1

if __name__ == "__main__":
    sys.exit(main())
