#!/usr/bin/env python3
"""
Smart requirements installer for Pulse Platform services.
Run from root directory to install dependencies in the correct service folders.

Usage:
    python scripts/install_requirements.py backend
    python scripts/install_requirements.py auth
    python scripts/install_requirements.py all
"""

import sys
import subprocess
from pathlib import Path

def run_command(command, cwd=None):
    """Run a shell command and return success status."""
    try:
        result = subprocess.run(
            command,
            shell=True,
            cwd=cwd,
            check=True,
            capture_output=True,
            text=True
        )
        print(result.stdout)
        return True
    except subprocess.CalledProcessError as e:
        print(f"Error: {e.stderr}")
        return False

def install_service_requirements(service_name):
    """Install requirements for a specific service in its directory."""
    root_dir = Path(__file__).parent.parent
    requirements_dir = root_dir / "requirements"
    
    # Map service names to directories
    service_map = {
        'backend': 'backend-service',
        'auth': 'auth-service'
    }
    
    service_dir_name = service_map.get(service_name)
    if not service_dir_name:
        print(f"❌ Unknown service: {service_name}")
        return False
    
    service_dir = root_dir / "services" / service_dir_name

    if not service_dir.exists():
        print(f"❌ Service directory not found: {service_dir}")
        return False

    requirements_file = requirements_dir / f"{service_name}.txt"
    if not requirements_file.exists():
        print(f"❌ Requirements file not found: {requirements_file}")
        return False

    print(f"\n📦 Installing {service_name} requirements...")
    print(f"   Service directory: {service_dir}")
    print(f"   Requirements file: {requirements_file}")

    # Create virtual environment if it doesn't exist
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

    # Install all requirements using the all.txt file
    all_file = requirements_dir / "all.txt"

    if not all_file.exists():
        print(f"❌ All requirements file not found: {all_file}")
        return False

    print(f"📦 Installing all dependencies from {all_file}...")
    command = f"{pip_cmd} install -r {all_file}"
    return run_command(command, cwd=root_dir)

def main():
    """Main installation function."""
    if len(sys.argv) < 2:
        print("📋 Pulse Platform Requirements Installer")
        print()
        print("Usage: python scripts/install_requirements.py <service|all>")
        print()
        print("Available options:")
        print("  • backend  - Backend Service (includes ETL & AI)")
        print("  • auth     - Auth Service (JWT authentication)")
        print("  • all      - Install all dependencies in root venv")
        print()
        print("Examples:")
        print("  python scripts/install_requirements.py backend")
        print("  python scripts/install_requirements.py auth")
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

    elif target in ["backend", "auth"]:
        success = install_service_requirements(target)
        print("=" * 50)
        if success:
            print(f"🎉 {target} requirements installed successfully!")
        else:
            print(f"❌ {target} installation failed!")

    else:
        print(f"❌ Unknown option: {target}")
        print("Available options: backend, auth, all")
        sys.exit(1)

if __name__ == "__main__":
    main()
