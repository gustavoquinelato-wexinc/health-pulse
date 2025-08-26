#!/usr/bin/env python3
"""
Smart requirements installer for Pulse Platform services.
Run from root directory to install dependencies in the correct service folders.

Usage:
    python scripts/install_requirements.py etl-service
    python scripts/install_requirements.py backend-service
    python scripts/install_requirements.py all
"""

import subprocess
import sys
from pathlib import Path

def run_command(command, cwd=None):
    """Run a command and return success status."""
    try:
        print(f"🔄 Running: {command}")
        print(f"   Working directory: {cwd}")

        result = subprocess.run(command, shell=True, cwd=cwd, check=True,
                              capture_output=True, text=True)
        print(f"✅ Success: {command}")
        if result.stdout.strip():
            print(f"   Output: {result.stdout.strip()}")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Failed: {command}")
        print(f"   Error: {e.stderr.strip()}")
        return False

def install_service_requirements(service_name):
    """Install requirements for a specific service in its directory."""
    root_dir = Path(__file__).parent.parent
    requirements_dir = root_dir / "requirements"
    service_dir = root_dir / "services" / service_name

    if not service_dir.exists():
        print(f"❌ Service directory not found: {service_dir}")
        return False

    requirements_file = requirements_dir / f"{service_name}.txt"
    if not requirements_file.exists():
        print(f"❌ Requirements file not found: {requirements_file}")
        return False

    print(f"\n📦 Installing requirements for {service_name}...")
    print(f"   Requirements file: {requirements_file}")
    print(f"   Service directory: {service_dir}")

    # Create virtual environment in service directory if it doesn't exist
    venv_dir = service_dir / "venv"
    if not venv_dir.exists():
        print(f"🔧 Creating virtual environment for {service_name}...")
        if not run_command(f"{sys.executable} -m venv venv", cwd=service_dir):
            print(f"❌ Failed to create virtual environment for {service_name}")
            return False
        print(f"✅ Virtual environment created for {service_name}")
    else:
        print(f"📁 Using existing virtual environment for {service_name}")

    # Determine pip command based on platform
    import os
    if os.name == 'nt':  # Windows
        pip_cmd = "venv\\Scripts\\pip"
        python_cmd = "venv\\Scripts\\python"
    else:  # Unix/Linux/Mac
        pip_cmd = "venv/bin/pip"
        python_cmd = "venv/bin/python"

    # Upgrade pip first
    print(f"🔄 Upgrading pip in {service_name} virtual environment...")
    if not run_command(f"{python_cmd} -m pip install --upgrade pip", cwd=service_dir):
        print(f"⚠️  Failed to upgrade pip, continuing with installation...")

    # Install requirements using the service's virtual environment
    print(f"📦 Installing dependencies for {service_name}...")
    command = f"{pip_cmd} install -r {requirements_file}"
    return run_command(command, cwd=service_dir)

def install_script_requirements(script_name):
    """Install requirements for a script in the scripts directory."""
    root_dir = Path(__file__).parent.parent
    requirements_dir = root_dir / "requirements"

    # Handle name mapping: requirements file uses hyphens, directory uses underscores
    script_dir_name = script_name.replace('-', '_')
    script_dir = root_dir / "scripts" / script_dir_name

    if not script_dir.exists():
        print(f"❌ Script directory not found: {script_dir}")
        return False

    requirements_file = requirements_dir / f"{script_name}.txt"
    if not requirements_file.exists():
        print(f"❌ Requirements file not found: {requirements_file}")
        return False

    print(f"\n📦 Installing requirements for {script_name}...")
    print(f"   Requirements file: {requirements_file}")
    print(f"   Script directory: {script_dir}")

    # Create virtual environment in script directory if it doesn't exist
    venv_dir = script_dir / "venv"
    if not venv_dir.exists():
        print(f"🔧 Creating virtual environment for {script_name}...")
        if not run_command(f"{sys.executable} -m venv venv", cwd=script_dir):
            print(f"❌ Failed to create virtual environment for {script_name}")
            return False
        print(f"✅ Virtual environment created for {script_name}")
    else:
        print(f"📁 Using existing virtual environment for {script_name}")

    # Determine pip command based on platform
    import os
    if os.name == 'nt':  # Windows
        pip_cmd = "venv\\Scripts\\pip"
        python_cmd = "venv\\Scripts\\python"
    else:  # Unix/Linux/Mac
        pip_cmd = "venv/bin/pip"
        python_cmd = "venv/bin/python"

    # Upgrade pip first
    print(f"🔄 Upgrading pip in {script_name} virtual environment...")
    if not run_command(f"{python_cmd} -m pip install --upgrade pip", cwd=script_dir):
        print(f"⚠️  Failed to upgrade pip, continuing with installation...")

    # Install requirements using the script's virtual environment
    print(f"📦 Installing dependencies for {script_name}...")
    command = f"{pip_cmd} install -r {requirements_file}"
    return run_command(command, cwd=script_dir)

def main():
    """Main installation function."""
    if len(sys.argv) < 2:
        print("📋 Pulse Platform Requirements Installer")
        print()
        print("Usage: python scripts/install_requirements.py <service_name|script_name|all>")
        print()
        print("Available services:")
        print("  • etl-service      - ETL Service dependencies")
        print("  • backend-service  - Backend Service dependencies")
        print("  • auth-service     - Auth Service dependencies")
        print("  • all              - Install for all services")
        print()
        print("Available scripts:")
        print("  • augment-jira-integration - Jira integration script dependencies")
        print()
        print("Examples:")
        print("  python scripts/install_requirements.py etl-service")
        print("  python scripts/install_requirements.py augment-jira-integration")
        print("  python scripts/install_requirements.py all")
        sys.exit(1)

    target = sys.argv[1].lower()

    print("🚀 Pulse Platform Requirements Installer")
    print("=" * 50)

    if target == "all":
        print("📦 Installing requirements for all services...")
        services = ["etl-service", "backend-service", "auth-service"]
        success_count = 0

        for service in services:
            if install_service_requirements(service):
                success_count += 1
            print()  # Add spacing between services

        print("=" * 50)
        print(f"📊 Installation Summary: {success_count}/{len(services)} services successful")

        if success_count == len(services):
            print("🎉 All services installed successfully!")
        else:
            print("⚠️  Some installations failed. Check the output above.")

    elif target in ["etl-service", "backend-service", "auth-service"]:
        success = install_service_requirements(target)
        print("=" * 50)
        if success:
            print(f"🎉 {target} requirements installed successfully!")
        else:
            print(f"❌ {target} installation failed!")

    elif target == "augment-jira-integration":
        success = install_script_requirements(target)
        print("=" * 50)
        if success:
            print(f"🎉 {target} requirements installed successfully!")
        else:
            print(f"❌ {target} installation failed!")

    else:
        print(f"❌ Unknown service or script: {target}")
        print("Available services: etl-service, backend-service, auth-service")
        print("Available scripts: augment-jira-integration")
        sys.exit(1)

if __name__ == "__main__":
    main()
