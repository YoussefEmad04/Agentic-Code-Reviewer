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

            // Display the results
            displayResults(data);

        } catch (error) {
            showError('Network error: ' + error.message);
            hideResults();
        }
    });
});

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

function showTab(tabName) {
    // Hide all tabs
    const tabContents = document.querySelectorAll('.tab-content');
    tabContents.forEach(tab => tab.classList.remove('active'));

    // Remove active class from all buttons
    const tabBtns = document.querySelectorAll('.tab-btn');
    tabBtns.forEach(btn => btn.classList.remove('active'));

    // Show selected tab
    document.getElementById(tabName).classList.add('active');

    // Add active class to clicked button
    event.target.classList.add('active');
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
            showTab(tabName[1]);
        }
    }
});
