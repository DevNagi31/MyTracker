// ── Auth ──
async function logout() {
    await fetch('/api/auth/logout', { method: 'POST' });
    window.location.href = '/login';
}

// ── State ──
let currentView = 'today';
let allGoals = [];
let calendarDate = new Date();
let selectedCalDate = null;
let journalDate = new Date();
let journalMood = 3;
let saveTimeout = null;
let subtasksTemp = [];
let atomicChart = null;
let categoryChart = null;

// ── Init ──
document.addEventListener('DOMContentLoaded', () => {
    document.getElementById('today-date').textContent = formatDateLong(new Date());
    document.getElementById('goal-date').value = todayStr();
    document.getElementById('journal-date-label').textContent = formatDateLong(journalDate);
    loadTheme();
    loadGoals();
    renderCalendar();
});

// ── Views ──
function switchView(view) {
    currentView = view;
    document.querySelectorAll('.view').forEach(v => v.classList.remove('active'));
    document.querySelectorAll('.nav-btn, .mobile-nav-btn').forEach(b => b.classList.remove('active'));
    document.getElementById(`view-${view}`).classList.add('active');
    document.querySelectorAll(`[data-view="${view}"]`).forEach(b => b.classList.add('active'));

    if (view === 'today') loadGoals();
    else if (view === 'all') loadAllGoals();
    else if (view === 'calendar') { renderCalendar(); loadCalendarGoals(); }
    else if (view === 'stats') loadStats();
    else if (view === 'journal') loadJournal();
    else if (view === 'agent') loadAgent();
    lucide.createIcons();
}

// ── API ──
async function loadGoals() {
    const res = await fetch('/api/goals');
    allGoals = await res.json();
    renderTodayGoals();
    loadOverdue();
    updateMiniStats();
}

async function loadAllGoals() {
    const res = await fetch('/api/goals');
    allGoals = await res.json();
    renderAllGoals();
    updateMiniStats();
}

async function loadOverdue() {
    const res = await fetch('/api/goals/overdue');
    const overdue = await res.json();
    const section = document.getElementById('overdue-section');
    if (overdue.length > 0) {
        section.style.display = 'block';
        renderGoalsList(overdue, 'overdue-goals');
    } else {
        section.style.display = 'none';
    }
}

async function loadCalendarGoals() {
    if (!selectedCalDate) {
        document.getElementById('calendar-goals').innerHTML =
            '<div class="empty-state"><p>Select a date to see goals</p></div>';
        return;
    }
    const res = await fetch(`/api/goals?date=${selectedCalDate}`);
    const goals = await res.json();
    renderGoalsList(goals, 'calendar-goals');
}

async function handleSearch(query) {
    if (!query.trim()) { renderTodayGoals(); return; }
    const res = await fetch(`/api/goals?q=${encodeURIComponent(query)}`);
    const goals = await res.json();
    renderGoalsList(goals, 'today-goals');
}

// ── Rendering ──
function renderTodayGoals() {
    const today = todayStr();
    const todayGoals = allGoals.filter(g => g.due_date === today);
    renderGoalsList(todayGoals, 'today-goals');
}

function renderAllGoals() {
    let filtered = [...allGoals];
    const cat = document.getElementById('filter-category').value;
    const status = document.getElementById('filter-status').value;
    const pri = document.getElementById('filter-priority').value;
    if (cat) filtered = filtered.filter(g => g.category === cat);
    if (status === 'completed') filtered = filtered.filter(g => g.completed);
    if (status === 'pending') filtered = filtered.filter(g => !g.completed);
    if (pri) filtered = filtered.filter(g => g.priority === pri);
    renderGoalsList(filtered, 'all-goals');
}

function renderGoalsList(goals, containerId) {
    const container = document.getElementById(containerId);
    if (goals.length === 0) {
        container.innerHTML = `
            <div class="empty-state">
                <div class="empty-icon"><i data-lucide="inbox" style="width:40px;height:40px"></i></div>
                <h3>No goals here yet</h3>
                <p>Click "Add Goal" to get started</p>
            </div>`;
        lucide.createIcons();
        return;
    }

    container.innerHTML = goals.map(g => {
        const pct = g.progress_target > 0 ? Math.round(g.progress / g.progress_target * 100) : 0;
        const subtasksHtml = (g.subtasks && g.subtasks.length > 0) ? `
            <div class="subtasks-inline">
                ${g.subtasks.map(s => `
                    <div class="subtask-item ${s.completed ? 'done' : ''}" onclick="toggleSubtask(${s.id}, event)">
                        <div class="subtask-check">${s.completed ? '<i data-lucide="check" style="width:9px;height:9px"></i>' : ''}</div>
                        <span>${escapeHtml(s.title)}</span>
                    </div>
                `).join('')}
            </div>` : '';

        return `
        <div class="goal-card ${g.completed ? 'completed' : ''}" data-id="${g.id}"
             draggable="true" ondragstart="dragStart(event)" ondragover="dragOver(event)"
             ondrop="drop(event)" ondragend="dragEnd(event)" ondragleave="dragLeave(event)">
            <div class="goal-check" onclick="toggleGoal(${g.id})">
                ${g.completed ? '<i data-lucide="check" style="width:12px;height:12px"></i>' : ''}
            </div>
            <div class="priority-dot ${g.priority}"></div>
            <div class="goal-info">
                <div class="goal-title">${escapeHtml(g.title)}</div>
                <div class="goal-meta">
                    <span class="goal-category">${g.category}</span>
                    ${g.due_date ? `<span class="meta-item"><i data-lucide="calendar" style="width:11px;height:11px"></i> ${formatDateShort(g.due_date)}</span>` : ''}
                    ${g.due_time ? `<span class="meta-item"><i data-lucide="clock" style="width:11px;height:11px"></i> ${formatTime(g.due_time)}</span>` : ''}
                    ${g.recurring !== 'none' ? `<span class="meta-item"><i data-lucide="repeat" style="width:11px;height:11px"></i> ${g.recurring}</span>` : ''}
                    ${g.reminder_enabled ? `<span class="meta-item"><i data-lucide="bell" style="width:11px;height:11px"></i></span>` : ''}
                </div>
                ${subtasksHtml}
            </div>
            ${!g.completed && g.progress_target > 0 ? `
                <div class="goal-progress"><div class="goal-progress-fill" style="width:${pct}%"></div></div>
                <span class="progress-text">${pct}%</span>
            ` : ''}
            <div class="goal-actions">
                ${!g.completed && g.progress_target > 0 ? `<button class="goal-action-btn" onclick="promptProgress(${g.id}, ${g.progress}, ${g.progress_target})" title="Update progress"><i data-lucide="trending-up" style="width:14px;height:14px"></i></button>` : ''}
                <button class="goal-action-btn" onclick="editGoal(${g.id})" title="Edit"><i data-lucide="pencil" style="width:14px;height:14px"></i></button>
                <button class="goal-action-btn" onclick="deleteGoal(${g.id})" title="Delete"><i data-lucide="trash-2" style="width:14px;height:14px"></i></button>
            </div>
        </div>`;
    }).join('');
    lucide.createIcons();
}

function updateMiniStats() {
    const total = allGoals.length;
    const done = allGoals.filter(g => g.completed).length;
    document.getElementById('stat-total').textContent = total;
    document.getElementById('stat-done').textContent = done;
    document.getElementById('stat-pending').textContent = total - done;
}

// ── Drag & Drop ──
let draggedId = null;
function dragStart(e) {
    draggedId = e.currentTarget.dataset.id;
    e.currentTarget.classList.add('dragging');
    e.dataTransfer.effectAllowed = 'move';
}
function dragOver(e) {
    e.preventDefault();
    e.currentTarget.classList.add('drag-over');
}
function dragLeave(e) { e.currentTarget.classList.remove('drag-over'); }
function dragEnd(e) { e.currentTarget.classList.remove('dragging'); }
function drop(e) {
    e.preventDefault();
    e.currentTarget.classList.remove('drag-over');
    const targetId = e.currentTarget.dataset.id;
    if (draggedId && draggedId !== targetId) {
        const ids = allGoals.map(g => String(g.id));
        const fromIdx = ids.indexOf(draggedId);
        const toIdx = ids.indexOf(targetId);
        ids.splice(fromIdx, 1);
        ids.splice(toIdx, 0, draggedId);
        fetch('/api/goals/reorder', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ ids: ids.map(Number) }),
        }).then(() => refreshCurrentView());
    }
}

// ── Calendar ──
function renderCalendar() {
    const grid = document.getElementById('calendar-grid');
    const year = calendarDate.getFullYear();
    const month = calendarDate.getMonth();
    document.getElementById('calendar-month-label').textContent =
        new Date(year, month).toLocaleDateString('en-US', { month: 'long', year: 'numeric' });

    const firstDay = new Date(year, month, 1).getDay();
    const daysInMonth = new Date(year, month + 1, 0).getDate();
    const today = new Date();

    fetch('/api/goals').then(r => r.json()).then(goals => {
        const goalDates = new Set(goals.map(g => g.due_date));
        let html = ['S','M','T','W','T','F','S'].map(d => `<div class="cal-header">${d}</div>`).join('');
        for (let i = 0; i < firstDay; i++) html += '<div class="cal-day"></div>';
        for (let day = 1; day <= daysInMonth; day++) {
            const ds = `${year}-${String(month+1).padStart(2,'0')}-${String(day).padStart(2,'0')}`;
            let cls = 'cal-day current-month';
            if (today.getFullYear()===year && today.getMonth()===month && today.getDate()===day) cls += ' today';
            if (selectedCalDate === ds) cls += ' selected';
            if (goalDates.has(ds)) cls += ' has-goals';
            html += `<div class="${cls}" onclick="selectCalDate('${ds}')">${day}</div>`;
        }
        grid.innerHTML = html;
    });
}

function changeMonth(d) { calendarDate.setMonth(calendarDate.getMonth()+d); renderCalendar(); }
function selectCalDate(ds) { selectedCalDate = ds; renderCalendar(); loadCalendarGoals(); }

// ── Stats ──
async function loadStats() {
    const res = await fetch('/api/stats');
    const s = await res.json();

    document.getElementById('sc-total').textContent = s.total;
    document.getElementById('sc-done').textContent = s.done;
    document.getElementById('sc-streak').textContent = s.streak;
    document.getElementById('sc-rate').textContent = s.total > 0 ? Math.round(s.done/s.total*100)+'%' : '0%';
    document.getElementById('streak-count').textContent = s.streak;

    // Atomic Habits Chart
    const ctx1 = document.getElementById('atomic-chart').getContext('2d');
    const labels = s.weeks.map(w => w.label);
    const actual = s.weeks.map(w => w.rate);
    // 1% compound: start at first week's rate (or 1), compound 1% daily (7% per week approx)
    const startVal = Math.max(actual[0] || 1, 1);
    const compound = [];
    for (let i = 0; i < s.weeks.length; i++) {
        compound.push(Math.min(Math.round(startVal * Math.pow(1.07, i)), 100));
    }

    const textColor = getComputedStyle(document.body).getPropertyValue('--text-secondary').trim();
    const gridColor = getComputedStyle(document.body).getPropertyValue('--chart-grid').trim();
    const lineColor = getComputedStyle(document.body).getPropertyValue('--chart-line').trim();

    if (atomicChart) atomicChart.destroy();
    atomicChart = new Chart(ctx1, {
        type: 'line',
        data: {
            labels,
            datasets: [
                {
                    label: 'Your Completion %',
                    data: actual,
                    borderColor: lineColor,
                    backgroundColor: 'transparent',
                    borderWidth: 2,
                    pointRadius: 4,
                    pointBackgroundColor: lineColor,
                    tension: 0.3,
                },
                {
                    label: '1% Daily Compound',
                    data: compound,
                    borderColor: textColor,
                    borderDash: [6, 4],
                    backgroundColor: 'transparent',
                    borderWidth: 1.5,
                    pointRadius: 0,
                    tension: 0.3,
                }
            ]
        },
        options: {
            responsive: true,
            plugins: {
                legend: { labels: { color: textColor, font: { size: 11 }, usePointStyle: true, pointStyle: 'line' } }
            },
            scales: {
                x: { ticks: { color: textColor, font: { size: 10 } }, grid: { color: gridColor } },
                y: { min: 0, max: 100, ticks: { color: textColor, font: { size: 10 }, callback: v => v+'%' }, grid: { color: gridColor } }
            }
        }
    });

    // Category Chart
    const ctx2 = document.getElementById('category-chart').getContext('2d');
    if (categoryChart) categoryChart.destroy();
    const catLabels = s.categories.map(c => c.category);
    const catTotal = s.categories.map(c => c.total);
    const catDone = s.categories.map(c => c.done || 0);

    categoryChart = new Chart(ctx2, {
        type: 'bar',
        data: {
            labels: catLabels,
            datasets: [
                { label: 'Total', data: catTotal, backgroundColor: lineColor, borderRadius: 4, barPercentage: 0.6 },
                { label: 'Done', data: catDone, backgroundColor: textColor, borderRadius: 4, barPercentage: 0.6 }
            ]
        },
        options: {
            responsive: true,
            plugins: { legend: { labels: { color: textColor, font: { size: 11 }, usePointStyle: true } } },
            scales: {
                x: { ticks: { color: textColor, font: { size: 10 } }, grid: { display: false } },
                y: { ticks: { color: textColor, font: { size: 10 }, stepSize: 1 }, grid: { color: gridColor } }
            }
        }
    });

    // Heatmap
    renderHeatmap(s.heatmap);
    lucide.createIcons();
}

function renderHeatmap(data) {
    const container = document.getElementById('heatmap');
    const map = {};
    data.forEach(d => { map[d.date] = d.count; });

    const today = new Date();
    const start = new Date(today);
    start.setDate(start.getDate() - 364);
    // Align to Sunday
    start.setDate(start.getDate() - start.getDay());

    let html = '';
    let current = new Date(start);
    while (current <= today) {
        html += '<div class="heatmap-week">';
        for (let d = 0; d < 7; d++) {
            const ds = current.toISOString().slice(0, 10);
            const count = map[ds] || 0;
            let level = 0;
            if (count === 1) level = 1;
            else if (count === 2) level = 2;
            else if (count <= 4) level = 3;
            else if (count > 4) level = 4;
            html += `<div class="heatmap-cell hm-${level}" title="${ds}: ${count} completed"></div>`;
            current.setDate(current.getDate() + 1);
        }
        html += '</div>';
    }
    container.innerHTML = html;
}

// ── Journal ──
async function loadJournal() {
    const ds = journalDate.toISOString().slice(0, 10);
    document.getElementById('journal-date-label').textContent = formatDateLong(journalDate);

    const res = await fetch(`/api/notes?date=${ds}`);
    const note = await res.json();
    document.getElementById('journal-content').value = note.content || '';
    setMood(note.mood || 3);

    // Load today's goals in journal
    const gres = await fetch(`/api/goals?date=${ds}`);
    const goals = await gres.json();
    renderGoalsList(goals, 'journal-goals-list');
}

function changeJournalDate(delta) {
    journalDate.setDate(journalDate.getDate() + delta);
    loadJournal();
}

function setMood(m) {
    journalMood = m;
    document.querySelectorAll('.mood-btn').forEach(b => {
        b.classList.toggle('active', parseInt(b.dataset.mood) === m);
    });
    autoSaveNote();
}

function autoSaveNote() {
    document.getElementById('save-status').textContent = 'Saving...';
    clearTimeout(saveTimeout);
    saveTimeout = setTimeout(async () => {
        const ds = journalDate.toISOString().slice(0, 10);
        await fetch('/api/notes', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ date: ds, content: document.getElementById('journal-content').value, mood: journalMood }),
        });
        document.getElementById('save-status').textContent = 'Saved';
    }, 800);
}

// ── AI Agent ──
async function loadAgent() {
    const container = document.getElementById('agent-container');
    container.innerHTML = '<div class="empty-state"><p>Thinking...</p></div>';
    const res = await fetch('/api/agent');
    const insights = await res.json();

    container.innerHTML = insights.map(i => `
        <div class="agent-card ${i.type}">
            <div class="agent-icon"><i data-lucide="${i.icon}" style="width:18px;height:18px"></i></div>
            <div class="agent-message">${escapeHtml(i.message)}</div>
        </div>
    `).join('');
    lucide.createIcons();
}

// ── Modal ──
function openModal(goalId = null) {
    subtasksTemp = [];
    const form = document.getElementById('goal-form');
    form.reset();
    document.getElementById('goal-id').value = '';
    document.getElementById('goal-date').value = selectedCalDate || todayStr();
    document.getElementById('goal-reminder').checked = true;
    document.getElementById('goal-progress-target').value = 100;
    renderSubtasksInput();

    if (goalId) {
        const g = allGoals.find(x => x.id === goalId);
        if (g) {
            document.getElementById('modal-title').textContent = 'Edit Goal';
            document.getElementById('goal-id').value = g.id;
            document.getElementById('goal-title').value = g.title;
            document.getElementById('goal-desc').value = g.description || '';
            document.getElementById('goal-category').value = g.category;
            document.getElementById('goal-priority').value = g.priority;
            document.getElementById('goal-date').value = g.due_date || '';
            document.getElementById('goal-time').value = g.due_time || '';
            document.getElementById('goal-recurring').value = g.recurring || 'none';
            document.getElementById('goal-progress-target').value = g.progress_target;
            document.getElementById('goal-reminder').checked = g.reminder_enabled;
            document.getElementById('goal-email').value = g.reminder_email || '';
            subtasksTemp = (g.subtasks || []).map(s => s.title);
            renderSubtasksInput();
        }
    } else {
        document.getElementById('modal-title').textContent = 'Add New Goal';
    }

    document.getElementById('modal-overlay').classList.add('open');
    setTimeout(() => document.getElementById('goal-title').focus(), 100);
    lucide.createIcons();
}

function closeModal() { document.getElementById('modal-overlay').classList.remove('open'); }

function addSubtaskInput() {
    const input = document.getElementById('subtask-input');
    if (input.value.trim()) {
        subtasksTemp.push(input.value.trim());
        input.value = '';
        renderSubtasksInput();
    }
}

function removeSubtaskInput(idx) {
    subtasksTemp.splice(idx, 1);
    renderSubtasksInput();
}

function renderSubtasksInput() {
    const list = document.getElementById('subtasks-list');
    list.innerHTML = subtasksTemp.map((s, i) => `
        <div class="subtask-input-item">
            <span style="flex:1">${escapeHtml(s)}</span>
            <button type="button" onclick="removeSubtaskInput(${i})"><i data-lucide="x" style="width:12px;height:12px"></i></button>
        </div>
    `).join('');
    lucide.createIcons();
}

async function saveGoal(e) {
    e.preventDefault();
    const id = document.getElementById('goal-id').value;
    const data = {
        title: document.getElementById('goal-title').value.trim(),
        description: document.getElementById('goal-desc').value.trim(),
        category: document.getElementById('goal-category').value,
        priority: document.getElementById('goal-priority').value,
        due_date: document.getElementById('goal-date').value,
        due_time: document.getElementById('goal-time').value,
        recurring: document.getElementById('goal-recurring').value,
        progress_target: parseInt(document.getElementById('goal-progress-target').value) || 100,
        reminder_enabled: document.getElementById('goal-reminder').checked,
        reminder_email: document.getElementById('goal-email').value.trim(),
        subtasks: subtasksTemp,
    };
    if (!data.title) return;

    if (id) {
        await fetch(`/api/goals/${id}`, { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(data) });
        showToast('Goal updated');
    } else {
        await fetch('/api/goals', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(data) });
        showToast('Goal added');
    }
    closeModal();
    refreshCurrentView();
}

// ── Actions ──
async function toggleGoal(id) {
    await fetch(`/api/goals/${id}/toggle`, { method: 'POST' });
    refreshCurrentView();
}

async function toggleSubtask(id, e) {
    e.stopPropagation();
    await fetch(`/api/subtasks/${id}/toggle`, { method: 'POST' });
    refreshCurrentView();
}

function editGoal(id) { openModal(id); }

async function deleteGoal(id) {
    if (!confirm('Delete this goal?')) return;
    await fetch(`/api/goals/${id}`, { method: 'DELETE' });
    showToast('Goal deleted');
    refreshCurrentView();
}

function promptProgress(id, current, target) {
    const val = prompt(`Update progress (0-${target}):`, current);
    if (val !== null) {
        const n = parseInt(val);
        if (!isNaN(n) && n >= 0 && n <= target) {
            fetch(`/api/goals/${id}/progress`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ progress: n }),
            }).then(() => refreshCurrentView());
        }
    }
}

async function testNotification() {
    const res = await fetch('/api/test-notification', { method: 'POST' });
    const data = await res.json();
    showToast(data.success ? 'Notification sent — check your screen' : 'Failed — check permissions', data.success ? 'success' : 'error');
}

function refreshCurrentView() {
    if (currentView === 'today') loadGoals();
    else if (currentView === 'all') loadAllGoals();
    else if (currentView === 'calendar') { renderCalendar(); loadCalendarGoals(); }
    else if (currentView === 'stats') loadStats();
    else if (currentView === 'journal') loadJournal();
}

// ── Theme ──
function setTheme(theme) {
    document.body.dataset.theme = theme;
    localStorage.setItem('mytracker-theme', theme);
    document.getElementById('theme-dark').classList.toggle('active', theme === 'dark');
    document.getElementById('theme-light').classList.toggle('active', theme === 'light');
    // Refresh charts if on stats view
    if (currentView === 'stats') loadStats();
}

function loadTheme() {
    const saved = localStorage.getItem('mytracker-theme') || 'dark';
    setTheme(saved);
}

// ── Helpers ──
function todayStr() {
    const d = new Date();
    return `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,'0')}-${String(d.getDate()).padStart(2,'0')}`;
}
function formatDateLong(d) {
    return d.toLocaleDateString('en-US', { weekday: 'long', month: 'long', day: 'numeric', year: 'numeric' });
}
function formatDateShort(s) {
    const d = new Date(s + 'T00:00:00');
    return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
}
function formatTime(t) {
    const [h, m] = t.split(':');
    const hr = parseInt(h);
    return `${hr % 12 || 12}:${m} ${hr >= 12 ? 'PM' : 'AM'}`;
}
function escapeHtml(s) {
    const d = document.createElement('div');
    d.textContent = s;
    return d.innerHTML;
}
function showToast(msg, type = 'success') {
    const existing = document.querySelector('.toast');
    if (existing) existing.remove();
    const t = document.createElement('div');
    t.className = `toast ${type}`;
    t.textContent = msg;
    document.body.appendChild(t);
    setTimeout(() => t.remove(), 3000);
}

// ── Keyboard ──
document.addEventListener('keydown', e => {
    if (e.key === 'Escape') closeModal();
    if (e.key === 'n' && !e.ctrlKey && !e.metaKey && !document.querySelector('.modal-overlay.open') &&
        !['INPUT','TEXTAREA','SELECT'].includes(document.activeElement.tagName)) {
        openModal();
    }
});

// Enter key for subtask input
document.addEventListener('keydown', e => {
    if (e.target.id === 'subtask-input' && e.key === 'Enter') {
        e.preventDefault();
        addSubtaskInput();
    }
});
