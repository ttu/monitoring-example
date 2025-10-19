#!/usr/bin/env python3
"""
Continuous traffic generator for monitoring-example.
Runs until manually stopped with Ctrl+C.
"""
import subprocess
import sys
import signal
import os

# Handle graceful shutdown
process = None

def signal_handler(sig, frame):
    print('\n\nStopping traffic generation...')
    if process:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
    sys.exit(0)

signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)

if __name__ == "__main__":
    print("Starting continuous traffic generation...")
    print("Press Ctrl+C to stop")
    print("Using 50 concurrent users (~40 requests/sec)\n")

    script_dir = os.path.dirname(os.path.abspath(__file__))
    generate_traffic_path = os.path.join(script_dir, "generate-traffic.py")

    try:
        # Run generate-traffic.py with a very long duration
        # Use Popen instead of run to allow streaming output
        process = subprocess.Popen(
            [sys.executable, generate_traffic_path, "--users", "50", "--duration", "999999"],
            cwd=script_dir,
            stdout=sys.stdout,
            stderr=sys.stderr
        )
        process.wait()
    except KeyboardInterrupt:
        print("\nTraffic generation stopped.")
        if process:
            process.terminate()
        sys.exit(0)
