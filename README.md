# Crypto Dashboard 

A feature-rich, real-time cryptocurrency tracking dashboard built with Python and Tkinter. This application connects to the Binance API to provide live price data, advanced candlestick charting, and transactional portfolio management, all wrapped in a sleek, custom-built, borderless user interface.
 
---

##  Key Features

*   **Real-Time Price Tracking**: Utilizes WebSockets for a high-frequency, low-latency stream of cryptocurrency price data directly from Binance.
*   **Fully Custom UI**: A modern, borderless window with a custom-built title bar and a professional dark theme, created entirely with Python's Tkinter and the Pillow library.
*   **Advanced Live Charting**:
    *   Interactive **candlestick charts** with trading volume.
    *   On-the-fly selection of different coins and timeframes (1m, 5m, 15m, 1h, etc.).
    *   Charts are powered by `mplfinance` and `matplotlib`.
*   **Dynamic Coin Management**:
    *   **Add Coins Instantly**: A dashboard-integrated search dialog allows you to find and add any USDT-paired coin to the tracker in real-time.
    *   **One-Click Remove**: Easily remove tracked coins directly from the dashboard.
    *   **Bulk Management**: A dedicated "Markets" tab for managing your tracked list in bulk.
*   **Transactional Portfolio Tracking**:
    *   Log individual **Buy** and **Sell** transactions.
    *   Automatically calculates total holdings, average buy cost, current market value, and **unrealized Profit/Loss**.
*   **Persistent State**: Your tracked coins and transaction history are automatically saved to a `config.json` file, so your setup is remembered every time you launch the app.
*   **Cross-Platform**: Built with standard Python libraries, making it compatible with Windows, macOS, and Linux.

---

##  Technology Stack

*   **Core**: Python 3
*   **GUI**: Tkinter (with `ttk` for modern widgets)
*   **Data & APIs**:
    *   `requests` for REST API calls (fetching historical data & market info).
    *   `websocket-client` for live data streams.
*   **Charting**: `matplotlib` & `mplfinance`
*   **Image Handling**: `Pillow` (PIL) for the custom UI elements.
*   **Data Handling**: `pandas`
*   **Desktop Notifications**: `plyer`

---

##  Setup and Installation

Follow these steps to get the application running on your local machine.

### 1. Prerequisites

Make sure you have **Python 3.7+** installed on your system. You can check this by running python --version

### 2. Install Dependencies

All required third-party libraries are listed in the `requirements.txt` file. Install them using pip:
```bash
pip install -r requirements.txt

```

---

##  Usage Guide

1.  **Connect**: Click the **"Connect"** button on the left panel to start the live data stream from Binance.
2.  **Add Coins**:
    *   **Quick Add**: On the **Dashboard** tab, click the **"+ Add Coin"** button. A search dialog will appear. Type the symbol you want (e.g., `SOLUSDT`) and double-click it to add it to the tracker instantly.
    *   **Bulk Add/Remove**: Go to the **Markets** tab to manage your tracked coins in bulk. Move coins between the "Available" and "Tracked" lists and click **"Apply Changes"**.
3.  **Remove a Coin**: On the **Dashboard**, simply click the **"❌"** in the "Action" column next to the coin you wish to remove.
4.  **View Charts**:
    *   Click on any coin in the **Dashboard** list to automatically switch to the **Live Chart** tab and view its chart.
    *   While on the chart tab, use the dropdown menus to select any of your other tracked coins or change the time interval.
5.  **Manage Portfolio**:
    *   Navigate to the **Portfolio** tab.
    *   Enter the details of a trade (Symbol, Type, Quantity, Price) and click **"Log Tx"** to record it.
    *   Your holdings, average cost, and P/L will be calculated and displayed automatically.
