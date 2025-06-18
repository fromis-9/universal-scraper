#!/usr/bin/env python3
"""
Universal Content Scraper - Easy Local Runner
Automatically handles setup and runs the app locally.
"""

import subprocess
import sys
import os
import webbrowser
import time

def print_banner():
    print("""
🚀 Universal Content Scraper - Local Setup
============================================
Setting up your scraper locally...
    """)

def check_python():
    """Check if Python version is compatible"""
    if sys.version_info < (3, 8):
        print("❌ Python 3.8+ required. Please upgrade Python.")
        print("   Download from: https://python.org/downloads/")
        sys.exit(1)
    print(f"✅ Python {sys.version.split()[0]} detected")

def install_dependencies():
    """Install required Python packages"""
    print("\n📦 Installing dependencies...")
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"])
        print("✅ Dependencies installed successfully")
    except subprocess.CalledProcessError:
        print("❌ Failed to install dependencies")
        print("💡 Try: pip install --upgrade pip")
        sys.exit(1)

def setup_browsers():
    """Setup Playwright browsers"""
    print("\n🌐 Setting up browsers...")
    try:
        subprocess.check_call([sys.executable, "-m", "playwright", "install", "chromium"])
        print("✅ Browser setup complete")
    except subprocess.CalledProcessError:
        print("⚠️  Browser setup failed, but app may still work with system Chrome")

def run_app():
    """Start the Flask application"""
    print("\n🚀 Starting the Universal Content Scraper...")
    print("📍 Server will start at: http://localhost:10000")
    print("🔄 Opening browser in 3 seconds...")
    
    # Start the app in background
    env = os.environ.copy()
    env['PYTHONUNBUFFERED'] = '1'
    
    try:
        # Wait a moment then open browser
        time.sleep(3)
        webbrowser.open('http://localhost:10000')
        
        # Run the app (this will block)
        subprocess.check_call([sys.executable, "app.py"], env=env)
        
    except KeyboardInterrupt:
        print("\n👋 Shutting down gracefully...")
    except subprocess.CalledProcessError as e:
        print(f"❌ Failed to start app: {e}")
        print("💡 Try running manually: python app.py")

def main():
    print_banner()
    
    # Check if we're in the right directory
    if not os.path.exists('app.py'):
        print("❌ app.py not found. Please run this script from the project directory.")
        sys.exit(1)
    
    check_python()
    install_dependencies()
    setup_browsers()
    run_app()

if __name__ == "__main__":
    main() 