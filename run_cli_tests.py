
import subprocess
import sys

def run_command(command):
    print(f"Running command: {command}")
    result = subprocess.run(command, shell=True, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"Command failed with exit code {result.returncode}")
        print(f"Stderr: {result.stderr}")
    else:
        print("Command succeeded")
    return result

def main():
    commands = [
        'python main.py backtest BTCUSD --start 2024-02-01 --end 2024-01-01 2>&1 | grep -q "start_date.*must be before"',
        'python main.py history --asset ZZZNONE --limit 1 >/dev/null 2>&1',
        'timeout 20 python main.py backtest BTCUSD --start 2024-01-01 --end 2024-01-02 2>&1 | grep -q "AI-Driven Backtest Summary"',
        'timeout 10 python main.py walk-forward BTCUSD --start-date 2024-01-01 --end-date 2024-01-10 --train-ratio 0.7 2>&1 | grep -q "Windows: train="',
        'timeout 10 python main.py monte-carlo BTCUSD --start-date 2024-01-01 --end-date 2024-01-02 --simulations 3 2>&1 | grep -q "Monte Carlo Simulation Results"'
    ]

    for command in commands:
        run_command(command)

if __name__ == "__main__":
    main()
