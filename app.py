#!/usr/bin/env python3
"""
Universal Content Scraper - Web Interface

A web interface for the universal content scraper that makes it easy for
customers to configure sources, run scraping jobs, and view results.

Version: 1.1 - Railway Production Ready
"""

from flask import Flask, render_template, request, jsonify, send_file
from flask_socketio import SocketIO, emit
import json
import os
import threading
import time
from datetime import datetime
from typing import Dict, List, Any
import uuid
from werkzeug.utils import secure_filename
import tempfile
import signal

from universal_scraper import UniversalKnowledgebaseScraper, ContentItem

# Configure app for Vercel
app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'your-secret-key-here')

# Initialize SocketIO with better production settings
try:
    socketio = SocketIO(
        app, 
        cors_allowed_origins="*",
        logger=False,
        engineio_logger=False,
        async_mode='threading'
    )
    print("✅ SocketIO initialized successfully")
except Exception as e:
    print(f"❌ SocketIO initialization error: {e}")
    # Fallback to basic Flask app
    socketio = None

# For Vercel deployment
application = app

# Helper function for safe SocketIO emit
def safe_emit(event, data):
    """Safely emit SocketIO events, with fallback if SocketIO unavailable"""
    try:
        if socketio:
            socketio.emit(event, data)
        else:
            print(f"📡 Would emit {event}: {data}")
    except Exception as e:
        print(f"❌ SocketIO emit error: {e}")

# Global variables to track jobs
active_jobs = {}
job_results = {}
UPLOAD_FOLDER = 'uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

class ScrapingJobManager:
    """Manages scraping jobs and provides real-time updates"""
    
    def __init__(self):
        self.jobs = {}
    
    def start_job(self, job_id: str, config: Dict[str, Any]) -> str:
        """Start a new scraping job"""
        
        def run_scraping_job():
            try:
                # Emit job started
                safe_emit('job_update', {
                    'job_id': job_id,
                    'status': 'running',
                    'message': 'Starting scraping job...',
                    'progress': 0
                })
                
                # Initialize scraper
                print(f"🔧 Initializing scraper for: {config['customer_name']}")
                scraper = UniversalKnowledgebaseScraper(
                    team_id=config.get('team_id', config['customer_name']),
                    customer_name=config['customer_name']
                )
                
                total_sources = len(config['sources'])
                processed_sources = 0
                
                # Emit initial progress
                safe_emit('job_update', {
                    'job_id': job_id,
                    'status': 'running',
                    'message': f'Starting to process {total_sources} sources...',
                    'progress': 0
                })
                
                for source in config['sources']:
                    url = source['url']
                    print(f"📡 Processing source: {url}")
                    # Extract config from source, excluding URL and type
                    source_config = {k: v for k, v in source.items() if k not in ['url', 'type']}
                    
                    # Emit progress update BEFORE processing
                    safe_emit('job_update', {
                        'job_id': job_id,
                        'status': 'running',
                        'message': f'Processing: {url}',
                        'progress': int((processed_sources / total_sources) * 100)
                    })
                    
                    try:
                        # Handle PDF uploads
                        if url == "PDF_PLACEHOLDER" and 'pdf_file' in source_config:
                            pdf_path = source_config['pdf_file']
                            print(f"📄 Processing PDF: {pdf_path}")
                            scraper._process_pdf_source(pdf_path, source_config)
                        else:
                            print(f"🌐 Starting web scraping: {url}")
                            
                            # Create a progress callback for granular updates
                            def progress_callback(current_item, total_items, current_url=""):
                                base_progress = int((processed_sources / total_sources) * 100)
                                item_progress = int((current_item / total_items) * (100 / total_sources)) if total_items > 0 else 0
                                total_progress = base_progress + item_progress
                                
                                safe_emit('job_update', {
                                    'job_id': job_id,
                                    'status': 'running',
                                    'message': f'Scraping article {current_item}/{total_items} from {url}',
                                    'progress': min(100, total_progress)
                                })
                            
                            # Pass the callback to the scraper
                            source_config['progress_callback'] = progress_callback
                            scraper.add_source(url, source_config)
                            print(f"✅ Completed scraping: {url}")
                    except Exception as source_error:
                        print(f"❌ Error processing {url}: {source_error}")
                        # Continue with other sources even if one fails
                        
                    processed_sources += 1
                    
                    # Emit progress update AFTER processing this source
                    safe_emit('job_update', {
                        'job_id': job_id,
                        'status': 'running',
                        'message': f'Completed: {url} ({processed_sources}/{total_sources})',
                        'progress': int((processed_sources / total_sources) * 100)
                    })
                
                # Save results with a meaningful filename
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                customer_name = config['customer_name'].replace(' ', '_').replace('-', '_')
                output_path = f"{customer_name}_scrape_{timestamp}.json"
                scraper.save(output_path)
                
                # Read the saved results to get item count
                try:
                    with open(output_path, 'r') as f:
                        results_data = json.load(f)
                    total_items = len(results_data.get('items', []))
                except:
                    total_items = 0
                
                # Store job results with config
                job_results[job_id] = {
                    'status': 'completed',
                    'output_path': output_path,
                    'total_items': total_items,
                    'completed_at': datetime.now().isoformat(),
                    'config': config
                }
                
                # Emit completion
                safe_emit('job_update', {
                    'job_id': job_id,
                    'status': 'completed',
                    'message': f'Scraping completed! Found {total_items} items.',
                    'progress': 100,
                    'total_items': total_items
                })
                
            except Exception as e:
                # Emit error
                job_results[job_id] = {
                    'status': 'error',
                    'error': str(e),
                    'completed_at': datetime.now().isoformat(),
                    'config': config
                }
                
                safe_emit('job_update', {
                    'job_id': job_id,
                    'status': 'error',
                    'message': f'Error: {str(e)}',
                    'progress': 0
                })
        
        # Start job in background thread
        thread = threading.Thread(target=run_scraping_job)
        thread.daemon = True
        thread.start()
        
        # Store job info
        self.jobs[job_id] = {
            'config': config,
            'started_at': datetime.now().isoformat(),
            'status': 'running'
        }
        
        return job_id

job_manager = ScrapingJobManager()

@app.route('/')
def index():
    """Main dashboard page"""
    return render_template('index.html')

@app.route('/api/jobs', methods=['POST'])
def create_job():
    """Create a new scraping job"""
    try:
        config = request.json
        
        # Generate unique job ID
        job_id = str(uuid.uuid4())
        
        # Start the job
        job_manager.start_job(job_id, config)
        
        return jsonify({
            'success': True,
            'job_id': job_id,
            'message': 'Scraping job started'
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 400

@app.route('/api/jobs/<job_id>/status')
def get_job_status(job_id):
    """Get status of a specific job"""
    if job_id in job_results:
        result = job_results[job_id].copy()
        result['job_id'] = job_id
        return jsonify(result)
    elif job_id in job_manager.jobs:
        job = job_manager.jobs[job_id].copy()
        job['job_id'] = job_id
        return jsonify(job)
    else:
        return jsonify({'error': 'Job not found'}), 404

@app.route('/api/jobs')
def list_jobs():
    """List all jobs"""
    all_jobs = {}
    all_jobs.update(job_manager.jobs)
    all_jobs.update(job_results)
    return jsonify(all_jobs)

@app.route('/api/jobs/<job_id>/results')
def get_job_results(job_id):
    """Get results of a completed job"""
    if job_id not in job_results:
        return jsonify({'error': 'Job not found or not completed'}), 404
    
    result = job_results[job_id]
    if result['status'] != 'completed':
        return jsonify({'error': 'Job not completed successfully'}), 400
    
    try:
        with open(result['output_path'], 'r') as f:
            data = json.load(f)
        # Convert 'items' to 'content_items' for frontend compatibility
        if 'items' in data and 'content_items' not in data:
            data['content_items'] = data['items']
        return jsonify(data)
    except Exception as e:
        return jsonify({'error': f'Failed to read results: {str(e)}'}), 500

@app.route('/api/jobs/<job_id>/download')
def download_results(job_id):
    """Download results as a file"""
    if job_id not in job_results:
        return jsonify({'error': 'Job not found or not completed'}), 404
    
    result = job_results[job_id]
    if result['status'] != 'completed':
        return jsonify({'error': 'Job not completed successfully'}), 400
    
    return send_file(result['output_path'], as_attachment=True)

@app.route('/api/upload-pdf', methods=['POST'])
def upload_pdf():
    """Handle PDF file uploads"""
    if 'file' not in request.files:
        return jsonify({'error': 'No file provided'}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400
    
    if not file.filename.lower().endswith('.pdf'):
        return jsonify({'error': 'Only PDF files are allowed'}), 400
    
    # Save file
    filename = secure_filename(file.filename)
    filepath = os.path.join(UPLOAD_FOLDER, filename)
    file.save(filepath)
    
    return jsonify({
        'success': True,
        'filepath': filepath,
        'filename': filename
    })

@app.route('/api/validate-url', methods=['POST'])
def validate_url():
    """Validate a URL before scraping"""
    try:
        url = request.json.get('url')
        if not url:
            return jsonify({'valid': False, 'error': 'No URL provided'})
        
        # Basic URL validation
        from urllib.parse import urlparse
        parsed = urlparse(url)
        
        if not parsed.scheme or not parsed.netloc:
            return jsonify({'valid': False, 'error': 'Invalid URL format'})
        
        # Try to fetch the page
        import requests
        response = requests.head(url, timeout=10)
        
        return jsonify({
            'valid': True,
            'status_code': response.status_code,
            'content_type': response.headers.get('content-type', 'unknown')
        })
        
    except Exception as e:
        return jsonify({'valid': False, 'error': str(e)})

@socketio.on('connect')
def handle_connect():
    """Handle client connection"""
    emit('connected', {'message': 'Connected to scraper'})

@socketio.on('disconnect')
def handle_disconnect():
    """Handle client disconnection"""
    print('Client disconnected')

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 10000))
    socketio.run(app, host='0.0.0.0', port=port, debug=False, allow_unsafe_werkzeug=True) 