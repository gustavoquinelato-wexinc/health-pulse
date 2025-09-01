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

def install_all_requirements_root():
    """Install all requirements in a single root virtual environment."""
    root_dir = Path(__file__).parent.parent
    requirements_dir = root_dir / "requirements"

    print(f"\n📦 Installing all requirements in root virtual environment...")
    print(f"   Root directory: {root_dir}")

    # Create virtual environment in root directory if it doesn't exist
    venv_dir = root_dir / "venv"
    if not venv_dir.exists():
        print(f"🔧 Creating root virtual environment...")
        if not run_command(f"{sys.executable} -m venv venv", cwd=root_dir):
            print(f"❌ Failed to create root virtual environment")
            return False
        print(f"✅ Root virtual environment created")
    else:
        print(f"📁 Using existing root virtual environment")

    # Determine pip command based on platform
    import os
    if os.name == 'nt':  # Windows
        pip_cmd = "venv\\Scripts\\pip"
        python_cmd = "venv\\Scripts\\python"
    else:  # Unix/Linux/Mac
        pip_cmd = "venv/bin/pip"
        python_cmd = "venv/bin/python"

    # Upgrade pip first
    print(f"🔄 Upgrading pip in root virtual environment...")
    if not run_command(f"{python_cmd} -m pip install --upgrade pip", cwd=root_dir):
        print(f"⚠️  Failed to upgrade pip, continuing with installation...")

    # Install all requirements files
    requirements_files = ["common.txt", "auth-service.txt", "backend-service.txt", "etl-service.txt"]
    success_count = 0

    for req_file in requirements_files:
        req_path = requirements_dir / req_file
        if req_path.exists():
            print(f"📦 Installing {req_file}...")
            command = f"{pip_cmd} install -r {req_path}"
            if run_command(command, cwd=root_dir):
                success_count += 1
            else:
                print(f"❌ Failed to install {req_file}")
        else:
            print(f"⚠️  Requirements file not found: {req_file}")

    return success_count == len([f for f in requirements_files if (requirements_dir / f).exists()])

def main():
    """Main installation function."""
    if len(sys.argv) < 2:
        print("📋 Pulse Platform Requirements Installer")
        print()
        print("Usage: python scripts/install_requirements.py <service_name|all>")
        print()
        print("Available services:")
        print("  • etl-service      - ETL Service dependencies (individual venv)")
        print("  • backend-service  - Backend Service dependencies (individual venv)")
        print("  • auth-service     - Auth Service dependencies (individual venv)")
        print("  • all              - Install all dependencies in root venv")
        print()
        print("Examples:")
        print("  python scripts/install_requirements.py etl-service")
        print("  python scripts/install_requirements.py all")
        sys.exit(1)

    target = sys.argv[1].lower()

    print("🚀 Pulse Platform Requirements Installer")
    print("=" * 50)

    if target == "all":
        success = install_all_requirements_root()
        print("=" * 50)
        if success:
            print("🎉 All requirements installed successfully in root venv!")
            print("💡 Activate with: venv\\Scripts\\activate (Windows) or source venv/bin/activate (Unix)")
        else:
            print("❌ Installation failed! Check the output above.")

    elif target in ["etl-service", "backend-service", "auth-service"]:
        success = install_service_requirements(target)
        print("=" * 50)
        if success:
            print(f"🎉 {target} requirements installed successfully!")
        else:
            print(f"❌ {target} installation failed!")

    else:
        print(f"❌ Unknown service: {target}")
        print("Available services: etl-service, backend-service, auth-service, all")
        sys.exit(1)

if __name__ == "__main__":
    main()
