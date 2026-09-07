# -*- coding: utf-8 -*-
"""
One-click launcher - manages all backend services in a single window
Usage: double-click 一键启动.bat (or run: python launcher.py)
NOTE: Closing this window stops ALL services. Keep it open during demo.
"""
import os
import sys
import time
import socket
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CREATE_NO_WINDOW = 0x08000000 if os.name == 'nt' else 0

# Force ASCII-safe output (works with any console codepage)
if os.name == 'nt':
    try:
        sys.stdout.reconfigure(encoding='ascii', errors='replace')
        sys.stderr.reconfigure(encoding='ascii', errors='replace')
    except Exception:
        pass

SERVICES = [
    {"name": "Data API (8501)",        "port": 8501, "cmd": [sys.executable, "data_api.py", "--port", "8501"]},
    {"name": "BMS Platform (8502)",    "port": 8502, "cmd": [sys.executable, "-m", "streamlit", "run", "app.py",
                                                            "--server.port", "8502", "--server.headless", "true"]},
    {"name": "Vehicle Dash (8503)",    "port": 8503, "cmd": [sys.executable, "-m", "streamlit", "run", "vehicle_dashboard.py",
                                                            "--server.port", "8503", "--server.headless", "true"]},
    {"name": "Trade Platform (8504)",  "port": 8504, "cmd": [sys.executable, "-m", "streamlit", "run", "trade_platform.py",
                                                            "--server.port", "8504", "--server.headless", "true"]},
]

def port_open(port, timeout=0.5):
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=timeout):
            return True
    except OSError:
        return False

BROWSER_PATHS = [
    # Edge (default priority)
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    # Chrome
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    # Firefox
    r"C:\Program Files\Mozilla Firefox\firefox.exe",
    r"C:\Program Files (x86)\Mozilla Firefox\firefox.exe",
]

def find_browser():
    """Detect installed browser: Edge > Chrome > Firefox > system default"""
    for path in BROWSER_PATHS:
        if os.path.exists(path):
            return path
    return None  # fallback: webbrowser module

def open_browsers():
    """Open BMS + Vehicle + Trade platforms in detected browser"""
    urls = ["http://localhost:8502",
            "http://localhost:8503?car=CATL-QJ-100",
            "http://localhost:8504"]
    browser = find_browser()
    if browser:
        print(f"  [BROWSER] Detected: {os.path.basename(os.path.dirname(os.path.dirname(browser)))}")
        try:
            subprocess.Popen([browser] + urls,
                             creationflags=CREATE_NO_WINDOW)
            print("  [BROWSER] Opened BMS + Vehicle + Trade platforms")
            return
        except Exception as e:
            print(f"  [BROWSER] Launch failed ({e}), using system default")
    # Fallback: system default browser
    try:
        import webbrowser
        for u in urls:
            webbrowser.open(u)
        print("  [BROWSER] Opened with system default browser")
    except Exception as e:
        print(f"  [BROWSER] Cannot open browser: {e}")

def main():
    os.chdir(ROOT)
    procs = []
    print("=" * 58)
    print("  AI Battery Lifecycle System - Launcher")
    print("=" * 58)
    print()
    print("  >>> Starting 4 background services <<<")
    print("  >>> DO NOT CLOSE THIS WINDOW <<<")
    print("  >>> Closing = stopping ALL services <<<")
    print()

    for svc in SERVICES:
        if port_open(svc["port"]):
            print(f"  [ALREADY RUNNING] {svc['name']:<20} http://localhost:{svc['port']}")
            continue
        try:
            log = open(ROOT / f"log_{svc['port']}.txt", "a", encoding="utf-8")
            p = subprocess.Popen(svc["cmd"], cwd=ROOT, stdout=log, stderr=log,
                                 creationflags=CREATE_NO_WINDOW, stdin=subprocess.DEVNULL)
            procs.append(p)
            print(f"  [STARTING] {svc['name']:<20} PID={p.pid}  log: log_{svc['port']}.txt")
        except Exception as e:
            print(f"  [FAILED]   {svc['name']}: {e}")

    # Wait for ports
    print()
    for _ in range(30):
        ready = [s for s in SERVICES if port_open(s["port"])]
        if len(ready) == len(SERVICES):
            break
        time.sleep(1)

    print()
    print("=" * 58)
    print("  ALL SERVICES STARTED!")
    print()
    print("    BMS Platform       http://localhost:8502")
    print("    Vehicle Dashboard  http://localhost:8503")
    print()
    print("    Trade Platform - LOCAL : http://localhost:8504")
    print("    Trade Platform - PUBLIC: https://battery-trade.streamlit.app")
    print()
    print("  [IMPORTANT] This window controls ALL services:")
    print("    Closing it stops everything!")
    print("    Keep it open during your demo.")
    print("=" * 58)
    print()

    # Auto-open browser (detect installed browser: Edge first)
    open_browsers()
    print()
    print("Press Ctrl+C to stop all services safely...")

    try:
        while True:
            time.sleep(2)
            for p in list(procs):
                if p.poll() is not None:
                    print(f"  [WARNING] A service exited (PID={p.pid}). Restart the launcher.")
                    procs.remove(p)
    except KeyboardInterrupt:
        print()
        print("  Stopping all services...")
        for p in procs:
            try:
                p.terminate()
            except Exception:
                pass
        time.sleep(1)
        print("  Stopped. Goodbye!")

if __name__ == "__main__":
    main()
