#!/usr/bin/env python3
"""
Run the Universal Content Scraper Web Interface

This script starts the Flask web application with proper configuration
for development and production use.
"""

import os
import sys
from app import app, socketio

def main():
    """Run the web application"""
    
    # Set environment variables if not already set
    if not os.environ.get('FLASK_ENV'):
        os.environ['FLASK_ENV'] = 'development'
    
    if not os.environ.get('FLASK_DEBUG'):
        os.environ['FLASK_DEBUG'] = '1'
    
    # Determine host and port
    host = os.environ.get('HOST', '0.0.0.0')
    port = int(os.environ.get('PORT', 8080))
    debug = os.environ.get('FLASK_DEBUG', '1') == '1'
    
    print("📄  Universal Content Scraper Web Interface")
    print("=" * 50)
    print(f"🌐 Server: http://localhost:{port}")
    print(f"🔧 Debug mode: {'ON' if debug else 'OFF'}")
    print(f"📂 Upload folder: uploads/")
    print("=" * 50)
    print("Ready to scrape any website! 🚀")
    print()
    
    try:
        socketio.run(
            app, 
            debug=debug, 
            host=host, 
            port=port,
            use_reloader=debug
        )
    except KeyboardInterrupt:
        print("\n👋 Shutting down gracefully...")
        sys.exit(0)
    except Exception as e:
        print(f"❌ Failed to start server: {e}")
        sys.exit(1)

if __name__ == '__main__':
    main() 