"""
Run this once: python keep_alive.py
Keeps Crop Bot server + public tunnel running forever.
Auto-restarts if either crashes.
"""
import subprocess, time, sys, os

SERVER_CMD = [sys.executable, "server.py"]
TUNNEL_CMD = ["ssh", "-o", "StrictHostKeyChecking=no",
               "-o", "ServerAliveInterval=30",
               "-o", "ExitOnForwardFailure=yes",
               "-R", "80:localhost:5000", "serveo.net"]

def start(cmd, name):
    print(f"Starting {name}...")
    return subprocess.Popen(cmd, cwd=os.path.dirname(os.path.abspath(__file__)))

server = start(SERVER_CMD, "Crop Bot server")
time.sleep(3)
tunnel = start(TUNNEL_CMD, "Public tunnel")

print("\n✅ Crop Bot is running! Check serveo.net output for your URL.")
print("   Press Ctrl+C to stop.\n")

try:
    while True:
        time.sleep(10)
        if server.poll() is not None:
            print("Server crashed — restarting...")
            server = start(SERVER_CMD, "server")
            time.sleep(3)
        if tunnel.poll() is not None:
            print("Tunnel dropped — reconnecting...")
            tunnel = start(TUNNEL_CMD, "tunnel")
except KeyboardInterrupt:
    print("\nStopping Crop Bot...")
    server.terminate()
    tunnel.terminate()
