
from finance_feedback_engine.cli.main import cli
import sys

if __name__ == '__main__':
    sys.argv = ['main.py', 'analyze', 'ETH-USD']
    cli()
