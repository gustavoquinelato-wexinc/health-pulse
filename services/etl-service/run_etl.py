#!/usr/bin/env python3
"""
Clean ETL Service runner that suppresses CancelledError traceback.
Use this instead of `python -m uvicorn app.main:app` for cleaner shutdown.
"""

import asyncio
import os
import signal
import sys
from pathlib import Path

# Add the app directory to Python path
app_dir = Path(__file__).parent / "app"
sys.path.insert(0, str(app_dir))

def signal_handler(signum, frame):
    """Handle shutdown signals gracefully"""
    print(f"\n[INFO] Received signal {signum}, shutting down gracefully...")
    sys.exit(0)

def main():
    """Main entry point with clean shutdown handling"""
    import asyncio

    # Suppress asyncio CancelledError traceback
    def exception_handler(loop, context):
        exception = context.get('exception')
        if isinstance(exception, asyncio.CancelledError):
            # Suppress CancelledError traceback - this is normal during shutdown
            return
        # Let other exceptions through
        loop.default_exception_handler(context)

    try:
        # Import uvicorn
        import uvicorn

        # Get configuration from environment
        host = os.getenv("HOST", "0.0.0.0")
        port = int(os.getenv("PORT", "8000"))
        reload = os.getenv("ENVIRONMENT", "development") == "development"

        print(f"[INFO] Starting ETL Service on {host}:{port}")
        print(f"[INFO] Reload mode: {reload}")
        print(f"[INFO] Press Ctrl+C to stop")

        # Set up asyncio exception handler to suppress CancelledError
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.set_exception_handler(exception_handler)

        # Run the server
        uvicorn.run(
            "app.main:app",
            host=host,
            port=port,
            reload=reload,
            log_level="info",
            access_log=False,  # Reduce log noise
            loop=loop
        )

    except KeyboardInterrupt:
        print("\n[INFO] Keyboard interrupt received")
    except SystemExit:
        print("[INFO] System exit requested")
    except asyncio.CancelledError:
        print("[INFO] Service cancelled during shutdown")
    except Exception as e:
        print(f"[ERROR] Unexpected error: {e}")
    finally:
        print("[INFO] ETL Service runner shutdown complete")

if __name__ == "__main__":
    main()
