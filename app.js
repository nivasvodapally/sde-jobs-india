let allJobs = [];
let currentFilter = 'all';

async function loadJobs() {
    try {
        const res = await fetch('jobs.json?t=' + Date.now());
        const data = await res.json();
        allJobs = data.jobs || [];
        document.getElementById('lastUpdated').textContent = 'Last updated: ' + (data.updated || 'Today');
        document.getElementById('jobCount').textContent = allJobs.length + ' jobs';
        renderJobs();
    } catch (e) {
        document.getElementById('loadingState').innerHTML = `
            <div style="text-align:center;padding:40px;color:var(--text-muted)">
                <p style="font-size:32px;margin-bottom:12px">⚠️</p>
                <p>Couldn't load jobs. Please try again later.</p>
            </div>
        `;
    }
}

function renderJobs() {
    const list = document.getElementById('jobsList');
    const empty = document.getElementById('emptyState');
    const loading = document.getElementById('loadingState');

    let filtered = [...allJobs];

    // Level filter
    if (currentFilter !== 'all') {
        filtered = filtered.filter(j => j.level === currentFilter);
    }

    // Search
    const q = document.getElementById('searchInput').value.toLowerCase().trim();
    if (q) {
        filtered = filtered.filter(j =>
            j.title.toLowerCase().includes(q) ||
            j.company.toLowerCase().includes(q) ||
            j.location.toLowerCase().includes(q) ||
            (j.tags && j.tags.some(t => t.toLowerCase().includes(q)))
        );
    }

    loading.style.display = 'none';

    if (filtered.length === 0) {
        list.innerHTML = '';
        empty.style.display = 'block';
        return;
    }

    empty.style.display = 'none';
    list.innerHTML = filtered.map(job => `
        <div class="job-card" onclick="window.open('${job.url}','_blank')">
            <div class="job-card-header">
                <div class="job-title">${job.title}</div>
            </div>
            <div class="job-company">${job.company}</div>
            <div class="job-tags">
                <span class="job-tag tag-location">📍 ${job.location}</span>
                <span class="job-tag tag-level">${getLevelLabel(job.level)}</span>
                <span class="job-tag tag-type">${job.type || 'Full-time'}</span>
                <span class="job-tag tag-source">${job.source || 'Web'}</span>
            </div>
            <div class="job-desc">${job.description || ''}</div>
            <div class="job-card-footer">
                <span class="job-posted">${job.posted || 'New'}</span>
                <a href="${job.url}" target="_blank" class="apply-btn">
                    Apply Now →
                </a>
            </div>
        </div>
    `).join('');
}

function getLevelLabel(level) {
    const labels = { 'entry': '🎯 Entry Level', 'mid': '📈 Mid Level', 'senior': '🚀 Senior' };
    return labels[level] || level;
}

function setFilter(filter) {
    currentFilter = filter;
    document.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
    document.querySelector(`[data-filter="${filter}"]`).classList.add('active');
    renderJobs();
}

function filterJobs() {
    renderJobs();
}

loadJobs();
