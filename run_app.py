import os
import sys
import time
import socket
import subprocess
import webview

def is_server_running(host="127.0.0.1", port=8501):
    """Check if the Streamlit port is actively listening."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(1)
        return s.connect_ex((host, port)) == 0

def get_base_dir():
    if getattr(sys, "frozen", False):
        return sys._MEIPASS
    return os.path.dirname(os.path.abspath(__file__))

if __name__ == "__main__":
    base_dir = get_base_dir()
    app_path = os.path.join(base_dir, "app.py")

    # Start the Streamlit server via python subprocess
    cmd = [
        sys.executable,
        "-m", "streamlit",
        "run", app_path,
        "--server.port=8501",
        "--server.headless=true",
        "--global.developmentMode=false"
    ]

    # Hide background console window on Windows
    startupinfo = None
    if sys.platform == "win32":
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW

    server_process = subprocess.Popen(cmd, startupinfo=startupinfo)

    # Wait up to 15 seconds until Streamlit is ready to respond
    for _ in range(30):
        if is_server_running():
            break
        time.sleep(0.5)

    # Open the standalone window once the server is confirmed online
    try:
        window = webview.create_window(
            title="Chat2Invoice - Order Automation Engine",
            url="http://localhost:8501",
            width=1150,
            height=850,
            resizable=True
        )
        webview.start()
    finally:
        # Cleanly shut down Streamlit when the window is closed
        server_process.terminate()
