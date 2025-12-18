#!/usr/bin/env python3
"""
Complete Development Environment Setup for Pulse Platform

This script sets up everything needed for a fresh development environment:
1. Python virtual environments for all services
2. Python dependencies installation
3. Node.js dependencies for frontend
4. Environment file setup
5. Database initialization

Usage:
    python scripts/setup_development.py [--skip-venv] [--skip-frontend] [--skip-db]
"""

import os
import sys
import subprocess
import shutil
import argparse
from pathlib import Path

def run_command(cmd, cwd=None, check=True):
    """Run a command and return the result."""
    print(f"🔧 Running: {' '.join(cmd) if isinstance(cmd, list) else cmd}")
    try:
        result = subprocess.run(
            cmd, 
            cwd=cwd, 
            check=check, 
            capture_output=True, 
            text=True,
            shell=True if isinstance(cmd, str) else False
        )
        if result.stdout:
            print(f"   ✅ {result.stdout.strip()}")
        return result
    except subprocess.CalledProcessError as e:
        print(f"   ❌ Error: {e}")
        if e.stderr:
            print(f"   ❌ {e.stderr.strip()}")
        if check:
            raise
        return e

def check_prerequisites():
    """Check if required tools are installed."""
    print("🔍 Checking prerequisites...")
    
    # Check Python
    try:
        result = subprocess.run([sys.executable, "--version"], capture_output=True, text=True)
        python_version = result.stdout.strip()
        print(f"   ✅ {python_version}")
        
        # Check if Python 3.11+
        version_parts = python_version.split()[1].split('.')
        major, minor = int(version_parts[0]), int(version_parts[1])
        if major < 3 or (major == 3 and minor < 11):
            print(f"   ⚠️  Python 3.11+ recommended, found {python_version}")
    except Exception as e:
        print(f"   ❌ Python not found: {e}")
        return False
    
    # Check Node.js
    try:
        result = subprocess.run(["node", "--version"], capture_output=True, text=True)
        node_version = result.stdout.strip()
        print(f"   ✅ Node.js {node_version}")
    except FileNotFoundError:
        print("   ❌ Node.js not found. Please install Node.js 18+ from https://nodejs.org/")
        return False
    
    # Check npm
    try:
        result = subprocess.run(["npm", "--version"], capture_output=True, text=True)
        npm_version = result.stdout.strip()
        print(f"   ✅ npm {npm_version}")
    except FileNotFoundError:
        print("   ❌ npm not found")
        return False
    
    return True

def setup_python_service(service_name, root_dir, skip_venv=False):
    """Set up Python virtual environment and dependencies for a service."""
    print(f"\n📦 Setting up {service_name}...")
    
    service_dir = root_dir / "services" / service_name
    service_req_map = {"backend-service": "backend", "auth-service": "auth"}
    req_name = service_req_map.get(service_name, service_name)
    requirements_file = root_dir / "requirements" / f"{req_name}.txt"
    
    if not service_dir.exists():
        print(f"   ⚠️  Service directory not found: {service_dir}")
        return False
    
    if not requirements_file.exists():
        print(f"   ⚠️  Requirements file not found: {requirements_file}")
        return False
    
    # Create virtual environment
    venv_dir = service_dir / "venv"
    if not skip_venv:
        if venv_dir.exists():
            print(f"   🗑️  Removing existing venv...")
            shutil.rmtree(venv_dir)
        
        print(f"   🏗️  Creating virtual environment...")
        run_command([sys.executable, "-m", "venv", "venv"], cwd=service_dir)
    
    # Determine Python executable in venv
    if os.name == 'nt':  # Windows
        python_exe = venv_dir / "Scripts" / "python.exe"
        pip_exe = venv_dir / "Scripts" / "pip.exe"
    else:  # Unix/Linux/macOS
        python_exe = venv_dir / "bin" / "python"
        pip_exe = venv_dir / "bin" / "pip"
    
    # Upgrade pip
    print(f"   📦 Upgrading pip...")
    run_command([str(pip_exe), "install", "--upgrade", "pip"])
    
    # Install requirements
    print(f"   📦 Installing requirements from {requirements_file}...")
    run_command([str(pip_exe), "install", "-r", str(requirements_file)])
    
    print(f"   ✅ {service_name} setup complete!")
    return True

def setup_frontend(root_dir, skip_frontend=False):
    """Set up frontend Node.js dependencies."""
    if skip_frontend:
        print("\n🚀 Skipping frontend setup...")
        return True
    
    print(f"\n🚀 Setting up frontend...")
    
    frontend_dir = root_dir / "services" / "frontend-app"
    package_json = frontend_dir / "package.json"
    
    if not frontend_dir.exists():
        print(f"   ⚠️  Frontend directory not found: {frontend_dir}")
        return False
    
    if not package_json.exists():
        print(f"   ⚠️  package.json not found: {package_json}")
        return False
    
    # Install npm dependencies
    print(f"   📦 Installing npm dependencies...")
    run_command(["npm", "install"], cwd=frontend_dir)
    
    print(f"   ✅ Frontend setup complete!")
    return True

def setup_environment_files(root_dir):
    """Set up environment files for all services."""
    print(f"\n🔧 Setting up environment files...")

    success_count = 0
    total_services = 0

    # Setup root .env file
    root_env_example = root_dir / ".env.example"
    root_env_file = root_dir / ".env"

    if root_env_example.exists():
        total_services += 1
        if not root_env_file.exists():
            print(f"   📋 Copying root .env.example to .env...")
            shutil.copy2(root_env_example, root_env_file)
            print(f"   ✅ Root .env file created!")
            success_count += 1
        else:
            print(f"   ✅ Root .env file already exists")
            success_count += 1

    # Setup service-specific .env files
    services = ["backend-service", "auth-service", "frontend-app", "frontend-etl"]

    for service in services:
        service_dir = root_dir / "services" / service
    service_req_map = {"backend-service": "backend", "auth-service": "auth"}
    req_name = service_req_map.get(service_name, service_name)
    requirements_file = root_dir / "requirements" / f"{req_name}.txt"
        service_env_example = service_dir / ".env.example"
        service_env_file = service_dir / ".env"

        if service_env_example.exists():
            total_services += 1
            if not service_env_file.exists():
                print(f"   📋 Copying {service}/.env.example to {service}/.env...")
                shutil.copy2(service_env_example, service_env_file)
                print(f"   ✅ {service} .env file created!")
                success_count += 1
            else:
                print(f"   ✅ {service} .env file already exists")
                success_count += 1
        else:
            print(f"   ⚠️  {service}/.env.example not found")

    print(f"   📊 Environment files: {success_count}/{total_services} configured")
    print(f"   📝 Please edit .env files with your configuration")

    return success_count > 0

def print_next_steps(root_dir):
    """Print next steps for the user."""
    print(f"\n🎉 Development environment setup complete!")
    print(f"=" * 60)
    print(f"")
    print(f"📝 Next Steps:")
    print(f"")
    print(f"1. 🔧 Configure your environment:")
    print(f"   Edit .env file with your database and API credentials")
    print(f"")
    print(f"2. 🐳 Start the database:")
    print(f"   docker-compose -f docker-compose.db.yml up -d")
    print(f"")
    print(f"3. 🗄️  Run database migrations:")
    print(f"   python services/backend-service/scripts/migration_runner.py --apply-all")
    print(f"")
    print(f"4. 🚀 Start the services:")
    print(f"   # Backend Service (includes ETL)")
    print(f"   cd services/backend-service")
    print(f"   venv/Scripts/activate  # Windows")
    print(f"   source venv/bin/activate  # Unix/Linux/macOS")
    print(f"   uvicorn app.main:app --reload --port 3001")
    print(f"")
    print(f"   # Auth Service")
    print(f"   cd services/auth-service")
    print(f"   venv/Scripts/activate  # Windows")
    print(f"   source venv/bin/activate  # Unix/Linux/macOS")
    print(f"   uvicorn app.main:app --reload --port 4000")
    print(f"")
    print(f"   # Frontend App")
    print(f"   cd services/frontend-app")
    print(f"   npm run dev")
    print(f"")
    print(f"   # Frontend ETL")
    print(f"   cd services/frontend-etl")
    print(f"   npm run dev")
    print(f"")
    print(f"5. 🌐 Access the application:")
    print(f"   Frontend App: http://localhost:3000")
    print(f"   Frontend ETL: http://localhost:3333")
    print(f"   Backend API: http://localhost:3001/docs")
    print(f"   Auth API: http://localhost:4000/docs")
    print(f"")
    print(f"🎯 Happy coding!")

def main():
    """Main setup function."""
    parser = argparse.ArgumentParser(description="Set up Pulse Platform development environment")
    parser.add_argument("--skip-venv", action="store_true", help="Skip virtual environment creation")
    parser.add_argument("--skip-frontend", action="store_true", help="Skip frontend setup")
    parser.add_argument("--skip-db", action="store_true", help="Skip database setup")
    
    args = parser.parse_args()
    
    print("🚀 Pulse Platform Development Environment Setup")
    print("=" * 60)
    
    # Get root directory
    root_dir = Path(__file__).parent.parent
    print(f"📁 Root directory: {root_dir}")
    
    # Check prerequisites
    if not check_prerequisites():
        print("\n❌ Prerequisites check failed. Please install missing tools.")
        sys.exit(1)
    
    # Setup Python services
    python_services = ["backend-service", "auth-service"]  # Maps to backend.txt and auth.txt
    success_count = 0

    for service in python_services:
        if setup_python_service(service, root_dir, args.skip_venv):
            success_count += 1
    
    # Setup frontend
    if setup_frontend(root_dir, args.skip_frontend):
        success_count += 1
    
    # Setup environment files
    setup_environment_files(root_dir)
    
    # Print results
    total_services = len(python_services) + (0 if args.skip_frontend else 1)
    print(f"\n📊 Setup Summary: {success_count}/{total_services} services successful")
    
    if success_count == total_services:
        print_next_steps(root_dir)
    else:
        print("⚠️  Some setups failed. Check the output above.")
        sys.exit(1)

if __name__ == "__main__":
    main()

