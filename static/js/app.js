/**
 * NetSuite AI Agent - Frontend JavaScript
 * Handles settings, analysis execution, progress tracking, and results display.
 */

// ============== DOM Elements ==============
const els = {
    // Settings
    nsAccountId: document.getElementById('ns-account-id'),
    nsConsumerKey: document.getElementById('ns-consumer-key'),
    nsConsumerSecret: document.getElementById('ns-consumer-secret'),
    nsTokenId: document.getElementById('ns-token-id'),
    nsTokenSecret: document.getElementById('ns-token-secret'),
    inactiveThreshold: document.getElementById('inactive-threshold'),
    outputPath: document.getElementById('output-path'),
    btnSaveSettings: document.getElementById('btn-save-settings'),
    btnTestConnection: document.getElementById('btn-test-connection'),
    settingsMessage: document.getElementById('settings-message'),

    // Run
    filterStatus: document.getElementById('filter-status'),
    exportExcel: document.getElementById('export-excel'),
    exportCsv: document.getElementById('export-csv'),
    exportJson: document.getElementById('export-json'),
    btnRunAnalysis: document.getElementById('btn-run-analysis'),
    runMessage: document.getElementById('run-message'),

    // Progress
    progressPanel: document.getElementById('progress-panel'),
    progressBar: document.getElementById('progress-bar'),
    progressText: document.getElementById('progress-text'),

    // Results
    resultsPanel: document.getElementById('results-panel'),
    summaryCards: document.getElementById('summary-cards'),
    resultsTable: document.getElementById('results-table'),

    // Reports
    reportsList: document.getElementById('reports-list'),
    btnRefreshReports: document.getElementById('btn-refresh-reports'),
};

// ============== API Helpers ==============

async function apiGet(endpoint) {
    const res = await fetch(endpoint);
    return res.json();
}

async function apiPost(endpoint, data = {}) {
    const res = await fetch(endpoint, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(data),
    });
    return res.json();
}

function showMessage(el, text, type = 'info') {
    el.textContent = text;
    el.className = `message show ${type}`;
    setTimeout(() => el.classList.remove('show'), 5000);
}

// ============== Settings ==============

async function loadSettings() {
    try {
        const config = await apiGet('/api/config');
        els.nsAccountId.value = config.netsuite_account_id || '';
        els.nsConsumerKey.value = config.netsuite_consumer_key || '';
        els.nsTokenId.value = config.netsuite_token_id || '';
        els.inactiveThreshold.value = config.inactive_threshold || '90';
        els.outputPath.value = config.output_path || './reports';
        // Secrets remain empty for security
    } catch (e) {
        console.error('Failed to load settings:', e);
    }
}

async function saveSettings() {
    const data = {
        netsuite_account_id: els.nsAccountId.value,
        netsuite_consumer_key: els.nsConsumerKey.value,
        netsuite_consumer_secret: els.nsConsumerSecret.value,
        netsuite_token_id: els.nsTokenId.value,
        netsuite_token_secret: els.nsTokenSecret.value,
        inactive_threshold: els.inactiveThreshold.value,
        output_path: els.outputPath.value,
    };

    try {
        const result = await apiPost('/api/config', data);
        if (result.success) {
            showMessage(els.settingsMessage, 'Settings saved successfully!', 'success');
            els.btnRunAnalysis.disabled = false;
        } else {
            showMessage(els.settingsMessage, result.message || 'Failed to save settings', 'error');
        }
    } catch (e) {
        showMessage(els.settingsMessage, 'Error saving settings: ' + e.message, 'error');
    }
}

async function testConnection() {
    els.btnTestConnection.disabled = true;
    els.btnTestConnection.textContent = 'Testing...';

    try {
        // Save settings first so the test uses current values
        await saveSettings();
        const result = await apiPost('/api/test-connection');
        showMessage(
            els.settingsMessage,
            result.message,
            result.success ? 'success' : 'error'
        );
        if (result.success) {
            els.btnRunAnalysis.disabled = false;
        }
    } catch (e) {
        showMessage(els.settingsMessage, 'Connection test failed: ' + e.message, 'error');
    } finally {
        els.btnTestConnection.disabled = false;
        els.btnTestConnection.textContent = 'Test Connection';
    }
}

// ============== Analysis ==============

async function runAnalysis() {
    const formats = [];
    if (els.exportExcel.checked) formats.push('excel');
    if (els.exportCsv.checked) formats.push('csv');
    if (els.exportJson.checked) formats.push('json');

    const data = {
        threshold: parseInt(els.inactiveThreshold.value, 10) || 90,
        status_filter: els.filterStatus.value || null,
        export_formats: formats.length ? formats : ['excel', 'csv', 'json'],
    };

    // UI updates
    els.btnRunAnalysis.disabled = true;
    els.btnRunAnalysis.querySelector('.btn-text').textContent = 'Running...';
    els.btnRunAnalysis.querySelector('.spinner').classList.remove('hidden');
    els.progressPanel.classList.remove('hidden');
    els.resultsPanel.classList.add('hidden');
    els.runMessage.classList.remove('show');

    try {
        const result = await apiPost('/api/run', data);
        if (result.success) {
            showMessage(els.runMessage, 'Analysis started!', 'success');
            startProgressPolling();
        } else {
            showMessage(els.runMessage, result.message || 'Failed to start', 'error');
            resetRunButton();
        }
    } catch (e) {
        showMessage(els.runMessage, 'Error: ' + e.message, 'error');
        resetRunButton();
    }
}

function resetRunButton() {
    els.btnRunAnalysis.disabled = false;
    els.btnRunAnalysis.querySelector('.btn-text').textContent = 'Run Analysis';
    els.btnRunAnalysis.querySelector('.spinner').classList.add('hidden');
}

// ============== Progress Polling ==============

let progressInterval = null;

function startProgressPolling() {
    if (progressInterval) clearInterval(progressInterval);
    progressInterval = setInterval(async () => {
        try {
            const status = await apiGet('/api/status');
            updateProgress(status);

            if (!status.running) {
                clearInterval(progressInterval);
                progressInterval = null;
                resetRunButton();

                if (status.error) {
                    showMessage(els.runMessage, status.error, 'error');
                } else if (status.progress === 100) {
                    showMessage(els.runMessage, 'Analysis complete!', 'success');
                    await loadResults();
                    await loadReports();
                }
            }
        } catch (e) {
            console.error('Progress poll error:', e);
        }
    }, 1500);
}

function updateProgress(status) {
    els.progressBar.style.width = `${status.progress}%`;
    els.progressText.textContent = status.message || 'Processing...';
}

// ============== Results ==============

async function loadResults() {
    try {
        const data = await apiGet('/api/results');
        if (!data.success && !data.summary) {
            return; // No results yet
        }

        renderSummary(data.summary);
        renderTable(data.customers || []);
        els.resultsPanel.classList.remove('hidden');
    } catch (e) {
        console.error('Failed to load results:', e);
    }
}

function renderSummary(summary) {
    const cards = [
        { label: 'Total Customers', value: summary.total_customers, cls: '' },
        { label: 'Active', value: summary.active_customers, cls: 'active' },
        { label: 'At Risk', value: summary.at_risk_customers, cls: 'at-risk' },
        { label: 'Inactive', value: summary.inactive_customers, cls: 'inactive' },
        { label: 'New', value: summary.new_customers, cls: '' },
        { label: 'Total Revenue', value: '$' + (summary.total_revenue || 0).toLocaleString(), cls: '' },
    ];

    els.summaryCards.innerHTML = cards.map(c => `
        <div class="summary-card ${c.cls}">
            <div class="value">${c.value}</div>
            <div class="label">${c.label}</div>
        </div>
    `).join('');
}

function renderTable(customers) {
    const tbody = els.resultsTable.querySelector('tbody');
    if (!customers.length) {
        tbody.innerHTML = '<tr><td colspan="9" class="empty-state">No customers match the selected filter.</td></tr>';
        return;
    }

    tbody.innerHTML = customers.map(c => `
        <tr>
            <td>${c.customer_id}</td>
            <td>${escapeHtml(c.entity_id)}</td>
            <td>${escapeHtml(c.company_name || '-')}</td>
            <td>${escapeHtml(c.email || '-')}</td>
            <td><span class="status-badge ${c.status}">${c.status}</span></td>
            <td>${c.days_since_last_order ?? '-'}</td>
            <td>${c.last_order_date || '-'}</td>
            <td>${c.total_orders}</td>
            <td>$${(c.total_revenue || 0).toLocaleString()}</td>
        </tr>
    `).join('');
}

function escapeHtml(text) {
    if (!text) return '';
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// ============== Reports ==============

async function loadReports() {
    try {
        const files = await apiGet('/api/reports');
        renderReports(files);
    } catch (e) {
        console.error('Failed to load reports:', e);
    }
}

function renderReports(files) {
    if (!files.length) {
        els.reportsList.innerHTML = '<p class="empty-state">No reports generated yet.</p>';
        return;
    }

    els.reportsList.innerHTML = files.map(f => {
        const size = formatBytes(f.size);
        const date = new Date(f.modified).toLocaleString();
        return `
            <div class="report-item">
                <div class="report-info">
                    <span class="report-name">${escapeHtml(f.name)}</span>
                    <span class="report-meta">${size} &middot; ${date}</span>
                </div>
                <div class="report-actions">
                    <a href="/api/reports/${encodeURIComponent(f.name)}" class="btn btn-primary btn-small" download>Download</a>
                    <button class="btn btn-secondary btn-small" onclick="deleteReport('${escapeHtml(f.name)}')">Delete</button>
                </div>
            </div>
        `;
    }).join('');
}

async function deleteReport(filename) {
    if (!confirm(`Delete "${filename}"?`)) return;
    try {
        const res = await fetch(`/api/reports/${encodeURIComponent(filename)}`, { method: 'DELETE' });
        const data = await res.json();
        if (data.success) {
            await loadReports();
        }
    } catch (e) {
        console.error('Delete failed:', e);
    }
}

function formatBytes(bytes) {
    if (bytes === 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
}

// ============== Event Listeners ==============

document.addEventListener('DOMContentLoaded', () => {
    loadSettings();
    loadReports();

    els.btnSaveSettings.addEventListener('click', saveSettings);
    els.btnTestConnection.addEventListener('click', testConnection);
    els.btnRunAnalysis.addEventListener('click', runAnalysis);
    els.btnRefreshReports.addEventListener('click', loadReports);
});
