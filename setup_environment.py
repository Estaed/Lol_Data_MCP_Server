#!/usr/bin/env python3
"""
Setup script for LoL Data MCP Server development environment.
This script helps create and configure the virtual environment.
"""

import subprocess
import sys
import os
from pathlib import Path


def run_command(command, description):
    """Run a command and handle errors."""
    print(f"\n🔄 {description}")
    try:
        result = subprocess.run(
            command, shell=True, check=True, capture_output=True, text=True
        )
        print(f"✅ {description} - Success")
        if result.stdout:
            print(result.stdout)
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ {description} - Failed")
        print(f"Error: {e.stderr}")
        return False


def main():
    """Main setup function."""
    print("🚀 Setting up LoL Data MCP Server development environment...")

    # Get project root directory
    project_root = Path(__file__).parent
    venv_path = project_root / "venv"

    # Create virtual environment if it doesn't exist
    if not venv_path.exists():
        print(f"\n📁 Creating virtual environment at {venv_path}")
        if not run_command(
            f"python -m venv {venv_path}", "Creating virtual environment"
        ):
            sys.exit(1)
    else:
        print(f"\n✅ Virtual environment already exists at {venv_path}")

    # Determine activation script based on OS
    if os.name == "nt":  # Windows
        activate_script = venv_path / "Scripts" / "activate.bat"
        pip_executable = venv_path / "Scripts" / "pip.exe"
    else:  # Unix/Linux/macOS
        activate_script = venv_path / "bin" / "activate"
        pip_executable = venv_path / "bin" / "pip"

    # Install dependencies
    requirements_file = project_root / "requirements.txt"
    if requirements_file.exists():
        print(f"\n📦 Installing dependencies from {requirements_file}")
        if not run_command(
            f'"{pip_executable}" install -r "{requirements_file}"',
            "Installing requirements",
        ):
            sys.exit(1)
    else:
        print("⚠️  No requirements.txt found. Skipping dependency installation.")

    # Install development dependencies
    dev_packages = ["pytest", "pytest-asyncio", "black", "isort", "mypy", "flake8"]

    print("\n🛠️  Installing development dependencies...")
    for package in dev_packages:
        run_command(f'"{pip_executable}" install {package}', f"Installing {package}")

    print("\n🎉 Setup complete!")
    print("\n📋 Next steps:")
    print("1. Activate the virtual environment:")
    if os.name == "nt":
        print(f"   {activate_script}")
    else:
        print(f"   source {activate_script}")
    print("2. Start developing!")
    print("3. To run the MCP server: python -m src.mcp_server")


if __name__ == "__main__":
    main()
