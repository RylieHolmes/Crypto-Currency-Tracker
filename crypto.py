import tkinter as tk
from tkinter import ttk, font, messagebox
import json
import os
import queue
import threading
import time
from collections import deque, defaultdict
from datetime import datetime

# --- Required 3rd-party libraries ---
import requests
from plyer import notification
import matplotlib
matplotlib.use("TkAgg")
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.gridspec import GridSpec
import mplfinance as mpf
import pandas as pd
from PIL import Image, ImageDraw, ImageTk
import websocket

# --- Configuration & Theme ---
CONFIG_FILE = "config.json"
MAX_CHART_POINTS = 100

# --- Theme Dictionaries ---
THEME_DARK = {
    "root_bg": "#1D1D1D", "content_bg": "#252525", "title_bar": "#2D2D2D",
    "text": "#E0E0E0", "accent": "#4A90E2", "accent_hover": "#64A5F3",
    "border": "#3A3A3A", "green": "#7ED321", "red": "#D0021B", "placeholder": "#666666"
}
FONT_UI = ("Segoe UI", 10)
FONT_UI_BOLD = ("Segoe UI", 10, "bold")
FONT_TITLE = ("Segoe UI", 11, "bold")

# --- Helper function to create rounded images for buttons ---
def create_rounded_image(width, height, radius, color):
    image = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((0, 0, width - 1, height - 1), radius, fill=color)
    return ImageTk.PhotoImage(image)

# --- Custom Widget with Placeholder Text ---
class PlaceholderEntry(ttk.Entry):
    def __init__(self, master=None, placeholder="PLACEHOLDER", color='grey', **kwargs):
        super().__init__(master, **kwargs)
        self.placeholder = placeholder; self.placeholder_color = color
        self.default_fg_color = self['foreground']
        self.bind("<FocusIn>", self._focus_in); self.bind("<FocusOut>", self._focus_out)
        self.put_placeholder()
    def put_placeholder(self):
        self.insert(0, self.placeholder); self['foreground'] = self.placeholder_color
    def _focus_in(self, *args):
        if self['foreground'] == self.placeholder_color:
            self.delete('0', 'end'); self['foreground'] = self.default_fg_color
    def _focus_out(self, *args):
        if not self.get(): self.put_placeholder()

class EliteCryptoDashboard:
    def __init__(self, root):
        self.root = root; self.current_theme = THEME_DARK
        self._setup_main_window()
        self.settings = self.SettingsManager(CONFIG_FILE)
        self.api = self.BinanceAPI(self.data_callback, self.log_callback, self.status_callback, list(self.settings.get("tracked_pairs")))
        self.last_prices = {}; self.stats_24h = defaultdict(dict)
        self.selected_chart_coin = self.settings.get("tracked_pairs")[0].upper() if self.settings.get("tracked_pairs") else "BTCUSDT"
        self.selected_chart_interval = "5m"
        self._configure_styles(); self._create_layout()
        self.is_running = threading.Event(); self.is_running.set()
        self.root.after(100, self.process_ui_queue)
        self.api.start_initial_fetch()
        self.api.start_24h_stats_updater()

    def _setup_main_window(self):
        self.root.overrideredirect(True); self.root.geometry("1400x850"); self.root.minsize(1200, 700)
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        self.root.bind("<Map>", self._on_restore)

    def _create_custom_title_bar(self):
        self.title_bar = ttk.Frame(self.root, style="Title.TFrame"); self.title_bar.pack(side=tk.TOP, fill=tk.X)
        self.title_bar.bind("<ButtonPress-1>", self._start_move); self.title_bar.bind("<B1-Motion>", self._do_move)
        ttk.Label(self.title_bar, text="Elite Crypto Dashboard", style="Title.TLabel").pack(side=tk.LEFT, padx=15, pady=8)
        ttk.Button(self.title_bar, text='✕', command=self.on_closing, style="Close.TButton", width=4).pack(side=tk.RIGHT, padx=(0, 5))
        ttk.Button(self.title_bar, text='—', command=self._minimize_window, style="Title.TButton", width=4).pack(side=tk.RIGHT)

    def _start_move(self, event): self.x, self.y = event.x, event.y
    def _do_move(self, event):
        x, y = self.root.winfo_x() + (event.x - self.x), self.root.winfo_y() + (event.y - self.y)
        self.root.geometry(f"+{x}+{y}")
    def _minimize_window(self): self.root.overrideredirect(False); self.root.iconify()
    def _on_restore(self, event): self.root.overrideredirect(True)

    def _configure_styles(self):
        theme = self.current_theme
        self.style = ttk.Style(self.root); self.style.theme_use("clam")
        self.btn_img = create_rounded_image(120, 36, 8, theme["content_bg"])
        self.btn_img_hover = create_rounded_image(120, 36, 8, theme["border"])
        self.root.config(bg=theme["root_bg"])
        self.style.configure(".", background=theme["root_bg"], foreground=theme["text"], font=FONT_UI, borderwidth=0)
        self.style.configure("TFrame", background=theme["root_bg"])
        self.style.configure("Title.TFrame", background=theme["title_bar"])
        self.style.configure("Title.TLabel", background=theme["title_bar"], font=FONT_TITLE)
        self.style.configure("Title.TButton", background=theme["title_bar"], foreground=theme["text"], font=FONT_UI_BOLD)
        self.style.map("Title.TButton", background=[("active", theme["border"])])
        self.style.configure("Close.TButton", background=theme["title_bar"], foreground=theme["text"], font=FONT_UI_BOLD)
        self.style.map("Close.TButton", background=[("active", theme["red"])])
        self.style.configure('Rounded.TButton', font=FONT_UI_BOLD, foreground=theme["accent"], background=theme["root_bg"], borderwidth=0, relief='flat', anchor='center', padding=0)
        self.style.map('Rounded.TButton', background=[('active', theme["root_bg"]), ('disabled', theme["root_bg"])], foreground=[('disabled', theme["border"])])
        self.style.configure("Treeview", background=theme["content_bg"], foreground=theme["text"], fieldbackground=theme["content_bg"], rowheight=30)
        self.style.configure("Treeview.Heading", background=theme["root_bg"], font=FONT_UI_BOLD, padding=8)
        self.style.map("Treeview", background=[("selected", theme["accent"]), ("!selected", "hover", theme["border"])])
        self.style.configure("TNotebook", background=theme["root_bg"], tabmargins=[10, 10, 10, 0])
        self.style.configure("TNotebook.Tab", background=theme["root_bg"], foreground=theme["border"], padding=(15, 8), font=FONT_UI_BOLD)
        self.style.map("TNotebook.Tab", background=[("selected", theme["content_bg"])], foreground=[("selected", theme["accent"])])
        self.style.configure("TEntry", fieldbackground=theme["content_bg"], foreground=theme["text"], insertcolor=theme["text"], bordercolor=theme["border"], lightcolor=theme["content_bg"], darkcolor=theme["content_bg"])
        self.style.configure("TCombobox", fieldbackground=theme["content_bg"], foreground=theme["text"], selectbackground=theme["content_bg"], selectforeground=theme["text"], arrowcolor=theme["text"], bordercolor=theme["border"])
        self.style.map('TCombobox', fieldbackground=[('readonly', theme["content_bg"])])
        self.style.configure("Vertical.TScrollbar", troughcolor=theme["root_bg"], background=theme["content_bg"], bordercolor=theme["root_bg"], arrowcolor=theme["text"])
        self.style.map("Vertical.TScrollbar", background=[('active', theme["border"])])

    def _create_rounded_button(self, parent, text, command, width=120, height=36):
        frame = tk.Frame(parent, bg=self.current_theme["root_bg"], width=width, height=height); frame.pack_propagate(False)
        bg_label = tk.Label(frame, image=self.btn_img, bg=self.current_theme["root_bg"]); bg_label.place(x=0, y=0, relwidth=1, relheight=1)
        text_label = tk.Label(frame, text=text, font=FONT_UI_BOLD, fg=self.current_theme["accent"], bg=self.current_theme["content_bg"]); text_label.place(x=0, y=0, relwidth=1, relheight=1)
        for widget in [frame, text_label, bg_label]:
            widget.bind("<Button-1>", lambda e, c=command: c()); widget.bind("<Enter>", lambda e: bg_label.config(image=self.btn_img_hover)); widget.bind("<Leave>", lambda e: bg_label.config(image=self.btn_img))
        return frame

    def _create_layout(self):
        self._create_custom_title_bar()
        self.control_panel = ttk.Frame(self.root, width=280, padding=20); self.control_panel.pack(side=tk.LEFT, fill=tk.Y)
        main_content = ttk.Frame(self.root, padding=(0, 10, 10, 10)); main_content.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)
        self.connection_status_var = tk.StringVar(value="Status: Disconnected")
        self._create_rounded_button(self.control_panel, "Connect", self.api.connect).pack(fill=tk.X, pady=(0, 5))
        self._create_rounded_button(self.control_panel, "Disconnect", self.api.disconnect).pack(fill=tk.X, pady=(0, 10))
        ttk.Label(self.control_panel, textvariable=self.connection_status_var, font=FONT_UI).pack(anchor="w", pady=(0, 20))
        self.total_value_var = tk.StringVar(value="$0.00")
        ttk.Label(self.control_panel, text="Portfolio Value", font=FONT_UI_BOLD).pack(anchor="w")
        ttk.Label(self.control_panel, textvariable=self.total_value_var, font=("Segoe UI", 20, "bold"), foreground=self.current_theme["accent"]).pack(anchor="w", pady=(0, 30))
        self.notebook = ttk.Notebook(main_content); self.notebook.pack(fill=tk.BOTH, expand=True)
        self.dashboard_tab = self.DashboardTab(self.notebook, self)
        self.portfolio_tab = self.PortfolioTab(self.notebook, self)
        self.chart_tab = self.ChartingTab(self.notebook, self)
        self.markets_tab = self.MarketsTab(self.notebook, self)

    def process_ui_queue(self):
        if not self.is_running.is_set(): return
        try: self.api.process_queue()
        except queue.Empty: pass
        finally: self.root.after(100, self.process_ui_queue)
    def data_callback(self, type, data):
        if type == "kline":
            self.last_prices[data["s"]] = float(data["k"]["c"])
            self.dashboard_tab.update_dashboard(data["s"])
            self.portfolio_tab.update_portfolio_values()
            self.chart_tab.append_live_data(data)
        elif type == "24h_stats":
            for ticker in data: self.stats_24h[ticker['symbol']] = ticker
            self.dashboard_tab.populate_initial_data()
    def log_callback(self, msg): print(msg)
    def status_callback(self, status): self.connection_status_var.set(f"Status: {status}")
    def on_closing(self):
        self.is_running.clear(); self.settings.save(); self.api.disconnect()
        time.sleep(0.1); self.root.destroy()
    def add_coin_to_tracker(self, symbol):
        symbol = symbol.lower()
        current_tracked = self.settings.get('tracked_pairs')
        if symbol not in current_tracked:
            current_tracked.append(symbol)
            self.settings.set("tracked_pairs", current_tracked); self.settings.save()
            self.api.update_tracked_pairs(self.settings.get("tracked_pairs"))
            self.dashboard_tab.update_dashboard(symbol.upper())
            self.log_callback(f"Added {symbol.upper()} to tracker.")
    def remove_coin_from_tracker(self, symbol):
        symbol = symbol.lower()
        current_tracked = self.settings.get('tracked_pairs')
        if symbol in current_tracked:
            current_tracked.remove(symbol)
            self.settings.set("tracked_pairs", current_tracked); self.settings.save()
            self.api.update_tracked_pairs(self.settings.get("tracked_pairs"))
            self.dashboard_tab.remove_coin(symbol.upper())
            self.log_callback(f"Removed {symbol.upper()} from tracker.")

    class SettingsManager:
        def __init__(self, fp): self.fp = fp; self.config = self.load()
        def load(self):
            try:
                with open(self.fp, 'r') as f: return json.load(f)
            except: return {"tracked_pairs": ["btcusdt", "ethusdt"], "transactions": []}
        def save(self):
            with open(self.fp, 'w') as f: json.dump(self.config, f, indent=4)
        def get(self, k): return self.config.get(k, [])
        def set(self, k, v): self.config[k] = v

    class BinanceAPI:
        def __init__(self, data_cb, log_cb, status_cb, tracked):
            self.ws, self.ws_thread = None, None
            self.data_cb, self.log_cb, self.status_cb = data_cb, log_cb, status_cb
            self.is_connected, self.is_running = threading.Event(), threading.Event()
            self.queue = queue.Queue()
            self.tracked_pairs = set(p.lower() for p in tracked)
        def connect(self):
            if self.is_running.is_set(): return
            self.is_running.set()
            self.ws_thread = threading.Thread(target=self._run_websocket, daemon=True); self.ws_thread.start()
            self.status_cb("Connecting...")
        def disconnect(self):
            if not self.is_running.is_set(): return
            self.is_running.clear()
            if self.ws: self.ws.close()
        def process_queue(self): self.data_cb(*self.queue.get_nowait())
        def _run_websocket(self):
            self.ws = websocket.WebSocketApp("wss://stream.binance.com:9443/ws", on_open=self._on_open, on_message=self._on_message, on_error=self._on_error, on_close=self._on_close)
            while self.is_running.is_set(): self.ws.run_forever(ping_interval=20, ping_timeout=10); time.sleep(1)
        def _on_open(self, ws):
            self.is_connected.set(); self.log_cb("WebSocket Connected"); self.status_cb("Connected")
            self.subscribe(self.tracked_pairs)
        def _on_message(self, ws, msg):
            data = json.loads(msg)
            if 'k' in data: self.queue.put(("kline", data))
        def _on_error(self, ws, err): self.log_cb(f"WebSocket Error: {err}")
        def _on_close(self, ws, code, msg):
            self.is_connected.clear(); self.log_cb("WebSocket Closed"); self.status_cb("Disconnected")
        def update_tracked_pairs(self, new_pairs_list):
            new_tracked = set(p.lower() for p in new_pairs_list)
            to_sub, to_unsub = new_tracked - self.tracked_pairs, self.tracked_pairs - new_tracked
            self.subscribe(to_sub); self.unsubscribe(to_unsub)
            self.tracked_pairs = new_tracked
        def subscribe(self, pairs):
            if not self.is_connected.is_set() or not pairs: return
            msg = json.dumps({"method": "SUBSCRIBE", "params": [f"{p.lower()}@kline_1m" for p in pairs], "id": 1})
            self.ws.send(msg); self.log_cb(f"Subscribed to: {', '.join(pairs)}")
        def unsubscribe(self, pairs):
            if not self.is_connected.is_set() or not pairs: return
            msg = json.dumps({"method": "UNSUBSCRIBE", "params": [f"{p.lower()}@kline_1m" for p in pairs], "id": 2})
            self.ws.send(msg); self.log_cb(f"Unsubscribed from: {', '.join(pairs)}")
        def start_initial_fetch(self): threading.Thread(target=self._fetch_24h_stats, daemon=True).start()
        def start_24h_stats_updater(self): threading.Thread(target=self._periodic_24h_stats_fetch, daemon=True).start()
        def _fetch_24h_stats(self):
            try:
                res = requests.get("https://api.binance.com/api/v3/ticker/24hr", timeout=10)
                res.raise_for_status(); self.queue.put(("24h_stats", res.json()))
            except requests.RequestException as e: self.log_cb(f"Error fetching initial stats: {e}")
        def _periodic_24h_stats_fetch(self):
            time.sleep(30)
            while self.is_running.is_set(): self._fetch_24h_stats(); time.sleep(30)
        def get_all_usdt_symbols(self):
            try:
                res = requests.get("https://api.binance.com/api/v3/exchangeInfo", timeout=10)
                res.raise_for_status()
                return [s['symbol'] for s in res.json()['symbols'] if s['symbol'].endswith('USDT') and s['status'] == 'TRADING']
            except requests.RequestException as e: self.log_cb(f"Error fetching symbols: {e}"); return []
        def get_historical_klines(self, symbol, interval):
            try:
                res = requests.get(f"https://api.binance.com/api/v3/klines?symbol={symbol.upper()}&interval={interval}&limit=100", timeout=10)
                res.raise_for_status()
                df = pd.DataFrame(res.json(), columns=['timestamp', 'Open', 'High', 'Low', 'Close', 'Volume', 'ct', 'qav', 't', 'tbbav', 'tbqav', 'i'])
                df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms'); df.set_index('timestamp', inplace=True)
                for col in ['Open', 'High', 'Low', 'Close', 'Volume']: df[col] = pd.to_numeric(df[col])
                return df
            except requests.RequestException as e: self.log_cb(f"Error fetching klines for {symbol}: {e}"); return pd.DataFrame()

    class DashboardTab(ttk.Frame):
        def __init__(self, parent, app):
            super().__init__(parent); self.app = app; parent.add(self, text="Dashboard", padding=10)
            header = ttk.Frame(self); header.pack(fill=tk.X, pady=(0, 5))
            ttk.Label(header, text="Tracked Coins", font=FONT_UI_BOLD).pack(side=tk.LEFT)
            self.app._create_rounded_button(header, "+ Add Coin", self._open_add_coin_dialog, width=100, height=36).pack(side=tk.RIGHT)
            cols = ("Symbol", "Price", "24h %", "24h High", "24h Low", "24h Volume", "Action")
            self.tree = ttk.Treeview(self, columns=cols, show="headings", style="Treeview")
            for col in cols: self.tree.heading(col, text=col); self.tree.column(col, anchor='center', width=100)
            self.tree.column("Action", width=50, anchor='center')
            self.tree.pack(fill=tk.BOTH, expand=True)
            self.tree.bind("<<TreeviewSelect>>", self._on_select)
            self.tree.bind("<Button-1>", self._on_tree_click)
        def _open_add_coin_dialog(self): CoinSearchDialog(self.app.root, self.app)
        def populate_initial_data(self):
            for symbol in self.app.settings.get("tracked_pairs"): self.update_dashboard(symbol.upper())
        def update_dashboard(self, symbol):
            price = self.app.last_prices.get(symbol, 0)
            stats = self.app.stats_24h.get(symbol, {})
            change = float(stats.get('priceChangePercent', 0.0))
            values = (symbol, f"${price:,.4f}" if price > 0 else "Loading...", f"{change:.2f}%", f"${float(stats.get('highPrice', 0)):,.4f}",
                      f"${float(stats.get('lowPrice', 0)):,.4f}", f"${float(stats.get('quoteVolume', 0)):,.0f}", "❌")
            tag = "up" if change > 0 else "down"
            if self.tree.exists(symbol): self.tree.item(symbol, values=values, tags=(tag,))
            else: self.tree.insert("", "end", iid=symbol, values=values, tags=(tag,))
        def _on_select(self, event):
            if not self.tree.selection(): return
            self.app.selected_chart_coin = self.tree.item(self.tree.selection()[0], "values")[0]
            if self.app.selected_chart_coin == "Loading...": return
            self.app.chart_tab.update_chart_selection(); self.app.chart_tab.plot_chart(); self.app.notebook.select(self.app.chart_tab)
        def _on_tree_click(self, event):
            region = self.tree.identify("region", event.x, event.y)
            if region == "cell":
                col = self.tree.identify_column(event.x)
                if col == "#7": # Action column
                    item = self.tree.identify_row(event.y)
                    symbol = self.tree.item(item, "values")[0]
                    if messagebox.askyesno("Confirm", f"Are you sure you want to remove {symbol}?"):
                        self.app.remove_coin_from_tracker(symbol)
        def remove_coin(self, symbol):
            if self.tree.exists(symbol): self.tree.delete(symbol)

    class PortfolioTab(ttk.Frame):
        def __init__(self, parent, app):
            super().__init__(parent); self.app = app; parent.add(self, text="Portfolio", padding=10)
            self._create_widgets(); self.recalculate_portfolio()
        def _create_widgets(self):
            form = ttk.Frame(self); form.pack(fill=tk.X, pady=10)
            theme = self.app.current_theme
            self.symbol_entry = PlaceholderEntry(form, "BTC", theme["placeholder"], width=12, style="TEntry"); self.symbol_entry.pack(side=tk.LEFT, padx=5, ipady=4)
            self.type_combo = ttk.Combobox(form, values=['Buy', 'Sell'], width=5, style="TCombobox"); self.type_combo.set('Buy'); self.type_combo.pack(side=tk.LEFT, padx=5)
            self.qty_entry = PlaceholderEntry(form, "Quantity", theme["placeholder"], width=15, style="TEntry"); self.qty_entry.pack(side=tk.LEFT, padx=5, ipady=4)
            self.price_entry = PlaceholderEntry(form, "Price per coin", theme["placeholder"], width=15, style="TEntry"); self.price_entry.pack(side=tk.LEFT, padx=5, ipady=4)
            self.app._create_rounded_button(form, "Log Tx", self.log_transaction).pack(side=tk.LEFT, padx=10)
            notebook = ttk.Notebook(self); notebook.pack(fill=tk.BOTH, expand=True, pady=10)
            summary_frame, history_frame = ttk.Frame(notebook), ttk.Frame(notebook)
            notebook.add(summary_frame, text="Summary"); notebook.add(history_frame, text="Transaction History")
            cols_s = ("Asset", "Holdings", "Avg Buy Cost", "Value", "Unrealized P/L"); self.summary_tree = ttk.Treeview(summary_frame, columns=cols_s, show="headings"); self.summary_tree.pack(fill=tk.BOTH, expand=True)
            for col in cols_s: self.summary_tree.heading(col, text=col); self.summary_tree.column(col, anchor='center')
            cols_h = ("Date", "Symbol", "Type", "Quantity", "Price", "Total Value"); self.history_tree = ttk.Treeview(history_frame, columns=cols_h, show="headings"); self.history_tree.pack(fill=tk.BOTH, expand=True)
            for col in cols_h: self.history_tree.heading(col, text=col); self.history_tree.column(col, anchor='center')
        def log_transaction(self):
            try:
                new_tx = {"date": datetime.now().isoformat(), "symbol": self.symbol_entry.get().upper(), "type": self.type_combo.get(), "qty": float(self.qty_entry.get()), "price": float(self.price_entry.get())}
                self.app.settings.config['transactions'].append(new_tx); self.app.settings.save(); self.recalculate_portfolio()
            except ValueError: messagebox.showerror("Error", "Invalid quantity or price.")
        def recalculate_portfolio(self):
            self.holdings = defaultdict(lambda: {'qty': 0, 'cost': 0}); self.history_tree.delete(*self.history_tree.get_children())
            for tx in sorted(self.app.settings.get('transactions'), key=lambda x: x['date']):
                s, q, p = tx['symbol'], tx['qty'], tx['price']
                self.history_tree.insert("", "end", values=(datetime.fromisoformat(tx['date']).strftime("%y-%m-%d %H:%M"), s, tx['type'], f"{q:f}", f"${p:,.2f}", f"${q*p:,.2f}"))
                if tx['type'] == 'Buy': self.holdings[s]['cost'] += q*p; self.holdings[s]['qty'] += q
                else: self.holdings[s]['qty'] -= q
            self.update_portfolio_values()
        def update_portfolio_values(self):
            total_value = 0; self.summary_tree.delete(*self.summary_tree.get_children())
            for symbol, data in self.holdings.items():
                if data['qty'] <= 1e-9: continue
                price = self.app.last_prices.get(f"{symbol}USDT", 0); value = data['qty'] * price; total_value += value
                avg_cost = (data['cost'] / data['qty']) if data['qty'] > 0 else 0
                pnl = (value - (data['qty'] * avg_cost)) if avg_cost > 0 else 0
                self.summary_tree.insert("", "end", values=(symbol, f"{data['qty']:.6f}", f"${avg_cost:,.2f}", f"${value:,.2f}", f"${pnl:,.2f}"))
            self.app.total_value_var.set(f"${total_value:,.2f}")

    class ChartingTab(ttk.Frame):
        def __init__(self, parent, app):
            super().__init__(parent); self.app = app; parent.add(self, text="Live Chart")
            self.df = pd.DataFrame(); controls = ttk.Frame(self); controls.pack(fill=tk.X, pady=5)
            self.coin_var = tk.StringVar(value=self.app.selected_chart_coin)
            self.coin_combo = ttk.Combobox(controls, textvariable=self.coin_var, state="readonly", width=15); self.coin_combo.pack(side=tk.LEFT, padx=10)
            self.coin_combo.bind("<<ComboboxSelected>>", self._on_coin_select)
            self.interval_var = tk.StringVar(value="5m")
            self.interval_combo = ttk.Combobox(controls, textvariable=self.interval_var, values=["1m", "5m", "15m", "1h", "4h", "1d"], width=5); self.interval_combo.pack(side=tk.LEFT, padx=5)
            self.interval_combo.bind("<<ComboboxSelected>>", lambda e: self.plot_chart())
            self.app._create_rounded_button(controls, "Refresh", self.plot_chart).pack(side=tk.LEFT, padx=10)
            self.fig = None; self.canvas = None
            self.app.notebook.bind("<<NotebookTabChanged>>", lambda e: self.update_chart_selection() if str(self.app.notebook.select()) == str(self) else None)
        def _get_mpf_style(self):
            theme = self.app.current_theme
            return mpf.make_mpf_style(base_mpf_style='nightclouds', facecolor=theme['content_bg'], edgecolor=theme['border'], figcolor=theme['root_bg'], y_on_right=True, gridcolor=theme['border'], rc={'text.color': theme['text'], 'axes.labelcolor': theme['text'], 'xtick.color': theme['text'], 'ytick.color': theme['text']})
        def _on_coin_select(self, event):
            self.app.selected_chart_coin = self.coin_var.get(); self.plot_chart()
        def update_chart_selection(self):
            tracked = sorted([s.upper() for s in self.app.settings.get("tracked_pairs")])
            self.coin_combo['values'] = tracked
            if self.app.selected_chart_coin in tracked: self.coin_var.set(self.app.selected_chart_coin)
            elif tracked: self.coin_var.set(tracked[0]); self.app.selected_chart_coin = tracked[0]; self.plot_chart()
        def plot_chart(self):
            self.app.selected_chart_interval = self.interval_var.get()
            self.df = self.app.api.get_historical_klines(self.app.selected_chart_coin, self.app.selected_chart_interval); self.redraw_chart()
        def redraw_chart(self):
            if self.df.empty: return
            if self.canvas: self.canvas.get_tk_widget().destroy()
            fig, axlist = mpf.plot(self.df, type='candle', volume=True, style=self._get_mpf_style(), title=f"\n{self.app.selected_chart_coin} - {self.app.selected_chart_interval}", returnfig=True)
            self.fig = fig
            self.canvas = FigureCanvasTkAgg(self.fig, master=self)
            self.canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
            self.canvas.draw()
        def append_live_data(self, data):
            if data['s'] != self.app.selected_chart_coin or self.df.empty or self.app.selected_chart_interval != '1m': return
            k = data['k']
            if k['x']:
                new_candle = pd.DataFrame([{'Open': float(k['o']), 'High': float(k['h']), 'Low': float(k['l']), 'Close': float(k['c']), 'Volume': float(k['v'])}], index=[pd.to_datetime(k['t'], unit='ms')])
                self.df = pd.concat([self.df.iloc[1:], new_candle]); self.redraw_chart()

    class MarketsTab(ttk.Frame):
        def __init__(self, parent, app):
            super().__init__(parent); self.app = app; parent.add(self, text="Markets", padding=10)
            self.all_symbols = []; self._create_widgets()
            self.loading_label.pack(pady=20)
            threading.Thread(target=self._populate_symbols, daemon=True).start()
        def _create_widgets(self):
            self.loading_label = ttk.Label(self, text="Loading symbols from Binance...")
            self.main_frame = ttk.Frame(self)
            available_frame, controls_frame, tracked_frame = ttk.Frame(self.main_frame), ttk.Frame(self.main_frame), ttk.Frame(self.main_frame)
            available_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5); controls_frame.pack(side=tk.LEFT, fill=tk.Y, padx=10); tracked_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5)
            self.available_list = tk.Listbox(available_frame, bg=self.app.current_theme["content_bg"], fg=self.app.current_theme["text"], selectmode=tk.EXTENDED); self.available_list.pack(fill=tk.BOTH, expand=True)
            self.tracked_list = tk.Listbox(tracked_frame, bg=self.app.current_theme["content_bg"], fg=self.app.current_theme["text"], selectmode=tk.EXTENDED); self.tracked_list.pack(fill=tk.BOTH, expand=True)
            search_var = tk.StringVar(); search_var.trace("w", lambda n, i, m, sv=search_var: self._search(sv.get()))
            PlaceholderEntry(available_frame, "Search...", self.app.current_theme["placeholder"], textvariable=search_var).pack(fill=tk.X, pady=5, ipady=4, before=self.available_list)
            self.app._create_rounded_button(controls_frame, ">>", self._add).pack(pady=5)
            self.app._create_rounded_button(controls_frame, "<<", self._remove).pack(pady=5)
            ttk.Label(tracked_frame, text="Tracked Pairs").pack(fill=tk.X)
            self.app._create_rounded_button(self, "Apply Changes", self._apply).pack(pady=10)
        def _populate_symbols(self):
            self.all_symbols = sorted(self.app.api.get_all_usdt_symbols())
            self.loading_label.pack_forget(); self.main_frame.pack(fill=tk.BOTH, expand=True)
            tracked = set(s.lower() for s in self.app.settings.get('tracked_pairs'))
            for s in self.all_symbols:
                if s.lower() not in tracked: self.available_list.insert(tk.END, s)
            for s in sorted(list(tracked)): self.tracked_list.insert(tk.END, s.upper())
        def _search(self, term):
            self.available_list.delete(0, tk.END)
            tracked = set(s.lower() for s in self.tracked_list.get(0, tk.END))
            for s in self.all_symbols:
                if term.lower() in s.lower() and s.lower() not in tracked: self.available_list.insert(tk.END, s)
        def _add(self):
            for i in self.available_list.curselection()[::-1]: self.tracked_list.insert(tk.END, self.available_list.get(i)); self.available_list.delete(i)
        def _remove(self):
            for i in self.tracked_list.curselection()[::-1]: self.available_list.insert(tk.END, self.tracked_list.get(i)); self.tracked_list.delete(i); self._search('')
        def _apply(self):
            new_tracked = list(s.lower() for s in self.tracked_list.get(0, tk.END))
            self.app.api.update_tracked_pairs(new_tracked)
            self.app.settings.set("tracked_pairs", new_tracked); self.app.settings.save()
            messagebox.showinfo("Success", "Tracking list updated!")

class CoinSearchDialog(tk.Toplevel):
    def __init__(self, parent, app):
        super().__init__(parent); self.app = app
        self.transient(parent); self.grab_set(); self.title("Add Coin to Tracker"); self.geometry("300x400"); self.configure(bg=self.app.current_theme["root_bg"])
        self.all_symbols = self.app.markets_tab.all_symbols
        self.listbox = tk.Listbox(self, bg=self.app.current_theme["content_bg"], fg=self.app.current_theme["text"], selectmode=tk.SINGLE, highlightthickness=0)
        self.listbox.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))
        self.listbox.bind("<Double-Button-1>", self._on_select)
        search_var = tk.StringVar(); search_var.trace("w", lambda n, i, m, sv=search_var: self._on_search(sv.get()))
        PlaceholderEntry(self, "Search Coin (e.g., SOLUSDT)", self.app.current_theme["placeholder"], textvariable=search_var).pack(fill=tk.X, padx=10, pady=10, ipady=4, before=self.listbox)
        self._populate_list(self.all_symbols)
    def _populate_list(self, symbols):
        self.listbox.delete(0, tk.END)
        tracked = self.app.settings.get("tracked_pairs")
        for symbol in symbols:
            if symbol.lower() not in tracked: self.listbox.insert(tk.END, symbol)
    def _on_search(self, term):
        filtered_symbols = [s for s in self.all_symbols if term.lower() in s.lower()] if term else self.all_symbols
        self._populate_list(filtered_symbols)
    def _on_select(self, event):
        if not self.listbox.curselection(): return
        self.app.add_coin_to_tracker(self.listbox.get(self.listbox.curselection()[0])); self.destroy()

if __name__ == "__main__":
    root = tk.Tk()
    app = EliteCryptoDashboard(root)
    root.mainloop()