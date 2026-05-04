// ═══════════════════════════════════════════════════════════
//  SOCIAX SYNC — Dashboard JS
// ═══════════════════════════════════════════════════════════

// ── Toast Notification ──
// ── Toast Notification (Subtle alerts) ──
function showToast(message, type = 'success') {
    const Toast = Swal.mixin({
        toast: true,
        position: 'top-end',
        showConfirmButton: false,
        timer: 3000,
        timerProgressBar: true,
        background: '#1a1f33',
        color: '#ffffff',
        didOpen: (toast) => {
            toast.addEventListener('mouseenter', Swal.stopTimer)
            toast.addEventListener('mouseleave', Swal.resumeTimer)
        }
    });

    Toast.fire({
        icon: type,
        title: message
    });
}

// ── Loading Overlay ──
function showLoading(text = 'Processing…') {
    const overlay = document.getElementById('loading-overlay');
    document.getElementById('loading-text').textContent = text;
    overlay.classList.add('active');
}

function hideLoading() {
    document.getElementById('loading-overlay').classList.remove('active');
}

// ── Trigger Sync ──
function triggerSync() {
    showToast('🚀 Continuous sync starting...', 'info');
    
    fetch('/api/trigger-sync/', {
        method: 'POST',
        headers: {
            'X-CSRFToken': getCookie('csrftoken'),
            'Content-Type': 'application/json'
        }
    })
    .then(res => res.json())
    .then(data => {
        if (data.status === 'ok') {
            document.getElementById('btn-trigger-sync').style.display = 'none';
            document.getElementById('btn-stop-sync').style.display = 'inline-block';
            addLogEntry(`Sync started: Scraper will run continuously until stopped.`, 'success');
        } else {
            showToast('⚠️ Sync already running', 'warning');
        }
    })
    .catch(err => {
        showToast('❌ Sync failed: ' + err.message, 'error');
        addLogEntry('Sync failed: ' + err.message, 'error');
    });
}

// ── Stop Sync ──
function stopSync() {
    fetch('/api/stop-sync/', {
        method: 'POST',
        headers: {
            'X-CSRFToken': getCookie('csrftoken'),
            'Content-Type': 'application/json'
        }
    })
    .then(res => res.json())
    .then(data => {
        if (data.status === 'ok') {
            showToast('🛑 Stop signal sent', 'info');
            addLogEntry('Stop signal sent to engine...', 'warn');
        }
    });
}

// ── Delete Job ──
function deleteJob(jobId) {
    Swal.fire({
        title: 'Delete Job?',
        text: "This job will be permanently removed from your dashboard.",
        icon: 'warning',
        showCancelButton: true,
        confirmButtonColor: '#ef4444',
        cancelButtonColor: '#6b7280',
        confirmButtonText: 'Yes, delete it!',
        background: '#111827',
        color: '#fff'
    }).then((result) => {
        if (result.isConfirmed) {
            fetch(`/jobs/${jobId}/delete/`, {
                method: 'POST',
                headers: { 'X-CSRFToken': getCookie('csrftoken') }
            })
            .then(res => res.json())
            .then(data => {
                if (data.status === 'ok') {
                    showToast('🗑️ Job deleted', 'success');
                    const row = document.querySelector(`tr[data-job-id="${jobId}"]`);
                    if (row) row.remove();
                    else setTimeout(() => location.reload(), 500);
                }
            });
        }
    });
}

// ── Clear All Jobs ──
function clearAllJobs() {
    Swal.fire({
        title: 'Clear All Jobs?',
        text: "You are about to delete EVERY job from the database. This action is permanent!",
        icon: 'warning',
        showCancelButton: true,
        confirmButtonColor: '#dc2626',
        cancelButtonColor: '#6b7280',
        confirmButtonText: '🧹 Yes, clear everything!',
        background: '#111827',
        color: '#fff'
    }).then((result) => {
        if (result.isConfirmed) {
            showLoading('Clearing all jobs…');
            fetch('/api/clear-all/', {
                method: 'POST',
                headers: { 'X-CSRFToken': getCookie('csrftoken') }
            })
            .then(res => res.json())
            .then(data => {
                hideLoading();
                if (data.status === 'ok') {
                    Swal.fire({
                        title: 'Database Wiped!',
                        text: 'All jobs have been removed successfully.',
                        icon: 'success',
                        background: '#111827',
                        color: '#fff'
                    }).then(() => location.reload());
                }
            });
        }
    });
}

// ── Search ──
function handleNavbarSearch(event) {
    if (event) event.preventDefault();
    const query = document.getElementById('navbar-search-input').value;
    const params = new URLSearchParams(window.location.search);
    
    if (query) {
        params.set('q', query);
    } else {
        params.delete('q');
    }
    params.delete('page');
    
    window.location.href = '/jobs/?' + params.toString();
}



// ── Filters ──
function applyFilters() {
    const source = document.getElementById('filter-source')?.value || '';
    const visa = document.getElementById('filter-visa')?.value || '';
    const status = document.getElementById('filter-status')?.value || '';
    const search = document.getElementById('navbar-search-input')?.value || '';
    
    const params = new URLSearchParams();
    if (search) params.set('q', search);
    if (source) params.set('source', source);
    if (visa) params.set('visa', visa);
    if (status) params.set('status', status);
    
    window.location.href = window.location.pathname + '?' + params.toString();
}

// ── Log Entry ──
function addLogEntry(message, type = 'info') {
    const log = document.getElementById('sync-log');
    if (!log) return;
    
    const time = new Date().toLocaleTimeString();
    const colorClass = type === 'success' ? 'log-success' : type === 'error' ? 'log-error' : 'log-warn';
    
    const entry = document.createElement('div');
    entry.className = 'log-entry';
    entry.innerHTML = `<span class="log-time">[${time}]</span> <span class="${colorClass}">${message}</span>`;
    log.appendChild(entry);
    log.scrollTop = log.scrollHeight;
}

// ── CSRF Cookie ──
function getCookie(name) {
    let cookieValue = null;
    if (document.cookie && document.cookie !== '') {
        const cookies = document.cookie.split(';');
        for (let i = 0; i < cookies.length; i++) {
            const cookie = cookies[i].trim();
            if (cookie.substring(0, name.length + 1) === (name + '=')) {
                cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                break;
            }
        }
    }
    return cookieValue;
}

// ── Auto-refresh dashboard data every 3s ──
let lastJobId = null;

setInterval(() => {
    fetch('/api/status/')
        .then(r => r.json())
        .then(data => {
            const statusEl = document.getElementById('sync-status');
            const labelEl = document.getElementById('sync-label');
            const triggerBtn = document.getElementById('btn-trigger-sync');
            const stopBtn = document.getElementById('btn-stop-sync');
            
            // 1. Update Sync Status Indicator
            if (data.syncing) {
                if (statusEl) statusEl.className = 'sync-status running';
                if (labelEl) labelEl.textContent = 'Syncing...';
                if (triggerBtn) triggerBtn.style.display = 'none';
                if (stopBtn) stopBtn.style.display = 'inline-block';
            } else {
                if (statusEl) statusEl.className = 'sync-status idle';
                if (labelEl) labelEl.textContent = 'Idle';
                if (triggerBtn) triggerBtn.style.display = 'inline-block';
                if (stopBtn) stopBtn.style.display = 'none';
            }

            // 2. Update Stats Cards (Only on Dashboard)
            const statsMap = {
                'total_jobs': '.stat-card.accent .stat-value',
                'published_jobs': '.stat-card.green .stat-value',
                'reviewing_jobs': '.stat-card.amber .stat-value',
                'visa_jobs': '.stat-card.cyan .stat-value',
                'today_jobs': '.stat-card.purple .stat-value',
                'archived_jobs': '.stat-card.red .stat-value'
            };

            for (const [key, selector] of Object.entries(statsMap)) {
                const el = document.querySelector(selector);
                if (el) el.textContent = data[key];
            }

            // 3. Update Sync Log Time
            const syncTimeEl = document.getElementById('last-sync-time');
            if (syncTimeEl && data.last_sync) {
                syncTimeEl.textContent = `Last sync: ${data.last_sync}`;
            }

            // 4. Update Recent Jobs Table (Only on Dashboard)
            const tableBody = document.querySelector('.table-container table tbody');
            if (tableBody && data.recent_jobs && data.recent_jobs.length > 0) {
                const currentLastId = data.recent_jobs[0].id;
                
                // Only rewrite table if a NEW job has arrived
                if (currentLastId !== lastJobId) {
                    const rows = data.recent_jobs.map(job => `
                        <tr data-job-id="${job.id}">
                            <td>
                                <a href="${job.url}" style="text-decoration: none;">
                                    <div class="job-title-cell">
                                        ${job.company_logo ? 
                                            `<img src="${job.company_logo}" class="job-logo" alt="${job.company}" onerror="this.style.display='none'; this.nextElementSibling.style.display='flex';">
                                             <div class="job-logo-placeholder" style="display:none;">${job.company.charAt(0)}</div>` : 
                                            `<div class="job-logo-placeholder">${job.company.charAt(0)}</div>`
                                        }
                                        <div class="job-info">
                                            <span class="job-title">${job.title}</span>
                                            <span class="job-company">${job.company}</span>
                                        </div>
                                    </div>
                                </a>
                            </td>
                            <td><span class="badge badge-visa">${job.visa_type || '—'}</span></td>
                            <td class="truncate">${job.location}</td>
                            <td><span class="badge badge-source">${job.source}</span></td>
                            <td style="white-space: nowrap; font-size: 12px;">${job.posted_date}</td>
                            <td><a href="${job.external_apply_link}" target="_blank" class="apply-link">Apply →</a></td>
                            <td>
                                <button class="btn btn-sm btn-secondary" onclick="deleteJob(${job.id})" title="Delete Job">❌</button>
                            </td>
                        </tr>
                    `).join('');
                    
                    tableBody.innerHTML = rows;
                    lastJobId = currentLastId;
                    
                    if (data.syncing) {
                        addLogEntry(`New jobs found! Dashboard refreshed.`, 'success');
                    }
                }
            }
        })
        .catch(() => {});
}, 3000); 
