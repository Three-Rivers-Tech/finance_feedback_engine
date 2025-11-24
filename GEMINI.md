# GEMINI.md

## Project Overview

This project is a Python-based command-line tool called "Finance Feedback Engine 2.0". It is an AI-powered trading decision tool that uses real-time market data to generate trading signals. The project is modular and supports various AI providers (including local models and CLI-based tools like Gemini), and trading platforms like Coinbase and Oanda.

The engine can analyze different asset pairs (cryptocurrencies and forex), providing a trading decision (BUY/SELL/HOLD) along with a confidence level and reasoning. It also features portfolio tracking, live trade monitoring, and backtesting capabilities.

**Key Technologies:**

*   **Language:** Python 3.8+
*   **CLI Framework:** `click`
*   **Data Handling:** `pandas`, `numpy`
*   **Configuration:** `PyYAML`
*   **APIs:** Alpha Vantage (for market data), Coinbase, Oanda
*   **AI Integration:** Pluggable architecture for different AI providers.

## Building and Running

### Installation

1.  **Install dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

### Configuration

1.  Copy the example configuration file:
    ```bash
    cp config/examples/default.yaml config/config.local.yaml
    ```
2.  Edit `config/config.local.yaml` to add your API keys for Alpha Vantage and your chosen trading platform.

### Running the Application

The main entry point is `main.py`. The application provides a command-line interface with several commands.

*   **Analyze an asset:**
    ```bash
    python main.py analyze BTCUSD
    ```
    You can specify an AI provider using the `--provider` flag:
    ```bash
    python main.py analyze BTCUSD --provider gemini
    ```

*   **Check account balance:**
    ```bash
    python main.py balance
    ```

*   **View portfolio dashboard:**
    ```bash
    python main.py dashboard
    ```

*   **View decision history:**
    ```bash
    python main.py history
    ```

*   **Run a backtest:**
    ```bash
    python main.py backtest BTCUSD --start 2023-01-01 --end 2023-12-31
    ```

*   **Start live trade monitoring:**
    ```bash
    python main.py monitor start
    ```

## Development Conventions

*   **Modular Architecture:** The project is organized into distinct modules for different functionalities (data providers, trading platforms, decision engine, etc.).
*   **Pluggable Components:** The trading platforms and AI providers are designed to be extensible. New platforms can be added by implementing the `BaseTradingPlatform` interface, and new AI providers can be integrated into the `DecisionEngine`.
*   **Configuration:** The application uses YAML files for configuration, allowing for easy customization of API keys, trading platforms, and other settings.
*   **CLI:** The `click` library is used to create a user-friendly command-line interface.
*   **Error Handling:** The application includes error handling to gracefully manage issues like missing configuration files or API errors.
*   **Logging:** The `logging` module is used for logging, with a verbose option available through the `--verbose` flag.
*   **Code Style:** The code follows standard Python conventions (PEP 8).
