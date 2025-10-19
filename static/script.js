// static/script.js
document.addEventListener('DOMContentLoaded', function() {
    const form = document.getElementById('codeForm');
    const results = document.getElementById('results');
    const errorDiv = document.getElementById('error');

    // Handle form submission
    form.addEventListener('submit', async function(e) {
        e.preventDefault();

        const code = document.getElementById('codeInput').value.trim();
        if (!code) {
            showError('Please enter some code to analyze.');
            return;
        }

        // Show loading state
        showResults();
        showTab('security');

        try {
            // If input looks like a GitHub repo URL, switch to repo analysis
            const isGithub = /^https?:\/\/github\.com\//i.test(code);
            if (isGithub) {
                __lastRepoUrl = code;
                const data = await analyzeRepoUrl(code);
                if (data.status === 'error') {
                    showError(data.error || 'Repository analysis failed');
                    hideResults();
                    return;
                }
                displayRepoResults(data);
            } else {
                const formData = new FormData(form);
                const response = await fetch('/analyze', {
                    method: 'POST',
                    body: formData
                });
                const data = await response.json();
                if (data.status === 'error') {
                    showError(data.error);
                    hideResults();
                    return;
                }
                displayResults(data);
            }

        } catch (error) {
            showError('Network error: ' + error.message);
            hideResults();
        }
    });
});

// (removed duplicate download handler and stray code block)

// Cache for current repository analysis results
let __repoAnalysis = null;
let __lastRepoUrl = null;

function showResults() {
    document.getElementById('results').style.display = 'block';
    document.getElementById('error').style.display = 'none';
}

function hideResults() {
    document.getElementById('results').style.display = 'none';
}

function showError(message) {
    const errorDiv = document.getElementById('error');
    errorDiv.textContent = message;
    errorDiv.style.display = 'block';
    document.getElementById('results').style.display = 'none';
}

function showTab(tabName, evt) {
    // Hide all tabs
    const tabContents = document.querySelectorAll('.tab-content');
    tabContents.forEach(tab => tab.classList.remove('active'));

    // Remove active class from all buttons
    const tabBtns = document.querySelectorAll('.tab-btn');
    tabBtns.forEach(btn => btn.classList.remove('active'));

    // Show selected tab
    document.getElementById(tabName).classList.add('active');

    // Add active class to clicked button
    if (evt && evt.target) {
        evt.target.classList.add('active');
    }
}

function displayResults(data) {
    const analysisResults = data.analysis_results || {};

    // Display Security issues
    displayCategoryIssues('security', analysisResults.security);

    // Display Maintainability issues
    displayCategoryIssues('maintainability', analysisResults.maintainability);

    // Display Style issues
    displayCategoryIssues('style', analysisResults.style);
}

function displayCategoryIssues(category, categoryData) {
    const container = document.getElementById(category);
    container.innerHTML = '';

    if (!categoryData || !categoryData.issues || categoryData.issues.length === 0) {
        container.innerHTML = '<div class="issue"><p class="issue-description">✅ No issues found in this category.</p></div>';
        return;
    }

    categoryData.issues.forEach(issue => {
        const issueDiv = document.createElement('div');
        issueDiv.className = `issue ${issue.severity}`;

        const title = issue.title || `${category.charAt(0).toUpperCase() + category.slice(1)} Issue`;
        const description = cleanDescription(issue.description || 'No description available');
        const severity = (issue.severity || 'medium').toLowerCase();

        issueDiv.innerHTML = `
            <div class="issue-title">
                ${getSeverityIcon(severity)} ${title}
                <span class="severity-badge severity-${severity}">${severity.toUpperCase()}</span>
            </div>
            <div class="issue-description">${description}</div>
        `;

        container.appendChild(issueDiv);
    });
}

function cleanDescription(description) {
    if (!description) return '';

    // Remove LLM formatting tags
    let cleaned = description
        .replace(/<s>/g, '')
        .replace(/<\/s>/g, '')
        .replace(/\[OUT\]/g, '')
        .replace(/\[\/OUT\]/g, '')
        .replace(/` ``/g, '```')
        .replace(/`  ``/g, '```');

    // Convert markdown-like formatting to HTML
    cleaned = cleaned.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
    cleaned = cleaned.replace(/`(.*?)`/g, '<code>$1</code>');

    // Handle code blocks
    cleaned = cleaned.replace(/```python\n([\s\S]*?)\n```/g, '<pre><code>$1</code></pre>');
    cleaned = cleaned.replace(/```\n([\s\S]*?)\n```/g, '<pre><code>$1</code></pre>');

    return cleaned;
}

function getSeverityIcon(severity) {
    const icons = {
        'high': '🔴',
        'medium': '🟠',
        'low': '🔵'
    };
    return icons[severity] || '⚪';
}

// Handle tab clicks
document.addEventListener('click', function(e) {
    if (e.target.classList.contains('tab-btn')) {
        const tabName = e.target.onclick.toString().match(/showTab\('(\w+)'\)/);
        if (tabName) {
            showTab(tabName[1], e);
        }
    }
});

// ---- Repo analysis helpers ----
async function analyzeRepoUrl(repoUrl) {
    const response = await fetch('/analyze_repo', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ repo_url: repoUrl })
    });
    return await response.json();
}

function displayRepoResults(data) {
    const repoContainer = document.getElementById('repo-container');
    const repoMeta = document.getElementById('repo-meta');
    const repoTree = document.getElementById('repo-tree');
    const repoExts = document.getElementById('repo-exts');
    const repoFiles = document.getElementById('repo-files');
    const repoFeedback = document.getElementById('repo-feedback');
    if (!repoContainer) {
        showError('UI not updated to display repository results.');
        return;
    }
    repoContainer.style.display = 'block';

    const analyzed = data.files_analyzed ?? 0;
    const considered = data.files_considered ?? 0;
    repoMeta.innerHTML = `
        <div><strong>Repository:</strong> ${data.repository}</div>
        <div><strong>Branch:</strong> ${data.branch}</div>
        <div><strong>Subdirectory:</strong> ${data.subdirectory || '(root)'}</div>
        <div><strong>Files analyzed:</strong> ${analyzed} / ${considered}</div>
    `;

    repoTree.textContent = data.structure_summary?.top_level_tree || '';

    const exts = data.structure_summary?.extension_counts || {};
    const extList = Object.entries(exts).slice(0, 20).map(([k, v]) => `${k}: ${v}`).join(' | ');
    repoExts.textContent = extList;

    // store for later selection
    __repoAnalysis = data;
    repoFiles.innerHTML = '';
    (data.results || []).forEach((item, idx) => {
        const li = document.createElement('li');
        const status = (item.status || '').toUpperCase();
        const err = item.error ? ` — ${item.error}` : '';
        li.textContent = `${status}: ${item.path}${err}`;
        li.dataset.idx = String(idx);
        li.className = 'repo-file';
        // Mark clickable only for reviewed items
        if (item.status === 'reviewed' && item.result) {
            li.classList.add('clickable');
            li.title = 'Click to view analysis in tabs';
        }
        repoFiles.appendChild(li);
    });

    const firstReviewed = (data.results || []).find(r => r.status === 'reviewed' && r.result);
    if (firstReviewed && firstReviewed.result) {
        renderFileResult(firstReviewed);
        repoFeedback.innerHTML = '';
    } else {
        ['security','maintainability','style'].forEach(id => {
            const el = document.getElementById(id);
            if (el) el.innerHTML = '<div class="issue"><p class="issue-description">No reviewed files to show.</p></div>';
        });
        repoFeedback.innerHTML = '<em>No reviewed files available. Check filters or increase max files.</em>';
    }

    // Render aggregate
    renderAggregate(data);
}

// Click handling for selecting a file to display
document.addEventListener('click', function(e) {
    const li = e.target.closest && e.target.closest('li.repo-file');
    if (!li) return;
    const idx = Number(li.dataset.idx || '-1');
    if (!__repoAnalysis || !Array.isArray(__repoAnalysis.results)) return;
    const item = __repoAnalysis.results[idx];
    if (item && item.status === 'reviewed' && item.result) {
        renderFileResult(item);
    }
});

function renderFileResult(item) {
    // Update tabs with this file's analysis
    displayResults(item.result);
    const repoFeedback = document.getElementById('repo-feedback');
    if (repoFeedback) {
        repoFeedback.innerHTML = `<strong>Showing:</strong> ${item.path}`;
    }
    // Ensure a tab is active
    showTab('security');
}

function renderAggregate(data) {
    const container = document.getElementById('aggregate');
    if (!container) return;
    const reviewed = (data.results || []).filter(r => r.status === 'reviewed' && r.result);
    if (reviewed.length === 0) {
        container.innerHTML = '<div class="issue"><p class="issue-description">No reviewed files to aggregate.</p></div>';
        return;
    }
    const rows = reviewed.map((r, idx) => {
        const ar = (r.result && r.result.analysis_results) || {};
        const c = (cat) => ((ar[cat] && Array.isArray(ar[cat].issues)) ? ar[cat].issues.length : 0);
        const sec = c('security');
        const main = c('maintainability');
        const sty = c('style');
        return `
        <tr>
            <td>${r.path}</td>
            <td>${sec}</td>
            <td>${main}</td>
            <td>${sty}</td>
            <td><button class="mini-btn" data-view-idx="${idx}">View</button></td>
        </tr>`;
    }).join('');
    container.innerHTML = `
        <div class="aggregate-table-wrapper">
            <table class="aggregate-table">
                <thead>
                    <tr><th>File</th><th>Security</th><th>Maintainability</th><th>Style</th><th></th></tr>
                </thead>
                <tbody>${rows}</tbody>
            </table>
        </div>`;
    // Wire up view buttons
    container.querySelectorAll('button[data-view-idx]').forEach(btn => {
        btn.addEventListener('click', () => {
            const idx = Number(btn.getAttribute('data-view-idx'));
            const reviewed = (data.results || []).filter(r => r.status === 'reviewed' && r.result);
            const item = reviewed[idx];
            if (item) renderFileResult(item);
        });
    });
}

// Download report button handler (top-level)
document.addEventListener('DOMContentLoaded', function() {
    const btn = document.getElementById('downloadReportBtn');
    if (!btn) return;
    btn.addEventListener('click', async function() {
        if (!__lastRepoUrl) {
            showError('No repository URL detected. Paste a GitHub repo URL and analyze first.');
            return;
        }
        try {
            const resp = await fetch('/analyze_repo_report', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ repo_url: __lastRepoUrl })
            });
            if (!resp.ok) {
                const err = await resp.json().catch(() => ({}));
                showError(err.error || ('Failed to download report: ' + resp.status));
                return;
            }
            const blob = await resp.blob();
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = 'code_review_report.md';
            document.body.appendChild(a);
            a.click();
            a.remove();
            window.URL.revokeObjectURL(url);
        } catch (e) {
            showError('Network error while downloading report: ' + e.message);
        }
    });
});
