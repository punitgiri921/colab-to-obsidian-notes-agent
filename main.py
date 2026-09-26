"""
Colab-to-Obsidian AI Knowledge Agent

Desktop Entry Point — Validates environment, checks Azure OpenAI configuration,
and launches the CustomTkinter GUI.

Usage:
    python main.py
"""

import os
import sys
from pathlib import Path

# Add project root to sys.path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from dotenv import load_dotenv


def check_environment() -> list[str]:
    """
    Validate that all required Azure OpenAI environment variables are configured.
    """
    load_dotenv(project_root / ".env")
    errors = []

    required = [
        "AZURE_OPENAI_ENDPOINT",
        "AZURE_OPENAI_KEY",
        "AZURE_OPENAI_DEPLOYMENT",
    ]

    for var in required:
        if not os.getenv(var):
            errors.append(f"Missing required environment variable: {var}")

    return errors


def main():
    """Validate environment and launch the GUI."""
    errors = check_environment()

    if errors:
        print("\n❌ Configuration Error in .env:")
        print("=" * 45)
        for err in errors:
            print(f"  • {err}")
        print("\nPlease check your .env file with:")
        print("  AZURE_OPENAI_ENDPOINT=https://...")
        print("  AZURE_OPENAI_KEY=your-api-key")
        print("  AZURE_OPENAI_DEPLOYMENT=gpt-5-mini")
        print("  AZURE_OPENAI_API_VERSION=2024-10-21")
        input("\nPress Enter to exit...")
        return

    # Launch GUI
    from gui.app import launch_app
    launch_app()


if __name__ == "__main__":
    main()
