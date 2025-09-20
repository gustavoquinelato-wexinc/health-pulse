/**
 * Reusable Vectorization Card Component
 * Provides table-specific vectorization with progress tracking
 */

class VectorizationCard {
    constructor(config) {
        this.tableName = config.tableName;
        this.displayName = config.displayName;
        this.containerId = config.containerId;
        this.apiBaseUrl = config.apiBaseUrl || '/api/v1/vectorization';
        
        this.sessionId = null;
        this.progressInterval = null;
        this.isProcessing = false;
        
        this.init();
    }
    
    init() {
        this.render();
        this.attachEventListeners();
        this.loadInitialStatus();
    }
    
    render() {
        const container = document.getElementById(this.containerId);
        if (!container) {
            console.error(`Container ${this.containerId} not found`);
            return;
        }
        
        container.innerHTML = `
            <div class="vectorization-card bg-white rounded-lg shadow-sm border p-4 mb-6" style="border-color: var(--border-color); background-color: var(--bg-secondary);">
                <div class="flex items-center justify-between">
                    <div class="flex items-center space-x-3">
                        <div class="vectorization-icon">
                            <svg class="w-5 h-5" style="color: var(--text-secondary);" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 10V3L4 14h7v7l9-11h-7z"></path>
                            </svg>
                        </div>
                        <div>
                            <h3 class="text-sm font-medium" style="color: var(--text-primary);">
                                Vectorize ${this.displayName}
                            </h3>
                            <p class="text-xs vectorization-status" style="color: var(--text-secondary);">
                                Loading status...
                            </p>
                        </div>
                    </div>
                    
                    <div class="flex items-center space-x-2">
                        <button class="details-btn px-3 py-1.5 text-xs rounded-md border" 
                                style="border-color: var(--border-color); color: var(--text-secondary); background-color: var(--bg-primary);">
                            Details
                        </button>
                        <button class="execute-btn px-3 py-1.5 text-xs rounded-md text-white" 
                                style="background-color: #3b82f6;">
                            Execute
                        </button>
                    </div>
                </div>
                
                <!-- Progress Bar (hidden by default) -->
                <div class="progress-container mt-3 hidden">
                    <div class="flex items-center justify-between mb-1">
                        <span class="text-xs progress-text" style="color: var(--text-secondary);">Processing...</span>
                        <span class="text-xs progress-percentage" style="color: var(--text-secondary);">0%</span>
                    </div>
                    <div class="w-full bg-gray-200 rounded-full h-2" style="background-color: var(--bg-tertiary);">
                        <div class="progress-bar bg-blue-500 h-2 rounded-full transition-all duration-300" style="width: 0%"></div>
                    </div>
                    <div class="text-xs mt-1 current-item" style="color: var(--text-tertiary);"></div>
                </div>
            </div>
        `;
    }
    
    attachEventListeners() {
        const container = document.getElementById(this.containerId);
        
        // Execute button
        const executeBtn = container.querySelector('.execute-btn');
        executeBtn.addEventListener('click', () => this.executeVectorization());
        
        // Details button
        const detailsBtn = container.querySelector('.details-btn');
        detailsBtn.addEventListener('click', () => this.showDetails());
    }
    
    async loadInitialStatus() {
        try {
            const token = this.getAuthToken();
            const response = await fetch(`${this.apiBaseUrl}/table/${this.tableName}/status`, {
                headers: {
                    'Authorization': `Bearer ${token}`,
                    'Content-Type': 'application/json'
                }
            });
            
            if (response.ok) {
                const status = await response.json();
                this.updateStatus(status);
            } else {
                this.updateStatusText('Error loading status');
            }
        } catch (error) {
            console.error('Error loading initial status:', error);
            this.updateStatusText('Error loading status');
        }
    }
    
    async executeVectorization() {
        if (this.isProcessing) return;
        
        try {
            this.setProcessing(true);
            this.updateStatusText('Starting vectorization...');
            
            const token = this.getAuthToken();
            const response = await fetch(`${this.apiBaseUrl}/table/${this.tableName}/execute`, {
                method: 'POST',
                headers: {
                    'Authorization': `Bearer ${token}`,
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({})
            });
            
            if (response.ok) {
                const result = await response.json();
                this.sessionId = result.session_id;
                
                if (result.status === 'completed') {
                    this.showNotification('No items to vectorize', 'info');
                    this.setProcessing(false);
                    this.loadInitialStatus();
                } else {
                    this.showProgressBar();
                    this.startProgressTracking();
                    this.showNotification('Vectorization started', 'success');
                }
            } else {
                const error = await response.json();
                this.showNotification(`Error: ${error.detail}`, 'error');
                this.setProcessing(false);
            }
        } catch (error) {
            console.error('Error executing vectorization:', error);
            this.showNotification('Error starting vectorization', 'error');
            this.setProcessing(false);
        }
    }
    
    startProgressTracking() {
        if (this.progressInterval) {
            clearInterval(this.progressInterval);
        }
        
        this.progressInterval = setInterval(async () => {
            await this.updateProgress();
        }, 1000); // Update every second
    }
    
    async updateProgress() {
        if (!this.sessionId) return;
        
        try {
            const token = this.getAuthToken();
            const response = await fetch(`${this.apiBaseUrl}/session/${this.sessionId}/progress`, {
                headers: {
                    'Authorization': `Bearer ${token}`,
                    'Content-Type': 'application/json'
                }
            });
            
            if (response.ok) {
                const progress = await response.json();
                this.updateProgressBar(progress);
                
                if (progress.status === 'completed' || progress.status === 'error' || progress.status === 'cancelled') {
                    this.stopProgressTracking();
                    this.setProcessing(false);
                    
                    if (progress.status === 'completed') {
                        this.showNotification('Vectorization completed successfully', 'success');
                        this.hideProgressBar();
                        this.loadInitialStatus();
                    } else if (progress.status === 'error') {
                        this.showNotification(`Vectorization failed: ${progress.error}`, 'error');
                        this.hideProgressBar();
                    }
                }
            }
        } catch (error) {
            console.error('Error updating progress:', error);
        }
    }
    
    stopProgressTracking() {
        if (this.progressInterval) {
            clearInterval(this.progressInterval);
            this.progressInterval = null;
        }
    }
    
    updateStatus(status) {
        this.updateStatusText(`${status.total_items} items • ${status.vectorized_items} vectorized`);
        
        if (status.status === 'processing') {
            this.sessionId = status.session_id;
            this.setProcessing(true);
            this.showProgressBar();
            this.startProgressTracking();
        }
    }
    
    updateStatusText(text) {
        const container = document.getElementById(this.containerId);
        const statusElement = container.querySelector('.vectorization-status');
        statusElement.textContent = text;
    }
    
    updateProgressBar(progress) {
        const container = document.getElementById(this.containerId);
        const progressBar = container.querySelector('.progress-bar');
        const progressText = container.querySelector('.progress-text');
        const progressPercentage = container.querySelector('.progress-percentage');
        const currentItem = container.querySelector('.current-item');
        
        progressBar.style.width = `${progress.progress_percentage}%`;
        progressText.textContent = `Processing ${progress.processed}/${progress.total} items...`;
        progressPercentage.textContent = `${progress.progress_percentage}%`;
        
        if (progress.current_item) {
            currentItem.textContent = `Current: ${progress.current_item}`;
        }
    }
    
    showProgressBar() {
        const container = document.getElementById(this.containerId);
        const progressContainer = container.querySelector('.progress-container');
        progressContainer.classList.remove('hidden');
    }
    
    hideProgressBar() {
        const container = document.getElementById(this.containerId);
        const progressContainer = container.querySelector('.progress-container');
        progressContainer.classList.add('hidden');
    }
    
    setProcessing(processing) {
        this.isProcessing = processing;
        const container = document.getElementById(this.containerId);
        const executeBtn = container.querySelector('.execute-btn');
        
        if (processing) {
            executeBtn.textContent = 'Processing...';
            executeBtn.disabled = true;
            executeBtn.style.backgroundColor = '#9ca3af';
        } else {
            executeBtn.textContent = 'Execute';
            executeBtn.disabled = false;
            executeBtn.style.backgroundColor = '#3b82f6';
        }
    }
    
    async showDetails() {
        try {
            const token = this.getAuthToken();
            const response = await fetch(`${this.apiBaseUrl}/table/${this.tableName}/status`, {
                headers: {
                    'Authorization': `Bearer ${token}`,
                    'Content-Type': 'application/json'
                }
            });
            
            if (response.ok) {
                const status = await response.json();
                this.showDetailsModal(status);
            } else {
                this.showNotification('Error loading details', 'error');
            }
        } catch (error) {
            console.error('Error loading details:', error);
            this.showNotification('Error loading details', 'error');
        }
    }
    
    showDetailsModal(status) {
        // Create modal backdrop
        const backdrop = document.createElement('div');
        backdrop.className = 'fixed inset-0 bg-black bg-opacity-50 backdrop-blur-sm flex items-center justify-center z-50';
        
        // Create modal content
        const modal = document.createElement('div');
        modal.className = 'bg-white rounded-lg shadow-xl max-w-md w-full mx-4';
        modal.style.backgroundColor = 'var(--bg-secondary)';
        modal.style.border = '1px solid var(--border-color)';
        
        modal.innerHTML = `
            <div class="p-6">
                <h3 class="text-lg font-semibold mb-4" style="color: var(--text-primary);">
                    ${status.display_name} Vectorization Details
                </h3>
                <div class="space-y-3 text-sm">
                    <div class="flex justify-between">
                        <span style="color: var(--text-secondary);">Total Items:</span>
                        <span style="color: var(--text-primary);">${status.total_items}</span>
                    </div>
                    <div class="flex justify-between">
                        <span style="color: var(--text-secondary);">Vectorized:</span>
                        <span style="color: var(--text-primary);">${status.vectorized_items}</span>
                    </div>
                    <div class="flex justify-between">
                        <span style="color: var(--text-secondary);">Collection:</span>
                        <span style="color: var(--text-primary); font-mono; font-xs;">${status.qdrant_collection}</span>
                    </div>
                    <div class="flex justify-between">
                        <span style="color: var(--text-secondary);">Status:</span>
                        <span style="color: var(--text-primary);">${status.status}</span>
                    </div>
                    <div class="flex justify-between">
                        <span style="color: var(--text-secondary);">Last Updated:</span>
                        <span style="color: var(--text-primary);">${new Date(status.last_updated).toLocaleString()}</span>
                    </div>
                </div>
                <div class="flex justify-end mt-6">
                    <button id="closeDetailsBtn" class="px-4 py-2 text-sm rounded-lg border" style="border-color: var(--border-color); color: var(--text-secondary); background-color: var(--bg-primary);">
                        Close
                    </button>
                </div>
            </div>
        `;
        
        backdrop.appendChild(modal);
        document.body.appendChild(backdrop);
        
        // Handle close
        const closeBtn = modal.querySelector('#closeDetailsBtn');
        closeBtn.onclick = () => document.body.removeChild(backdrop);
        backdrop.onclick = (e) => {
            if (e.target === backdrop) document.body.removeChild(backdrop);
        };
    }
    
    getAuthToken() {
        return localStorage.getItem('authToken') || sessionStorage.getItem('authToken');
    }
    
    showNotification(message, type) {
        // Use existing notification system if available
        if (typeof showNotification === 'function') {
            showNotification(message, type);
        } else {
            console.log(`${type.toUpperCase()}: ${message}`);
        }
    }
    
    destroy() {
        this.stopProgressTracking();
        const container = document.getElementById(this.containerId);
        if (container) {
            container.innerHTML = '';
        }
    }
}
