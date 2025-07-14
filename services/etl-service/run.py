#!/usr/bin/env python3
"""
Startup script for ETL Service.
Facilitates running the application with different configurations.
"""

import os
import sys
import argparse
import uvicorn
from pathlib import Path

# Add application directory to path
app_dir = Path(__file__).parent
sys.path.insert(0, str(app_dir))

from app.core.config import get_settings


def main():
    """Main function to run the application."""
    parser = argparse.ArgumentParser(description="ETL Service - Jira Deep Data Extraction")
    
    parser.add_argument(
        "--host",
        default="0.0.0.0",
        help="Host for server bind (default: 0.0.0.0)"
    )
    
    parser.add_argument(
        "--port",
        type=int,
        default=8000,
        help="Port for server bind (default: 8000)"
    )
    
    parser.add_argument(
        "--reload",
        action="store_true",
        help="Enable auto-reload for development"
    )
    
    parser.add_argument(
        "--log-level",
        choices=["debug", "info", "warning", "error"],
        default="info",
        help="Log level (default: info)"
    )
    
    parser.add_argument(
        "--env-file",
        default=".env",
        help="Environment variables file (default: .env)"
    )
    
    args = parser.parse_args()

    # Debug information
    print(f"🔍 Debug Info:")
    print(f"   Working Directory: {Path.cwd()}")
    print(f"   Script Location: {Path(__file__).parent}")
    print(f"   Looking for .env file: {args.env_file}")
    print()

    # Check if .env file exists - search in current directory and parent directories
    env_file_path = Path(args.env_file)

    # If relative path, search in current directory and parent directories
    if not env_file_path.is_absolute():
        current_dir = Path.cwd()
        found_env = None

        # Check current directory and up to 3 parent directories
        for i in range(4):
            check_path = current_dir / args.env_file
            if check_path.exists():
                found_env = check_path
                break
            current_dir = current_dir.parent
            if current_dir == current_dir.parent:  # Reached root
                break

        if found_env:
            env_file_path = found_env
            print(f"📁 Found .env file at: {env_file_path.absolute()}")
        else:
            print(f"❌ Error: Configuration file '{args.env_file}' not found!")
            print(f"🔍 Searched in:")
            search_dir = Path.cwd()
            for i in range(4):
                print(f"   - {search_dir / args.env_file}")
                search_dir = search_dir.parent
                if search_dir == search_dir.parent:
                    break
            print("💡 Make sure the .env file exists in the ETL service directory.")
            sys.exit(1)
    elif not env_file_path.exists():
        print(f"❌ Error: Configuration file '{env_file_path}' not found!")
        print("💡 Make sure the .env file exists and the path is correct.")
        sys.exit(1)
    
    # Load settings
    try:
        settings = get_settings()
        print(f"🚀 Starting {settings.APP_NAME} v{settings.APP_VERSION}")
        print(f"📁 Working directory: {app_dir}")
        print(f"⚙️  Configuration file: {env_file_path.absolute()}")

        # Show accessible URLs (use localhost instead of 0.0.0.0)
        display_host = "localhost" if args.host == "0.0.0.0" else args.host
        print(f"🌐 Server: http://{display_host}:{args.port}")
        print(f"📚 Documentation: http://{display_host}:{args.port}/docs")
        print(f"🔍 Health Check: http://{display_host}:{args.port}/health")
        print(f"⚙️ Admin Dashboard: http://{display_host}:{args.port}/admin")
        print()
        
    except Exception as e:
        print(f"Error loading settings: {e}")
        sys.exit(1)
    
    # Run server
    try:
        uvicorn.run(
            "app.main:app",
            host=args.host,
            port=args.port,
            reload=args.reload,
            log_level=args.log_level,
            access_log=True
        )
    except KeyboardInterrupt:
        print("\n👋 Application interrupted by user")
    except Exception as e:
        print(f"Error running application: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
