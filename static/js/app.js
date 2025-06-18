// Universal Content Scraper - Frontend JavaScript

class ScraperApp {
    constructor() {
        this.socket = io();
        this.currentJobId = null;
        this.sources = [];
        this.init();
    }

    init() {
        this.setupSocketHandlers();
        this.setupEventHandlers();
        this.loadJobHistory();
        
        // Add initial source
        this.addSource();
    }

    setupSocketHandlers() {
        this.socket.on('connect', () => {
            this.updateConnectionStatus('connected', 'Connected');
            console.log('✅ WebSocket connected to server');
        });

        this.socket.on('disconnect', () => {
            this.updateConnectionStatus('disconnected', 'Disconnected');
            console.log('❌ WebSocket disconnected from server');
        });

        this.socket.on('job_update', (data) => {
            console.log('📡 WebSocket job update received:', data);
            this.handleJobUpdate(data);
        });
        
        this.socket.on('connected', (data) => {
            console.log('🔗 Server connection confirmed:', data);
        });
    }

    setupEventHandlers() {
        // Add source button
        document.getElementById('addSource').addEventListener('click', () => {
            this.addSource();
        });

        // Form submission
        document.getElementById('scrapingForm').addEventListener('submit', (e) => {
            e.preventDefault();
            this.startScrapingJob();
        });

        // PDF modal handlers
        document.getElementById('cancelPdfUpload').addEventListener('click', () => {
            this.closePdfModal();
        });

        document.getElementById('uploadPdf').addEventListener('click', () => {
            this.uploadPdf();
        });
    }

    updateConnectionStatus(status, message) {
        const statusElement = document.getElementById('connectionStatus');
        const dot = statusElement.querySelector('div');
        const text = statusElement.querySelector('span');
        
        text.textContent = message;
        
        if (status === 'connected') {
            dot.className = 'w-3 h-3 bg-green-400 rounded-full mr-2';
        } else {
            dot.className = 'w-3 h-3 bg-red-400 rounded-full mr-2';
        }
    }

    addSource() {
        const sourceId = `source_${Date.now()}`;
        const sourceHtml = `
            <div id="${sourceId}" class="card-minimal rounded-xl p-4 shadow-lg">
                <div class="flex justify-between items-start mb-3">
                    <h4 class="text-sm font-medium text-gray-300">Source Configuration</h4>
                    <button onclick="scraperApp.removeSource('${sourceId}')" 
                            class="text-gray-500 hover:text-gray-300 transition-colors">
                        <i class="fas fa-times"></i>
                    </button>
                </div>
                
                <div class="space-y-4">
                    <!-- Source Type Selection -->
                    <div class="flex space-x-2">
                        <button type="button" onclick="scraperApp.toggleSourceType('${sourceId}', 'website')" 
                                data-type="website"
                                class="source-type-btn btn-sleek flex-1 px-3 py-2 text-sm rounded-lg transition-all duration-300 bg-gray-700 text-gray-200 active">
                            <i class="fas fa-globe mr-2"></i>Website
                        </button>
                        <button type="button" onclick="scraperApp.toggleSourceType('${sourceId}', 'pdf')" 
                                data-type="pdf"
                                class="source-type-btn btn-sleek flex-1 px-3 py-2 text-sm rounded-lg transition-all duration-300">
                            <i class="fas fa-file-pdf mr-2"></i>PDF
                        </button>
                    </div>
                    
                    <!-- Website Source (default) -->
                    <div class="source-config website-config">
                        <input type="url" placeholder="Enter website URL (e.g., https://example.com/blog)" 
                               class="source-url input-sleek w-full px-3 py-2 text-sm rounded-lg text-gray-100 placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-gray-600/50">
                        <div class="mt-2 flex items-center">
                            <span class="url-status text-xs text-gray-500"></span>
                            <button type="button" onclick="scraperApp.validateUrl('${sourceId}', this.parentElement.previousElementSibling.value)" 
                                    class="ml-2 px-2 py-1 text-xs btn-sleek rounded transition-all hidden">
                                Validate
                            </button>
                        </div>
                    </div>
                    
                    <!-- PDF Source (hidden by default) -->
                    <div class="source-config pdf-config hidden">
                        <div class="text-center">
                            <button type="button" onclick="scraperApp.openPdfModal('${sourceId}')" 
                                    class="btn-primary px-4 py-2 text-sm rounded-lg hover:shadow-lg transition-all duration-300">
                                <i class="fas fa-upload mr-2"></i>Choose PDF File
                            </button>
                            <div class="pdf-status text-xs text-gray-500 mt-2"></div>
                            <input type="hidden" class="pdf-path" value="">
                        </div>
                    </div>
                    
                    <!-- Advanced Options -->
                    <details class="mt-3">
                        <summary class="text-xs text-gray-400 cursor-pointer hover:text-gray-300 transition-colors">Advanced Options</summary>
                        <div class="mt-3 space-y-2">
                            <!-- Website-specific options -->
                            <div class="website-advanced-options">
                                <div class="grid grid-cols-2 gap-2">
                                    <div>
                                        <label class="text-xs text-gray-400">Max Articles</label>
                                        <input type="number" value="50" min="1" max="200" 
                                               class="source-max-articles w-full px-2 py-1 text-xs input-sleek rounded focus:outline-none focus:ring-1 focus:ring-gray-600/50">
                                    </div>
                                    <div>
                                        <label class="text-xs text-gray-400">Delay (seconds)</label>
                                        <input type="number" value="1" min="0" max="10" step="0.5" 
                                               class="source-delay w-full px-2 py-1 text-xs input-sleek rounded focus:outline-none focus:ring-1 focus:ring-gray-600/50">
                                    </div>
                                </div>
                            </div>
                            <!-- PDF-specific options -->
                            <div class="pdf-advanced-options hidden">
                                <div class="grid grid-cols-1 gap-2">
                                    <div>
                                        <label class="text-xs text-gray-400">Description</label>
                                        <input type="text" placeholder="Optional description for this PDF" 
                                               class="source-description w-full px-2 py-1 text-xs input-sleek rounded focus:outline-none focus:ring-1 focus:ring-gray-600/50">
                                    </div>
                                </div>
                            </div>
                        </div>
                    </details>
                </div>
            </div>
        `;
        
        document.getElementById('sourcesList').insertAdjacentHTML('beforeend', sourceHtml);
    }

    removeSource(sourceId) {
        const sourceElement = document.getElementById(sourceId);
        if (sourceElement) {
            sourceElement.remove();
        }
    }

    toggleSourceType(sourceId, type) {
        const sourceDiv = document.getElementById(sourceId);
        const websiteConfig = sourceDiv.querySelector('.website-config');
        const pdfConfig = sourceDiv.querySelector('.pdf-config');
        const buttons = sourceDiv.querySelectorAll('.source-type-btn');
        

        
        // Update button states
        buttons.forEach(btn => {
            btn.dataset.type = btn.dataset.type || (btn.textContent.includes('Website') ? 'website' : 'pdf');
            if (btn.dataset.type === type) {
                btn.classList.add('active', 'bg-blue-600', 'text-white');
                btn.classList.remove('text-gray-300');

            } else {
                btn.classList.remove('active', 'bg-blue-600', 'text-white');
                btn.classList.add('text-gray-300');
            }
        });
        
        // Show/hide appropriate configuration
        const websiteAdvanced = sourceDiv.querySelector('.website-advanced-options');
        const pdfAdvanced = sourceDiv.querySelector('.pdf-advanced-options');
        
        if (type === 'pdf') {
            websiteConfig.classList.add('hidden');
            pdfConfig.classList.remove('hidden');
            websiteAdvanced.classList.add('hidden');
            pdfAdvanced.classList.remove('hidden');
        } else {
            websiteConfig.classList.remove('hidden');
            pdfConfig.classList.add('hidden');
            websiteAdvanced.classList.remove('hidden');
            pdfAdvanced.classList.add('hidden');
        }
    }

    async validateUrl(sourceId, url) {
        if (!url) return;
        
        const sourceElement = document.getElementById(sourceId);
        const statusElement = sourceElement.querySelector('.url-status');
        
        statusElement.className = 'url-status mt-2 text-sm text-blue-400';
        statusElement.innerHTML = '<i class="fas fa-spinner fa-spin mr-2"></i>Validating...';
        statusElement.classList.remove('hidden');
        
        try {
            const response = await fetch('/api/validate-url', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ url: url })
            });
            
            const result = await response.json();
            
            if (result.valid) {
                statusElement.className = 'url-status mt-2 text-sm text-green-400';
                statusElement.innerHTML = `<i class="fas fa-check-circle mr-2"></i>Valid (${result.status_code})`;
            } else {
                statusElement.className = 'url-status mt-2 text-sm text-red-400';
                statusElement.innerHTML = `<i class="fas fa-exclamation-circle mr-2"></i>${result.error}`;
            }
        } catch (error) {
            statusElement.className = 'url-status mt-2 text-sm text-red-400';
            statusElement.innerHTML = `<i class="fas fa-exclamation-circle mr-2"></i>Validation failed`;
        }
    }

    openPdfModal(sourceId) {
        this.currentPdfSourceId = sourceId;
        const modal = document.getElementById('pdfModal');
        modal.classList.remove('hidden');
        modal.classList.add('flex');
    }

    closePdfModal() {
        const modal = document.getElementById('pdfModal');
        modal.classList.add('hidden');
        modal.classList.remove('flex');
        document.getElementById('pdfFileInput').value = '';
    }

    async uploadPdf() {
        const fileInput = document.getElementById('pdfFileInput');
        const file = fileInput.files[0];
        
        if (!file) {
            alert('Please select a PDF file');
            return;
        }
        
        const formData = new FormData();
        formData.append('file', file);
        
        try {
            const response = await fetch('/api/upload-pdf', {
                method: 'POST',
                body: formData
            });
            
            const result = await response.json();
            
            if (result.success) {
                // Update the source element
                const sourceElement = document.getElementById(this.currentPdfSourceId);
                const pdfStatus = sourceElement.querySelector('.pdf-status');
                const pdfPath = sourceElement.querySelector('.pdf-path');
                
                pdfStatus.textContent = `Uploaded: ${result.filename}`;
                pdfStatus.className = 'pdf-status mt-1 text-xs text-green-400';
                pdfPath.value = result.filepath;
                
                this.closePdfModal();
            } else {
                alert(`Upload failed: ${result.error}`);
            }
        } catch (error) {
            alert(`Upload failed: ${error.message}`);
        }
    }

    gatherConfiguration() {
        const customerName = document.getElementById('customerName').value;
        
        if (!customerName) {
            throw new Error('Please fill in customer name');
        }
        
        // Collect source configurations
        const sources = [];
        
        // Get all source elements from the DOM
        const sourceElements = document.querySelectorAll('#sourcesList > div');
        
        for (const sourceElement of sourceElements) {
            // Determine source type by checking which button is active
            const activeButton = sourceElement.querySelector('.source-type-btn.active');
            if (!activeButton) continue;
            
            const sourceType = activeButton.dataset.type;
            const maxArticlesInput = sourceElement.querySelector('.source-max-articles');
            const descriptionInput = sourceElement.querySelector('.source-description');
            const maxArticles = maxArticlesInput ? parseInt(maxArticlesInput.value) : 100;
            const description = descriptionInput ? descriptionInput.value : '';
            
            if (sourceType === 'website') {
                const urlInput = sourceElement.querySelector('.source-url');
                const url = urlInput ? urlInput.value : '';
                if (url) {
                    sources.push({
                        url: url,
                        type: 'website',
                        max_articles: maxArticles,
                        description: description
                    });
                }
            } else if (sourceType === 'pdf') {
                const pdfPathInput = sourceElement.querySelector('.pdf-path');
                const pdfPath = pdfPathInput ? pdfPathInput.value : '';

                if (pdfPath) {
                    sources.push({
                        url: "PDF_PLACEHOLDER",
                        pdf_file: pdfPath,
                        title: description || "PDF Document",
                        author: customerName,
                        description: description
                    });
                }
            }
        }
        

        
        return {
            customer_name: customerName,
            sources: sources
        };
    }

    async startScrapingJob() {
        try {
            // Gather configuration from form
            const config = this.gatherConfiguration();
            
            if (!config.sources || config.sources.length === 0) {
                alert('Please add at least one source to scrape.');
                return;
            }
            
            console.log('🚀 Starting scraping job with config:', config);
            
            // Show loading state
            const resultsSection = document.getElementById('resultsSection');
            const submitButton = document.getElementById('startScraping');
            
            // No need to show status section - it's always visible
            resultsSection.classList.add('hidden');
            submitButton.disabled = true;
            this.showJobStatus();
            
            // Create the job
            const response = await fetch('/api/jobs', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(config)
            });
            
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }
            
            const result = await response.json();
            console.log('✅ Job created:', result);
            
            if (result.success) {
                this.currentJobId = result.job_id;
                console.log('📋 Current job ID set to:', this.currentJobId);
                
                // Show job started status
                this.updateJobStatus({
                    job_id: this.currentJobId,
                    status: 'starting',
                    message: 'Starting scraping job...',
                    progress: 0
                });
                
                // Start polling for status as a fallback
                this.startJobStatusPolling();
            } else {
                throw new Error(result.error || 'Failed to create job');
            }
            
        } catch (error) {
            console.error('❌ Failed to start scraping job:', error);
            alert(`Failed to start scraping: ${error.message}`);
            document.getElementById('startScraping').disabled = false;
        }
    }

    startJobStatusPolling() {
        if (!this.currentJobId) return;
        
        console.log('🔄 Starting status polling for job:', this.currentJobId);
        
        const pollInterval = setInterval(async () => {
            try {
                console.log('📊 Polling job status...');
                const response = await fetch(`/api/jobs/${this.currentJobId}/status`);
                if (!response.ok) {
                    throw new Error(`HTTP ${response.status}`);
                }
                
                const status = await response.json();
                console.log('📋 Polled status:', status);
                
                // Update UI with the status
                this.handleJobUpdate(status);
                
                // Stop polling if job is complete or errored
                if (status.status === 'completed' || status.status === 'error') {
                    console.log('🏁 Job finished, stopping polling');
                    clearInterval(pollInterval);
                }
                
            } catch (error) {
                console.warn('⚠️ Error polling job status:', error);
                // Continue polling on error - might be temporary
            }
        }, 2000); // Poll every 2 seconds
        
        // Store the interval so we can clear it later
        this.currentPollInterval = pollInterval;
        
        // Stop polling after 5 minutes to prevent infinite polling
        setTimeout(() => {
            console.log('⏰ Stopping polling after timeout');
            clearInterval(pollInterval);
        }, 5 * 60 * 1000);
    }

    handleJobUpdate(data) {
        console.log('🔄 Processing job update:', data);
        
        if (data.job_id === this.currentJobId) {
            console.log('📊 Updating status for current job:', this.currentJobId);
            this.updateJobStatus(data);
        } else {
            console.log('⚠️ Job update for different job:', data.job_id, 'vs current:', this.currentJobId);
        }
        
        if (data.status === 'completed') {
            console.log('🎉 Job completed! Loading results for:', data.job_id);
            this.loadJobResults(data.job_id);
            document.getElementById('startScraping').disabled = false;
            this.loadJobHistory(); // Refresh job history
        } else if (data.status === 'error') {
            console.log('❌ Job failed:', data.job_id);
            document.getElementById('startScraping').disabled = false;
            this.loadJobHistory(); // Refresh job history
        }
    }

    updateJobStatus(data) {
        console.log('📊 updateJobStatus called with:', data);
        const statusElement = document.getElementById('jobStatus');
        
        let statusClass = 'text-gray-400';
        let icon = 'fa-spinner fa-spin';
        let message = data.message || '';
        let progress = data.progress || 0;
        
        console.log('📈 Initial progress value:', progress);
        
        // Generate appropriate messages based on status
        if (data.status === 'completed') {
            statusClass = 'text-gray-300';
            icon = 'fa-check-circle';
            progress = 100;
            if (!message) {
                message = `Scraping completed! Found ${data.total_items || 0} items.`;
            }
        } else if (data.status === 'error') {
            statusClass = 'text-red-400';
            icon = 'fa-exclamation-circle';
            progress = 0;
            if (!message) {
                message = data.error || 'An error occurred during scraping';
            }
        } else if (data.status === 'running') {
            statusClass = 'text-gray-300';
            icon = 'fa-spinner fa-spin';
            // Use actual progress from backend - this is critical!
            if (data.progress !== undefined) {
                progress = Math.max(0, Math.min(100, data.progress));
            }
            if (!message) {
                message = 'Processing sources...';
            }
        } else {
            if (!message) {
                message = 'Initializing...';
            }
            // Keep progress at 0 for initialization unless explicitly set
            if (data.progress !== undefined) {
                progress = Math.max(0, Math.min(100, data.progress));
            }
        }
        
        console.log('📊 Final progress before rendering:', progress);
        
        statusElement.innerHTML = `
            <div class="space-y-4">
                <div class="text-center">
                    <div class="w-12 h-12 rounded-xl bg-gradient-to-br from-gray-800 to-gray-900 flex items-center justify-center mx-auto mb-4">
                        <i class="fas ${icon} text-xl ${statusClass}"></i>
                    </div>
                    <h3 class="text-sm font-medium text-gray-200">${this.getStatusText(data.status)}</h3>
                    <p class="text-xs text-gray-400 mt-2 leading-relaxed">${message}</p>
                </div>
                
                <div class="w-full bg-gray-800/50 rounded-full h-2 overflow-hidden">
                    <div class="progress-bar h-full rounded-full transition-all duration-500 ease-out" 
                         style="width: ${progress}%"></div>
                </div>
                <div class="text-center text-xs text-gray-500">${Math.round(progress)}%</div>
            </div>
        `;
    }

    getStatusText(status) {
        switch (status) {
            case 'running': return 'Scraping in Progress';
            case 'completed': return 'Scraping Completed';
            case 'error': return 'Scraping Failed';
            default: return 'Unknown Status';
        }
    }

    showJobStatus() {
        const statusElement = document.getElementById('jobStatus');
        statusElement.innerHTML = `
            <div class="text-center">
                <i class="fas fa-spinner fa-spin text-4xl text-blue-400 mb-4"></i>
                <h3 class="text-lg font-semibold text-white">Starting Job</h3>
                <p class="text-sm text-gray-300 mt-2">Initializing scraper...</p>
            </div>
        `;
    }

    async loadJobResults(jobId) {
        try {
            console.log('📄 Fetching results for job:', jobId);
            const response = await fetch(`/api/jobs/${jobId}/results`);
            
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }
            
            const results = await response.json();
            console.log('📊 Results loaded:', results);
            
            this.displayResults(results);
        } catch (error) {
            console.error('❌ Failed to load results:', error);
        }
    }

    displayResults(results) {
        console.log('🎨 Displaying results:', results);
        const resultsSection = document.getElementById('resultsSection');
        const resultsContent = document.getElementById('resultsContent');
        
        // Store results for JSON view
        this.currentResults = results;
        
        if (!results.content_items || results.content_items.length === 0) {
            console.log('⚠️ No content items found in results');
            resultsContent.innerHTML = '<p class="text-gray-400">No content items found.</p>';
        } else {
            const items = results.content_items;
            const itemsByType = {};
            
            // Group by content type
            items.forEach(item => {
                const type = item.content_type || 'unknown';
                if (!itemsByType[type]) {
                    itemsByType[type] = [];
                }
                itemsByType[type].push(item);
            });
            
            let html = `
                <div class="mb-6">
                    <div class="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
                        <div class="card-minimal p-4 rounded-xl text-center">
                            <div class="text-2xl font-light text-gray-200">${items.length}</div>
                            <div class="text-xs text-gray-500 mt-1">Total Items</div>
                        </div>
                        <div class="card-minimal p-4 rounded-xl text-center">
                            <div class="text-2xl font-light text-gray-200">${Object.keys(itemsByType).length}</div>
                            <div class="text-xs text-gray-500 mt-1">Content Types</div>
                        </div>
                        <div class="card-minimal p-4 rounded-xl text-center">
                            <div class="text-2xl font-light text-gray-200">${Math.round(items.reduce((acc, item) => acc + item.content.length, 0) / items.length)}</div>
                            <div class="text-xs text-gray-500 mt-1">Avg. Length</div>
                        </div>
                    </div>
                    
                    <div class="flex justify-end mb-4 space-x-3">
                        <button onclick="scraperApp.showJsonView()" 
                                class="btn-sleek text-gray-300 px-4 py-2 text-sm rounded-lg hover:shadow-lg transition-all duration-300">
                            <i class="fas fa-code mr-2"></i>Show JSON
                        </button>
                        <button onclick="scraperApp.downloadResults('${this.currentJobId}')" 
                                class="btn-primary text-gray-100 px-4 py-2 text-sm rounded-lg hover:shadow-lg transition-all duration-300">
                            <i class="fas fa-download mr-2"></i>Download
                        </button>
                    </div>
                </div>
                
                <div class="space-y-6">
            `;
            
            for (const [type, typeItems] of Object.entries(itemsByType)) {
                html += `
                    <div>
                        <h3 class="text-sm font-medium text-gray-300 mb-4 capitalize">${type} (${typeItems.length} items)</h3>
                        <div class="grid gap-3" id="itemsGrid_${type}">
                `;
                
                // Always show first 5 items
                typeItems.slice(0, 5).forEach((item, index) => {
                    const preview = item.content.substring(0, 150) + (item.content.length > 150 ? '...' : '');
                    const itemId = `${type}_${index}`;
                    const sourceUrl = item.source_url || '';
                    html += `
                        <div class="card-minimal rounded-xl p-4 hover:shadow-xl transition-all duration-300">
                            <div class="flex justify-between items-start mb-3">
                                <h4 class="text-sm font-medium text-gray-200 leading-relaxed">${item.title}</h4>
                                <button onclick="scraperApp.viewMarkdown('${itemId}', ${JSON.stringify(item.content).replace(/"/g, '&quot;')}, '${sourceUrl}')" 
                                        class="btn-primary text-gray-100 px-3 py-1.5 text-xs rounded-lg hover:shadow-lg transition-all duration-300 ml-3 flex-shrink-0">
                                    <i class="fas fa-eye mr-1"></i>View
                                </button>
                            </div>
                            <p class="text-xs text-gray-400 mb-3 leading-relaxed">${preview}</p>
                            <div class="flex justify-between items-center text-xs text-gray-500">
                                <span class="font-mono">${item.content.length} chars</span>
                                ${item.source_url ? `<a href="${item.source_url}" target="_blank" class="text-gray-400 hover:text-gray-300 transition-colors">Source</a>` : ''}
                            </div>
                        </div>
                    `;
                });
                
                // Add hidden items (initially collapsed)
                if (typeItems.length > 5) {
                    html += `<div id="hiddenItems_${type}" class="hidden">`;
                    
                    typeItems.slice(5).forEach((item, index) => {
                        const preview = item.content.substring(0, 150) + (item.content.length > 150 ? '...' : '');
                        const itemId = `${type}_${index + 5}`;
                        const sourceUrl = item.source_url || '';
                        html += `
                            <div class="card-minimal rounded-xl p-4 hover:shadow-xl transition-all duration-300">
                                <div class="flex justify-between items-start mb-3">
                                    <h4 class="text-sm font-medium text-gray-200 leading-relaxed">${item.title}</h4>
                                    <button onclick="scraperApp.viewMarkdown('${itemId}', ${JSON.stringify(item.content).replace(/"/g, '&quot;')}, '${sourceUrl}')" 
                                            class="btn-primary text-gray-100 px-3 py-1.5 text-xs rounded-lg hover:shadow-lg transition-all duration-300 ml-3 flex-shrink-0">
                                        <i class="fas fa-eye mr-1"></i>View
                                    </button>
                                </div>
                                <p class="text-xs text-gray-400 mb-3 leading-relaxed">${preview}</p>
                                <div class="flex justify-between items-center text-xs text-gray-500">
                                    <span class="font-mono">${item.content.length} chars</span>
                                    ${item.source_url ? `<a href="${item.source_url}" target="_blank" class="text-gray-400 hover:text-gray-300 transition-colors">Source</a>` : ''}
                                </div>
                            </div>
                        `;
                    });
                    
                    html += `</div>`;
                    
                    // Add expand/collapse button
                    html += `
                        <div class="text-center mt-4">
                            <button onclick="scraperApp.toggleItemsDisplay('${type}')" 
                                    id="toggleBtn_${type}"
                                    class="btn-sleek text-gray-300 px-4 py-2 text-sm rounded-lg hover:shadow-lg transition-all duration-300">
                                <i class="fas fa-chevron-down mr-2"></i>Show ${typeItems.length - 5} more ${type} items
                            </button>
                        </div>
                    `;
                }
                
                html += '</div></div>';
            }
            
            html += '</div>';
            resultsContent.innerHTML = html;
        }
        
        resultsSection.classList.remove('hidden');
    }

    showJsonView() {
        if (!this.currentResults) {
            alert('No results to display');
            return;
        }

        const modal = document.createElement('div');
        modal.className = 'fixed inset-0 bg-black/80 backdrop-blur-sm flex items-center justify-center z-50 p-4';
        modal.innerHTML = `
            <div class="glass-effect rounded-2xl max-w-6xl max-h-[90vh] w-full overflow-hidden shadow-2xl" style="background: rgba(12, 12, 12, 0.95); border: 1px solid rgba(255, 255, 255, 0.1);">
                <div class="flex justify-between items-center p-6 border-b border-gray-700/50">
                    <h3 class="text-lg font-medium text-gray-100">
                        <i class="fas fa-code mr-3 text-gray-400"></i>JSON Results
                    </h3>
                    <button onclick="this.closest('.fixed').remove()" 
                            class="btn-sleek px-4 py-2 text-sm text-gray-300 rounded-lg hover:text-red-300 transition-all duration-300"
                            style="background: linear-gradient(135deg, #2a1a1a 0%, #3a2a2a 100%); border: 1px solid rgba(255, 255, 255, 0.1);">
                        <i class="fas fa-times"></i>
                    </button>
                </div>
                <div class="p-6 overflow-auto max-h-[calc(90vh-4rem)]">
                    <div class="mb-4 flex space-x-3">
                        <button onclick="scraperApp.copyJsonToClipboard()" 
                                class="btn-primary px-4 py-2 text-sm text-gray-100 rounded-lg hover:shadow-lg transition-all duration-300"
                                style="background: linear-gradient(135deg, #404040 0%, #505050 100%); border: 1px solid rgba(255, 255, 255, 0.15);">
                            <i class="fas fa-copy mr-2"></i>Copy JSON
                        </button>
                        <button onclick="scraperApp.downloadJsonFile()" 
                                class="btn-primary px-4 py-2 text-sm text-gray-100 rounded-lg hover:shadow-lg transition-all duration-300"
                                style="background: linear-gradient(135deg, #404040 0%, #505050 100%); border: 1px solid rgba(255, 255, 255, 0.15);">
                            <i class="fas fa-download mr-2"></i>Download JSON
                        </button>
                    </div>
                    <pre class="p-6 rounded-xl text-sm text-gray-300 overflow-auto font-mono" 
                         style="background: rgba(8, 8, 8, 0.8); border: 1px solid rgba(255, 255, 255, 0.05); max-height: 70vh;"><code id="jsonContent">${JSON.stringify(this.currentResults, null, 2)}</code></pre>
                </div>
            </div>
        `;
        
        document.body.appendChild(modal);
        
        // Close modal when clicking outside
        modal.addEventListener('click', (e) => {
            if (e.target === modal) {
                modal.remove();
            }
        });
    }

    viewMarkdown(itemId, content, sourceUrl = '') {
        // Remove any existing modal with this itemId first
        const existingModal = document.querySelector(`[data-item-id="${itemId}"]`);
        if (existingModal) {
            existingModal.remove();
        }
        
        const currentMode = 'formatted'; // Always start in formatted mode
        
        // Properly escape content for data attributes
        const escapedContent = content.replace(/"/g, '&quot;').replace(/'/g, '&#39;');
        
        const modalHtml = `
            <div class="fixed inset-0 bg-black/80 backdrop-blur-sm flex items-center justify-center z-50" data-item-id="${itemId}" data-content="${escapedContent}" data-source-url="${sourceUrl}">
                <div class="glass-effect rounded-2xl p-8 max-w-4xl w-full mx-4 shadow-2xl" style="max-height: 90vh; background: rgba(12, 12, 12, 0.95); border: 1px solid rgba(255, 255, 255, 0.1);">
                    <div class="flex justify-between items-center mb-6">
                        <h3 class="text-lg font-medium text-gray-100">Content View</h3>
                        <div class="flex space-x-3">
                            <button onclick="scraperApp.toggleMarkdownView('${itemId}')" 
                                    class="btn-sleek px-4 py-2 text-sm text-gray-300 rounded-lg hover:text-gray-100 transition-all duration-300" 
                                    style="background: linear-gradient(135deg, #1a1a1a 0%, #2a2a2a 100%); border: 1px solid rgba(255, 255, 255, 0.1);">
                                Toggle Raw/Formatted
                            </button>
                            <button onclick="scraperApp.copyContentToClipboard('${itemId}')" 
                                    class="btn-primary px-4 py-2 text-sm text-gray-100 rounded-lg hover:shadow-lg transition-all duration-300"
                                    style="background: linear-gradient(135deg, #404040 0%, #505050 100%); border: 1px solid rgba(255, 255, 255, 0.15);">
                                <i class="fas fa-copy mr-2"></i>Copy
                            </button>
                            <button onclick="this.closest('.fixed').remove()" 
                                    class="btn-sleek px-4 py-2 text-sm text-gray-300 rounded-lg hover:text-red-300 transition-all duration-300"
                                    style="background: linear-gradient(135deg, #2a1a1a 0%, #3a2a2a 100%); border: 1px solid rgba(255, 255, 255, 0.1);">
                                <i class="fas fa-times"></i>
                            </button>
                        </div>
                    </div>
                    <div id="contentView_${itemId}" data-view-mode="${currentMode}" class="overflow-y-auto overflow-x-hidden rounded-xl" style="max-height: 70vh;">
                        <div class="p-6 rounded-xl text-sm text-gray-300 prose prose-invert max-w-none break-words overflow-wrap-anywhere overflow-x-hidden" 
                             style="background: rgba(8, 8, 8, 0.8); border: 1px solid rgba(255, 255, 255, 0.05);">
                            ${this.simpleMarkdownToHtml(content, sourceUrl)}
                        </div>
                    </div>
                </div>
            </div>
        `;
        
        document.body.insertAdjacentHTML('beforeend', modalHtml);
        
        // Close modal when clicking outside
        const modalElement = document.querySelector(`[data-item-id="${itemId}"]`);
        modalElement.addEventListener('click', (e) => {
            if (e.target === modalElement) {
                modalElement.remove();
            }
        });
    }

    copyJsonToClipboard() {
        const jsonContent = document.getElementById('jsonContent').textContent;
        navigator.clipboard.writeText(jsonContent).then(() => {
            this.showToast('JSON copied to clipboard!', 'success');
        }).catch(() => {
            this.showToast('Failed to copy JSON', 'error');
        });
    }

    downloadJsonFile() {
        const jsonContent = JSON.stringify(this.currentResults, null, 2);
        const blob = new Blob([jsonContent], { type: 'application/json' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `scraper_results_${new Date().toISOString().split('T')[0]}.json`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
        this.showToast('JSON file downloaded!', 'success');
    }

    copyContentToClipboard(itemId) {
        const modal = document.querySelector(`[data-item-id="${itemId}"]`);
        const content = modal?.dataset.content || '';
        navigator.clipboard.writeText(content).then(() => {
            this.showToast('Content copied to clipboard!', 'success');
        }).catch(() => {
            this.showToast('Failed to copy content', 'error');
        });
    }

    toggleMarkdownView(itemId) {
        const contentView = document.getElementById(`contentView_${itemId}`);
        const modal = document.querySelector(`[data-item-id="${itemId}"]`);
        const content = modal?.dataset.content || '';
        // Unescape the content
        const unescapedContent = content.replace(/&quot;/g, '"').replace(/&#39;/g, "'");
        const currentMode = contentView.dataset.viewMode || 'formatted';
        
        if (currentMode === 'formatted') {
            // Switch to raw view
            contentView.innerHTML = `
                <pre class="p-6 rounded-xl text-sm text-gray-300 whitespace-pre-wrap font-mono break-words overflow-wrap-anywhere overflow-x-hidden" 
                     style="background: rgba(8, 8, 8, 0.8); border: 1px solid rgba(255, 255, 255, 0.05); max-height: 70vh; overflow-y: auto;">${unescapedContent}</pre>
            `;
            contentView.dataset.viewMode = 'raw';
        } else {
            // Switch back to formatted view (markdown rendering)
            const formattedHtml = this.simpleMarkdownToHtml(unescapedContent, modal?.dataset.sourceUrl || '');
            contentView.innerHTML = `
                <div class="p-6 rounded-xl text-sm text-gray-300 prose prose-invert max-w-none break-words overflow-wrap-anywhere overflow-x-hidden" 
                     style="background: rgba(8, 8, 8, 0.8); border: 1px solid rgba(255, 255, 255, 0.05); max-height: 70vh; overflow-y: auto;">
                    ${formattedHtml}
                </div>
            `;
            contentView.dataset.viewMode = 'formatted';
        }
    }

    simpleMarkdownToHtml(markdown, sourceUrl = '') {
        let html = markdown;
        
        // Clean up and normalize line breaks first
        html = html.replace(/\r\n/g, '\n').replace(/\r/g, '\n');
        
        // Handle images: ![alt](url) - must be before regular links
        html = html.replace(/!\[([^\]]*)\]\(([^)]+)\)/g, (match, alt, url) => {
            // Handle relative URLs by making them absolute
            if (url.startsWith('/')) {
                if (sourceUrl) {
                    // Extract domain from sourceUrl
                    try {
                        const urlObj = new URL(sourceUrl);
                        url = `${urlObj.protocol}//${urlObj.host}${url}`;
                    } catch (e) {
                        console.warn('Failed to parse source URL:', sourceUrl);
                    }
                } else {
                    // Fallback: try to extract base domain from any existing absolute URLs in the content
                    const domainMatch = html.match(/https?:\/\/([^\/\s]+)/);
                    if (domainMatch) {
                        url = `https://${domainMatch[1]}${url}`;
                    }
                }
            }
            
            // Special handling for SVGs - they might need different loading approach
            const isSvg = url.toLowerCase().includes('.svg');
            const loadHandler = isSvg ? 
                `onload="this.nextElementSibling.style.display='none'" onerror="console.log('SVG failed to load:', this.src); this.style.display='none'; this.nextElementSibling.style.display='block'"` :
                `onload="this.nextElementSibling.style.display='none'" onerror="this.style.display='none'; this.nextElementSibling.style.display='block'"`;
            
            return `<div class="image-container my-4">
                        <img src="${url}" alt="${alt}" class="max-w-full h-auto rounded-lg mx-auto block" ${loadHandler}>
                        <div class="text-center text-gray-500 text-sm p-4 border border-gray-600 rounded bg-gray-800" style="display: none;">
                            <i class="fas fa-image mr-2"></i>Image: ${alt || 'Untitled'}<br>
                            <span class="text-xs break-all">${url}</span>
                        </div>
                    </div>`;
        });
        
        // Handle links: [text](url) - but not if it's just [# text] without URL
        html = html.replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2" target="_blank" class="text-blue-400 underline hover:text-blue-300 break-words overflow-wrap-anywhere overflow-x-hidden">$1</a>');
        
        // Handle standalone markdown-style links that don't have URLs (like [# Product])
        html = html.replace(/\[(#{1,6})\s+([^\]]+)\]/g, '<span class="text-blue-400 font-semibold">$1 $2</span>');
        
        // Handle headers (must be at start of line)
        html = html.replace(/^#### (.*$)/gim, '<h4 class="text-base font-semibold text-gray-200 mt-6 mb-3 border-l-4 border-blue-500 pl-3">$1</h4>');
        html = html.replace(/^### (.*$)/gim, '<h3 class="text-lg font-semibold text-white mt-6 mb-3 border-l-4 border-green-500 pl-3">$1</h3>');
        html = html.replace(/^## (.*$)/gim, '<h2 class="text-xl font-bold text-white mt-8 mb-4 pb-2 border-b border-gray-600">$1</h2>');
        html = html.replace(/^# (.*$)/gim, '<h1 class="text-2xl font-bold text-white mt-8 mb-4 pb-3 border-b-2 border-blue-500">$1</h1>');
        
        // Handle code blocks (triple backticks)
        html = html.replace(/```(\w+)?\n([\s\S]*?)```/g, '<pre class="bg-gray-900 border border-gray-600 rounded-lg p-4 my-4 overflow-x-auto"><code class="text-green-300 text-sm">$2</code></pre>');
        
        // Handle inline code
        html = html.replace(/`([^`]+)`/g, '<code class="bg-gray-700 px-2 py-1 rounded text-green-300 text-sm font-mono">$1</code>');
        
        // Handle bold and italic
        html = html.replace(/\*\*\*(.*?)\*\*\*/g, '<strong><em class="font-bold italic text-yellow-300">$1</em></strong>');
        html = html.replace(/\*\*(.*?)\*\*/g, '<strong class="font-bold text-white">$1</strong>');
        html = html.replace(/\*(.*?)\*/g, '<em class="italic text-gray-300">$1</em>');
        
        // Handle lists
        html = html.replace(/^- (.*$)/gim, '<li class="ml-4 mb-1 text-gray-300">• $1</li>');
        html = html.replace(/^\d+\. (.*$)/gim, '<li class="ml-4 mb-1 text-gray-300 list-decimal">$1</li>');
        
        // Wrap consecutive list items
        html = html.replace(/(<li[^>]*>.*<\/li>\s*)+/g, '<ul class="my-3 space-y-1">$&</ul>');
        
        // Handle blockquotes
        html = html.replace(/^> (.*$)/gim, '<blockquote class="border-l-4 border-gray-500 pl-4 py-2 my-4 bg-gray-800 italic text-gray-300">$1</blockquote>');
        
        // Handle horizontal rules
        html = html.replace(/^---$/gim, '<hr class="border-gray-600 my-6">');
        
        // Clean up URLs that aren't in links (make them clickable) 
        html = html.replace(/(^|[^"])(https?:\/\/[^\s<>"]+)/g, '$1<a href="$2" target="_blank" class="text-blue-400 underline hover:text-blue-300 break-all word-break-all overflow-wrap-anywhere overflow-x-hidden inline-block max-w-full">$2</a>');
        
        // Handle paragraphs - split by double newlines
        const paragraphs = html.split(/\n\s*\n/);
        html = paragraphs.map(p => {
            p = p.trim();
            if (!p) return '';
            
            // Don't wrap if it's already a block element
            if (p.match(/^<(h[1-6]|div|p|ul|ol|li|blockquote|pre|hr)/)) {
                return p;
            }
            
            // Replace single newlines with <br> within paragraphs
            p = p.replace(/\n/g, '<br>');
            
            return `<p class="mb-4 text-gray-300 leading-relaxed break-words overflow-wrap-anywhere overflow-x-hidden word-break-break-word">${p}</p>`;
        }).filter(p => p).join('\n');
        
        return html;
    }

    showToast(message, type = 'info') {
        const toast = document.createElement('div');
        const bgColor = type === 'success' ? 'bg-green-600' : type === 'error' ? 'bg-red-600' : 'bg-blue-600';
        toast.className = `fixed top-4 right-4 ${bgColor} text-white px-4 py-2 rounded-lg shadow-lg z-50 transition-opacity duration-300`;
        toast.textContent = message;
        
        document.body.appendChild(toast);
        
        setTimeout(() => {
            toast.style.opacity = '0';
            setTimeout(() => {
                document.body.removeChild(toast);
            }, 300);
        }, 3000);
    }

    downloadResults(jobId) {
        window.open(`/api/jobs/${jobId}/download`, '_blank');
    }

    async loadJobHistory() {
        try {
            const response = await fetch('/api/jobs');
            const jobs = await response.json();
            
            this.displayJobHistory(jobs);
        } catch (error) {
            console.error('Failed to load job history:', error);
        }
    }

    displayJobHistory(jobs) {
        const historyElement = document.getElementById('jobHistory');
        const jobEntries = Object.entries(jobs).slice(-5); // Show last 5 jobs
        
        if (jobEntries.length === 0) {
            historyElement.innerHTML = '<p class="text-gray-500 text-sm text-center py-4">No previous jobs</p>';
            return;
        }
        
        let html = '';
        jobEntries.forEach(([jobId, job]) => {
            const statusClass = job.status === 'completed' ? 'text-gray-300' : 
                               job.status === 'error' ? 'text-red-400' : 'text-gray-400';
            const statusIcon = job.status === 'completed' ? 'fa-check-circle' : 
                              job.status === 'error' ? 'fa-exclamation-circle' : 'fa-clock';
            
            html += `
                <div class="card-minimal rounded-lg p-3 hover:shadow-lg transition-all duration-300">
                    <div class="flex justify-between items-center mb-2">
                        <span class="text-xs text-gray-500 font-mono">${jobId.substring(0, 8)}...</span>
                        <i class="fas ${statusIcon} ${statusClass} text-sm"></i>
                    </div>
                    <div class="text-sm font-medium text-gray-300">
                        ${job.config ? job.config.customer_name : 'Unknown'}
                    </div>
                    ${job.total_items ? `<div class="text-xs text-gray-500 mt-1">${job.total_items} items</div>` : ''}
                </div>
            `;
        });
        
        historyElement.innerHTML = html;
    }

    toggleItemsDisplay(type) {
        const hiddenItems = document.getElementById(`hiddenItems_${type}`);
        const toggleBtn = document.getElementById(`toggleBtn_${type}`);
        
        if (hiddenItems.classList.contains('hidden')) {
            // Show hidden items
            hiddenItems.classList.remove('hidden');
            hiddenItems.style.display = 'grid';
            hiddenItems.style.gap = '0.5rem'; // match the grid gap
            toggleBtn.innerHTML = '<i class="fas fa-chevron-up mr-1"></i>Hide additional items';
        } else {
            // Hide items
            hiddenItems.classList.add('hidden');
            hiddenItems.style.display = 'none';
            // Get the count from the button text or calculate it
            const hiddenCount = hiddenItems.children.length;
            toggleBtn.innerHTML = `<i class="fas fa-chevron-down mr-1"></i>Show ${hiddenCount} more ${type} items`;
        }
    }
}

// Initialize the app when the page loads
let scraperApp;
document.addEventListener('DOMContentLoaded', () => {
    scraperApp = new ScraperApp();
}); 