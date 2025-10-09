#!/usr/bin/env python3
"""
Development server script with better reload handling for backend service.
This script provides more reliable auto-reload functionality than uvicorn's built-in reload.
"""

import os
import sys
import time
import subprocess
from pathlib import Path
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

class BackendReloadHandler(FileSystemEventHandler):
    """Handler for file system events that triggers server reload."""
    
    def __init__(self, restart_callback):
        self.restart_callback = restart_callback
        self.last_restart = 0
        self.restart_delay = 2  # Minimum seconds between restarts
        
    def on_modified(self, event):
        if event.is_directory:
            return
            
        # Only reload for Python files
        if not event.src_path.endswith('.py'):
            return
            
        # Avoid too frequent restarts
        current_time = time.time()
        if current_time - self.last_restart < self.restart_delay:
            return
            
        print(f"🔄 File changed: {event.src_path}")
        print("🔄 Restarting backend service...")
        self.last_restart = current_time
        self.restart_callback()

class BackendDevServer:
    """Development server with auto-reload functionality."""
    
    def __init__(self):
        self.process = None
        self.observer = None
        self.app_dir = Path(__file__).parent / "app"
        
    def start_server(self):
        """Start the uvicorn server."""
        if self.process:
            self.stop_server()
            
        cmd = [
            sys.executable, "-m", "uvicorn",
            "app.main:app",
            "--host", "0.0.0.0",
            "--port", "3001",
            "--log-level", "info"
        ]
        
        print(f"🚀 Starting backend service: {' '.join(cmd)}")
        self.process = subprocess.Popen(
            cmd,
            cwd=Path(__file__).parent,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            universal_newlines=True,
            bufsize=1
        )
        
        # Print server output in real-time
        def print_output():
            for line in iter(self.process.stdout.readline, ''):
                print(f"[BACKEND] {line.rstrip()}")
                
        import threading
        output_thread = threading.Thread(target=print_output, daemon=True)
        output_thread.start()
        
    def stop_server(self):
        """Stop the uvicorn server."""
        if self.process:
            print("🛑 Stopping backend service...")
            self.process.terminate()
            try:
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.process.kill()
            self.process = None
            
    def start_file_watcher(self):
        """Start watching for file changes."""
        event_handler = BackendReloadHandler(self.start_server)
        self.observer = Observer()
        self.observer.schedule(event_handler, str(self.app_dir), recursive=True)
        self.observer.start()
        print(f"👀 Watching for changes in: {self.app_dir}")
        
    def stop_file_watcher(self):
        """Stop the file watcher."""
        if self.observer:
            self.observer.stop()
            self.observer.join()
            
    def run(self):
        """Run the development server with auto-reload."""
        try:
            print("🔧 Starting Backend Development Server")
            print("=" * 50)
            
            # Start the server
            self.start_server()
            
            # Start file watcher
            self.start_file_watcher()
            
            print("✅ Backend development server is running!")
            print("📝 Edit files in app/ directory to trigger auto-reload")
            print("🔄 Press Ctrl+C to stop")
            
            # Keep the script running
            while True:
                time.sleep(1)
                
        except KeyboardInterrupt:
            print("\n🛑 Shutting down development server...")
            self.stop_server()
            self.stop_file_watcher()
            print("✅ Development server stopped")

if __name__ == "__main__":
    # Check if watchdog is installed
    try:
        import watchdog
    except ImportError:
        print("❌ Error: watchdog package is required for auto-reload")
        print("📦 Install it with: pip install watchdog")
        sys.exit(1)
        
    server = BackendDevServer()
    server.run()
