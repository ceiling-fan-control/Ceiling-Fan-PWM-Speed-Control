// --- State Management ---
let config = {};
let status = {};
let activeFanId = null;
let editorMode = 'curve'; // 'curve' or 'manual'

// Canvas variables
let canvas, ctx;
const margin = { top: 20, right: 20, bottom: 40, left: 50 };
let curvePoints = []; // Current editing points: [{x: temp_c, y: pwm_pct}, ...]
let draggedPointIndex = -1;
const hitRadius = 8;

// --- DOM Elements ---
document.addEventListener('DOMContentLoaded', () => {
    canvas = document.getElementById('curve-canvas');
    ctx = canvas.getContext('2d');
    
    // Initial fetches
    fetchConfig().then(() => {
        // Set first fan as active by default
        const fanIds = Object.keys(config.fans || {});
        if (fanIds.length > 0) {
            selectFan(fanIds[0]);
        }
        
        // Start polling status
        fetchStatus();
        setInterval(fetchStatus, 1000);
    });

    // Profile selector event
    document.getElementById('active-profile-select').addEventListener('change', (e) => {
        changeProfile(e.target.value);
    });

    // Manual slider event
    const slider = document.getElementById('manual-pwm-slider');
    const sliderVal = document.getElementById('manual-pwm-val');
    slider.addEventListener('input', (e) => {
        sliderVal.textContent = e.target.value + '%';
    });

    // Add point button event
    document.getElementById('add-point-btn').addEventListener('click', () => {
        addNewPoint();
    });

    // Setup Canvas Drag and Drop Listeners
    setupCanvasEvents();
});

// --- API Interactions ---
async function fetchConfig() {
    try {
        const res = await fetch('/api/config');
        config = await res.json();
        
        // Update profile select dropdown
        const select = document.getElementById('active-profile-select');
        select.value = config.active_profile;
        
        // Build editor tabs
        buildFanTabs();
    } catch (e) {
        showToast('Error loading configuration', 'error');
        console.error(e);
    }
}

async function fetchStatus() {
    try {
        const res = await fetch('/api/status');
        status = await res.json();
        
        updateSystemStatus();
    } catch (e) {
        document.getElementById('daemon-status').innerHTML = `
            <span class="pulse-indicator red"></span>
            <span class="status-text">Daemon Disconnected</span>
        `;
        console.error("Error reading daemon status:", e);
    }
}

async function changeProfile(profileName) {
    try {
        const res = await fetch('/api/select-profile', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ profile: profileName })
        });
        const data = await res.json();
        if (data.success) {
            showToast(`Profile changed to: ${profileName}`);
            await fetchConfig();
            if (activeFanId) loadFanConfigIntoEditor(activeFanId);
        } else {
            showToast(`Failed to change profile: ${data.error}`, 'error');
        }
    } catch (e) {
        showToast('Network error updating profile', 'error');
    }
}

async function saveEditorSettings() {
    if (!activeFanId) return;

    const payload = {
        fan_id: activeFanId,
        mode: editorMode
    };

    if (editorMode === 'manual') {
        payload.manual_value = parseInt(document.getElementById('manual-pwm-slider').value);
    } else {
        const tempSource = document.getElementById('temp-source-select').value.split(':');
        payload.temp_device_name = tempSource[0];
        payload.temp_channel = parseInt(tempSource[1]);
        
        // Sort points by temperature before saving
        curvePoints.sort((a, b) => a.x - b.x);
        payload.curve = curvePoints.map(p => [Math.round(p.x), Math.round(p.y)]);
    }

    try {
        const res = await fetch('/api/save-fan-curve', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        const data = await res.json();
        if (data.success) {
            showToast('Settings saved successfully!');
            await fetchConfig();
        } else {
            showToast(`Failed to save: ${data.error}`, 'error');
        }
    } catch (e) {
        showToast('Network error saving configuration', 'error');
    }
}

// --- UI Rendering ---

function buildFanTabs() {
    const tabsContainer = document.getElementById('editor-fan-tabs');
    tabsContainer.innerHTML = '';

    Object.entries(config.fans || {}).forEach(([id, fan]) => {
        const btn = document.createElement('button');
        btn.className = `tab-btn ${id === activeFanId ? 'active' : ''}`;
        btn.textContent = fan.label;
        btn.onclick = () => selectFan(id);
        tabsContainer.appendChild(btn);
    });
}

function selectFan(fanId) {
    activeFanId = fanId;
    
    // Update active tab styling
    document.querySelectorAll('.tab-btn').forEach(btn => {
        if (btn.textContent === config.fans[fanId].label) {
            btn.classList.add('active');
        } else {
            btn.classList.remove('active');
        }
    });

    document.getElementById('editor-active-fan-name').textContent = config.fans[fanId].label;

    // Highlight card in overview
    document.querySelectorAll('.fan-card').forEach(card => {
        if (card.dataset.fanId === fanId) {
            card.classList.add('active-editing');
        } else {
            card.classList.remove('active-editing');
        }
    });

    loadFanConfigIntoEditor(fanId);
}

function loadFanConfigIntoEditor(fanId) {
    const activeProfName = config.active_profile;
    const fanProf = config.profiles[activeProfName]?.[fanId];
    if (!fanProf) return;

    setEditorMode(fanProf.mode);

    if (fanProf.mode === 'manual') {
        const val = fanProf.manual_value || 50;
        document.getElementById('manual-pwm-slider').value = val;
        document.getElementById('manual-pwm-val').textContent = val + '%';
    } else {
        const tempSource = `${fanProf.temp_device_name}:${fanProf.temp_channel}`;
        document.getElementById('temp-source-select').value = tempSource;
        
        // Parse curve points
        curvePoints = (fanProf.curve || []).map(pt => ({ x: pt[0], y: pt[1] }));
        curvePoints.sort((a, b) => a.x - b.x);
        
        drawCurve();
        renderPointsTable();
    }
}

function setEditorMode(mode) {
    editorMode = mode;
    
    const curveBtn = document.getElementById('mode-curve-btn');
    const manualBtn = document.getElementById('mode-manual-btn');
    const curveSection = document.getElementById('curve-speed-section');
    const manualSection = document.getElementById('manual-speed-section');

    if (mode === 'curve') {
        curveBtn.classList.add('active');
        manualBtn.classList.remove('active');
        curveSection.classList.remove('hidden');
        manualSection.classList.add('hidden');
        setTimeout(drawCurve, 50); // Small timeout to ensure canvas is visible & size is calculated
    } else {
        curveBtn.classList.remove('active');
        manualBtn.classList.add('active');
        curveSection.classList.add('hidden');
        manualSection.classList.remove('hidden');
    }
}

function updateSystemStatus() {
    // 1. Connection indicator
    document.getElementById('daemon-status').innerHTML = `
        <span class="pulse-indicator green"></span>
        <span class="status-text">Daemon Connected</span>
    `;

    // 2. Render temperatures
    const temps = status.temperatures || {};
    
    // CPU Temp (k10temp)
    const cpuT = temps["k10temp_temp1"];
    if (cpuT !== undefined) {
        document.getElementById('temp-cpu-val').textContent = cpuT.toFixed(1);
        document.getElementById('temp-cpu-bar').style.width = Math.min(100, Math.max(0, (cpuT / 95) * 100)) + '%';
    }
    
    // Coolant Temp (kraken2023)
    const coolantT = temps["kraken2023_temp1"];
    if (coolantT !== undefined) {
        document.getElementById('temp-coolant-val').textContent = coolantT.toFixed(1);
        document.getElementById('temp-coolant-bar').style.width = Math.min(100, Math.max(0, (coolantT / 60) * 100)) + '%';
    }

    // GPU Temp (amdgpu)
    const gpuT = temps["amdgpu_temp1"];
    if (gpuT !== undefined) {
        document.getElementById('temp-gpu-val').textContent = gpuT.toFixed(1);
        document.getElementById('temp-gpu-bar').style.width = Math.min(100, Math.max(0, (gpuT / 90) * 100)) + '%';
    }

    // 3. Render fan status grid
    const fansContainer = document.getElementById('fans-container');
    fansContainer.innerHTML = '';

    Object.entries(status.fans || {}).forEach(([id, fan]) => {
        const isEditing = id === activeFanId;
        const card = document.createElement('div');
        card.className = `glass-card fan-card ${isEditing ? 'active-editing' : ''} ${fan.is_identifying ? 'identifying' : ''}`;
        card.dataset.fanId = id;
        card.onclick = () => selectFan(id);

        // Spin animation calculation
        let spinDuration = '0s';
        if (fan.rpm > 0) {
            // Formula limits rotation to a visual speed: 500 RPM -> 3s, 1000 RPM -> 1.5s, 2000 RPM -> 0.75s
            const dur = Math.max(0.4, 3.0 / (fan.rpm / 500));
            spinDuration = `${dur.toFixed(2)}s`;
        }

        // Inline Fan SVG
        const fanSvg = `
            <svg class="fan-spinner" viewBox="0 0 100 100" style="animation: spin ${spinDuration} linear infinite; ${fan.rpm === 0 ? 'animation: none;' : ''}">
                <circle cx="50" cy="50" r="8" fill="currentColor"></circle>
                <!-- Blade 1 -->
                <path d="M50 42 C40 30 35 15 50 15 C65 15 60 30 50 42 Z" fill="currentColor" opacity="0.85"></path>
                <!-- Blade 2 -->
                <path d="M58 50 C70 40 85 35 85 50 C85 65 70 60 58 50 Z" fill="currentColor" opacity="0.85"></path>
                <!-- Blade 3 -->
                <path d="M50 58 C60 70 65 85 50 85 C35 85 40 70 50 58 Z" fill="currentColor" opacity="0.85"></path>
                <!-- Blade 4 -->
                <path d="M42 50 C30 60 15 65 15 50 C15 35 30 40 42 50 Z" fill="currentColor" opacity="0.85"></path>
            </svg>
        `;

        card.innerHTML = `
            <div class="fan-card-info">
                <div class="fan-icon-wrapper">
                    ${fanSvg}
                </div>
                <div class="fan-details">
                    <h3>${fan.label}</h3>
                    <div class="metadata">PWM Channel: ${fan.pwm_channel} | HW: ${fan.device_name}</div>
                    ${fan.error ? `<span class="error-tag">⚠️ ${fan.error}</span>` : ''}
                    <div class="fan-actions">
                        <button class="btn-identify ${fan.is_identifying ? 'active' : ''}" onclick="toggleIdentifyFan(event, '${id}', ${!fan.is_identifying})">
                            🎯 ${fan.is_identifying ? 'Stop Finder' : 'Identify Fan'}
                        </button>
                    </div>
                </div>
            </div>
            <div class="fan-metrics">
                <div class="metric">
                    <span class="m-label">Actual RPM</span>
                    <span class="m-value rpm">${fan.rpm} <span style="font-size: 0.75rem; font-weight: 500;">RPM</span></span>
                </div>
                <div class="metric">
                    <span class="m-label">Duty Cycle</span>
                    <span class="m-value pwm">${fan.target_pwm}%</span>
                    <span class="m-mode ${fan.mode === 'curve' ? 'auto' : 'manual'}">${fan.mode}</span>
                </div>
            </div>
        `;
        
        fansContainer.appendChild(card);
    });

    // Draw red line indicating current sensor temperature on canvas
    if (editorMode === 'curve' && activeFanId) {
        drawCurve(); // Redraw curve to overlay current temp line
    }
}

// --- Canvas Plotter Logic ---

function getCanvasCoordinates(point) {
    const width = canvas.width - margin.left - margin.right;
    const height = canvas.height - margin.top - margin.bottom;
    
    // x mapping: 0 to 100°C -> margin.left to canvas.width - margin.right
    // y mapping: 0 to 100% PWM -> canvas.height - margin.bottom to margin.top
    const px = margin.left + (point.x / 100) * width;
    const py = canvas.height - margin.bottom - (point.y / 100) * height;
    
    return { x: px, y: py };
}

function getValuesFromCoordinates(px, py) {
    const width = canvas.width - margin.left - margin.right;
    const height = canvas.height - margin.top - margin.bottom;
    
    let vx = ((px - margin.left) / width) * 100;
    let vy = ((canvas.height - margin.bottom - py) / height) * 100;
    
    // Bounds check
    vx = Math.max(0, Math.min(100, vx));
    vy = Math.max(0, Math.min(100, vy));
    
    return { x: vx, y: vy };
}

function drawCurve() {
    // Update canvas scale depending on CSS layout (responsive scale)
    const rect = canvas.getBoundingClientRect();
    canvas.width = rect.width;
    canvas.height = rect.height;

    ctx.clearRect(0, 0, canvas.width, canvas.height);
    
    const width = canvas.width - margin.left - margin.right;
    const height = canvas.height - margin.top - margin.bottom;

    // 1. Draw Grid Lines
    ctx.strokeStyle = 'rgba(255, 255, 255, 0.04)';
    ctx.lineWidth = 1;
    ctx.font = '10px Outfit';
    ctx.fillStyle = '#8b95b3';
    
    // Vertical grid lines (every 10°C)
    for (let t = 0; t <= 100; t += 10) {
        const pt = getCanvasCoordinates({ x: t, y: 0 });
        ctx.beginPath();
        ctx.moveTo(pt.x, margin.top);
        ctx.lineTo(pt.x, canvas.height - margin.bottom);
        ctx.stroke();
        
        // Draw tick label
        ctx.fillText(t + '°', pt.x - 7, canvas.height - margin.bottom + 18);
    }
    
    // Horizontal grid lines (every 10%)
    for (let p = 0; p <= 100; p += 10) {
        const pt = getCanvasCoordinates({ x: 0, y: p });
        ctx.beginPath();
        ctx.moveTo(margin.left, pt.y);
        ctx.lineTo(canvas.width - margin.right, pt.y);
        ctx.stroke();
        
        // Draw tick label
        ctx.fillText(p + '%', margin.left - 30, pt.y + 3);
    }

    // Axes Labels
    ctx.fillStyle = '#f1f3f9';
    ctx.font = '11px Outfit';
    ctx.fillText('Temperature (°C)', margin.left + width / 2 - 40, canvas.height - 10);
    
    ctx.save();
    ctx.translate(15, margin.top + height / 2 + 30);
    ctx.rotate(-Math.PI / 2);
    ctx.fillText('Fan Speed / PWM (%)', 0, 0);
    ctx.restore();

    if (curvePoints.length === 0) return;

    // 2. Draw Curve Connection Line
    ctx.beginPath();
    let startPt = getCanvasCoordinates(curvePoints[0]);
    ctx.moveTo(startPt.x, startPt.y);
    
    for (let i = 1; i < curvePoints.length; i++) {
        let pt = getCanvasCoordinates(curvePoints[i]);
        ctx.lineTo(pt.x, pt.y);
    }
    
    ctx.strokeStyle = '#00f2fe';
    ctx.lineWidth = 3;
    ctx.shadowColor = 'rgba(0, 242, 254, 0.4)';
    ctx.shadowBlur = 8;
    ctx.stroke();
    ctx.shadowBlur = 0; // Reset shadow

    // 3. Draw Nodes (Points)
    curvePoints.forEach((point, idx) => {
        const pt = getCanvasCoordinates(point);
        ctx.beginPath();
        ctx.arc(pt.x, pt.y, 6, 0, 2 * Math.PI);
        
        if (idx === draggedPointIndex) {
            ctx.fillStyle = '#e100ff';
            ctx.strokeStyle = '#fff';
            ctx.lineWidth = 2;
        } else {
            ctx.fillStyle = '#00ff87';
            ctx.strokeStyle = '#00f2fe';
            ctx.lineWidth = 1.5;
        }
        
        ctx.fill();
        ctx.stroke();
    });

    // 4. Overlay Current Temperature indicator line
    const activeProfName = config.active_profile;
    const fanProf = config.profiles[activeProfName]?.[activeFanId];
    if (fanProf && status.temperatures) {
        const tempKey = `${fanProf.temp_device_name}_temp${fanProf.temp_channel}`;
        const currentTemp = status.temperatures[tempKey];
        if (currentTemp !== undefined) {
            const pt = getCanvasCoordinates({ x: currentTemp, y: 0 });
            
            // Draw dotted line
            ctx.beginPath();
            ctx.setLineDash([4, 4]);
            ctx.moveTo(pt.x, margin.top);
            ctx.lineTo(pt.x, canvas.height - margin.bottom);
            ctx.strokeStyle = '#ff416c';
            ctx.lineWidth = 1.5;
            ctx.stroke();
            ctx.setLineDash([]); // Reset dash

            // Draw temperature label pill on top
            ctx.fillStyle = '#ff416c';
            ctx.fillRect(pt.x - 22, margin.top - 12, 44, 16);
            ctx.fillStyle = '#fff';
            ctx.font = 'bold 9px Outfit';
            ctx.fillText(currentTemp.toFixed(0) + '°C', pt.x - 14, margin.top);
        }
    }
}

function setupCanvasEvents() {
    canvas.addEventListener('mousedown', (e) => {
        const rect = canvas.getBoundingClientRect();
        const mouseX = e.clientX - rect.left;
        const mouseY = e.clientY - rect.top;

        // Check if clicked near a point
        draggedPointIndex = -1;
        for (let i = 0; i < curvePoints.length; i++) {
            const pt = getCanvasCoordinates(curvePoints[i]);
            const dist = Math.hypot(pt.x - mouseX, pt.y - mouseY);
            if (dist <= hitRadius) {
                draggedPointIndex = i;
                drawCurve();
                break;
            }
        }
    });

    canvas.addEventListener('mousemove', (e) => {
        if (draggedPointIndex === -1) return;
        
        const rect = canvas.getBoundingClientRect();
        const mouseX = e.clientX - rect.left;
        const mouseY = e.clientY - rect.top;

        const val = getValuesFromCoordinates(mouseX, mouseY);
        
        // Constrain movement: can't drag past neighboring points on X axis
        let minX = 0;
        let maxX = 100;
        
        if (draggedPointIndex > 0) {
            minX = curvePoints[draggedPointIndex - 1].x + 1; // At least 1°C apart
        }
        if (draggedPointIndex < curvePoints.length - 1) {
            maxX = curvePoints[draggedPointIndex + 1].x - 1;
        }

        curvePoints[draggedPointIndex].x = Math.max(minX, Math.min(maxX, val.x));
        curvePoints[draggedPointIndex].y = val.y;

        drawCurve();
        renderPointsTable();
    });

    canvas.addEventListener('mouseup', () => {
        if (draggedPointIndex !== -1) {
            draggedPointIndex = -1;
            drawCurve();
        }
    });

    canvas.addEventListener('mouseleave', () => {
        if (draggedPointIndex !== -1) {
            draggedPointIndex = -1;
            drawCurve();
        }
    });

    // Double-click to add a new point
    canvas.addEventListener('dblclick', (e) => {
        const rect = canvas.getBoundingClientRect();
        const mouseX = e.clientX - rect.left;
        const mouseY = e.clientY - rect.top;
        
        const val = getValuesFromCoordinates(mouseX, mouseY);
        
        // Add new point and sort
        curvePoints.push({ x: val.x, y: val.y });
        curvePoints.sort((a, b) => a.x - b.x);
        
        drawCurve();
        renderPointsTable();
    });

    // Right-click to remove point
    canvas.addEventListener('contextmenu', (e) => {
        e.preventDefault();
        
        const rect = canvas.getBoundingClientRect();
        const mouseX = e.clientX - rect.left;
        const mouseY = e.clientY - rect.top;

        // Check if clicked near a point
        let deleteIdx = -1;
        for (let i = 0; i < curvePoints.length; i++) {
            const pt = getCanvasCoordinates(curvePoints[i]);
            const dist = Math.hypot(pt.x - mouseX, pt.y - mouseY);
            if (dist <= hitRadius) {
                deleteIdx = i;
                break;
            }
        }

        // Must preserve at least 2 points for a valid curve line
        if (deleteIdx !== -1 && curvePoints.length > 2) {
            curvePoints.splice(deleteIdx, 1);
            drawCurve();
            renderPointsTable();
        } else if (deleteIdx !== -1) {
            showToast('A curve must have at least 2 coordinate points', 'error');
        }
    });
}

function renderPointsTable() {
    const tbody = document.getElementById('curve-points-tbody');
    tbody.innerHTML = '';

    curvePoints.forEach((pt, idx) => {
        const row = document.createElement('tr');
        row.innerHTML = `
            <td>
                <input type="number" min="0" max="100" class="point-input" value="${Math.round(pt.x)}" onchange="updatePointValue(${idx}, 'x', this.value)">
            </td>
            <td>
                <input type="number" min="0" max="100" class="point-input" value="${Math.round(pt.y)}" onchange="updatePointValue(${idx}, 'y', this.value)">
            </td>
            <td>
                <button type="button" class="glass-btn btn-sm btn-danger" onclick="deletePoint(${idx})">Delete</button>
            </td>
        `;
        tbody.appendChild(row);
    });
}

function updatePointValue(index, field, value) {
    let numVal = parseInt(value);
    if (isNaN(numVal)) return;
    numVal = Math.max(0, Math.min(100, numVal));
    
    curvePoints[index][field] = numVal;
    
    // Sort table array if temperature (x) was edited
    if (field === 'x') {
        curvePoints.sort((a, b) => a.x - b.x);
    }
    
    drawCurve();
    renderPointsTable();
}

function deletePoint(index) {
    if (curvePoints.length <= 2) {
        showToast('A curve must have at least 2 coordinate points', 'error');
        return;
    }
    curvePoints.splice(index, 1);
    drawCurve();
    renderPointsTable();
}

function addNewPoint() {
    // Generate a point in between existing ones or at the end
    let newTemp = 50;
    if (curvePoints.length > 0) {
        const maxTemp = curvePoints[curvePoints.length - 1].x;
        newTemp = maxTemp < 90 ? maxTemp + 10 : 95;
    }
    
    curvePoints.push({ x: newTemp, y: 50 });
    curvePoints.sort((a, b) => a.x - b.x);
    
    drawCurve();
    renderPointsTable();
}

function resetEditor() {
    if (activeFanId) {
        loadFanConfigIntoEditor(activeFanId);
        showToast('Editor values reset to last saved state');
    }
}

// --- Notification Toast ---
function showToast(message, type = 'success') {
    const toast = document.getElementById('toast');
    const msgEl = document.getElementById('toast-message');
    
    msgEl.textContent = message;
    
    if (type === 'error') {
        toast.style.borderColor = 'rgba(255, 65, 108, 0.5)';
        toast.style.boxShadow = '0 10px 30px rgba(0,0,0,0.4), 0 0 15px rgba(255, 65, 108, 0.15)';
    } else {
        toast.style.borderColor = 'rgba(0, 242, 254, 0.3)';
        toast.style.boxShadow = '0 10px 30px rgba(0,0,0,0.4), 0 0 15px rgba(0, 242, 254, 0.1)';
    }
    
    toast.classList.remove('hidden');
    
    // Hide toast after 3.5s
    setTimeout(() => {
        toast.classList.add('hidden');
    }, 3500);
}

// --- Hardware Settings & Mapping Wizard ---
let detectedHardware = {};
let localMappedFans = [];

function toggleSettingsModal(show) {
    const modal = document.getElementById('settings-modal');
    if (show) {
        modal.classList.remove('hidden');
        
        // Initialize mapping list from current configuration
        localMappedFans = Object.entries(config.fans || {}).map(([id, fan]) => ({
            id: id,
            label: fan.label || '',
            device_name: fan.device_name || '',
            pwm_channel: fan.pwm_channel || 1,
            fan_channel: fan.fan_channel || 1
        }));
        
        // First scan to populate devices
        scanHardware().then(() => {
            renderMappedFansTable();
        });
    } else {
        modal.classList.add('hidden');
    }
}

async function scanHardware() {
    const scannedContainer = document.getElementById('scanned-devices-list');
    scannedContainer.innerHTML = '<div class="loading-state">Scanning physical channels...</div>';
    
    try {
        const res = await fetch('/api/detect');
        detectedHardware = await res.json();
        
        scannedContainer.innerHTML = '';
        
        // Populate scanned device cards
        Object.entries(detectedHardware).forEach(([name, dev]) => {
            const card = document.createElement('div');
            card.className = 'scanned-device-card';
            
            let tempPills = dev.temps.map(t => `
                <div class="scanned-item">
                    <span class="item-label">temp${t.channel}_input ${t.label ? `(${t.label})` : ''}</span>
                    <span class="item-value">${t.current_value !== null ? t.current_value.toFixed(1) + '°C' : 'N/A'}</span>
                </div>
            `).join('');
            
            let fanPills = dev.fans.map(f => `
                <div class="scanned-item">
                    <span class="item-label">fan${f.channel}_input ${f.label ? `(${f.label})` : ''}</span>
                    <span class="item-value">
                        ${f.current_rpm} RPM 
                        ${f.has_pwm ? '<span class="pwm-tag">PWM</span>' : ''}
                    </span>
                </div>
            `).join('');
            
            card.innerHTML = `
                <h4>${name}</h4>
                <div class="device-path" title="${dev.path}">${dev.path}</div>
                <div class="scanned-device-items">
                    ${tempPills || '<div class="scanned-item text-secondary" style="font-style: italic;">No temperature inputs</div>'}
                    ${fanPills || '<div class="scanned-item text-secondary" style="font-style: italic;">No RPM inputs</div>'}
                </div>
            `;
            scannedContainer.appendChild(card);
        });

        // Re-render table in case select dropdown options need updating
        renderMappedFansTable();
        
    } catch (e) {
        scannedContainer.innerHTML = '<div class="loading-state text-danger">Failed to scan hardware sensors.</div>';
        console.error(e);
    }
}

function renderMappedFansTable() {
    const tbody = document.getElementById('mapped-fans-tbody');
    tbody.innerHTML = '';
    
    // Build options for Controller dropdown from detected hardware keys
    const deviceNames = Object.keys(detectedHardware);
    let deviceOptionsHtml = `<option value="">-- Select --</option>`;
    
    deviceNames.forEach(name => {
        deviceOptionsHtml += `<option value="${name}">${name}</option>`;
    });
    
    // If a nct* device was detected, add wildcard option 'nct*' helper
    if (deviceNames.some(n => n.startsWith('nct'))) {
        deviceOptionsHtml += `<option value="nct*">nct* (Motherboard Wildcard)</option>`;
    }

    if (localMappedFans.length === 0) {
        tbody.innerHTML = `<tr><td colspan="6" style="text-align: center; color: var(--text-secondary); padding: 20px;">No fan channels mapped yet. Click 'Add Fan' to begin.</td></tr>`;
        return;
    }

    localMappedFans.forEach((fan, idx) => {
        const row = document.createElement('tr');
        
        let pwmOptions = '';
        let rpmOptions = '';
        
        let lookupName = fan.device_name;
        if (lookupName === 'nct*' && deviceNames.some(n => n.startsWith('nct'))) {
            lookupName = deviceNames.find(n => n.startsWith('nct'));
        }
        
        const deviceData = detectedHardware[lookupName];
        if (deviceData) {
            const numPwm = Math.max(7, deviceData.fans.length);
            for (let i = 1; i <= numPwm; i++) {
                pwmOptions += `<option value="${i}" ${fan.pwm_channel === i ? 'selected' : ''}>pwm${i}</option>`;
                rpmOptions += `<option value="${i}" ${fan.fan_channel === i ? 'selected' : ''}>fan${i}</option>`;
            }
        } else {
            for (let i = 1; i <= 10; i++) {
                pwmOptions += `<option value="${i}" ${fan.pwm_channel === i ? 'selected' : ''}>pwm${i}</option>`;
                rpmOptions += `<option value="${i}" ${fan.fan_channel === i ? 'selected' : ''}>fan${i}</option>`;
            }
        }

        row.innerHTML = `
            <td>
                <input type="text" class="mapping-input" style="font-family: monospace;" value="${fan.id}" onchange="updateLocalFanField(${idx}, 'id', this.value)" placeholder="e.g. chassis_fan_1">
            </td>
            <td>
                <input type="text" class="mapping-input" value="${fan.label}" onchange="updateLocalFanField(${idx}, 'label', this.value)" placeholder="e.g. Rear Exhaust">
            </td>
            <td>
                <select class="mapping-select" onchange="updateLocalFanField(${idx}, 'device_name', this.value)">
                    ${deviceOptionsHtml.replace(`value="${fan.device_name}"`, `value="${fan.device_name}" selected`)}
                </select>
            </td>
            <td>
                <select class="mapping-select" onchange="updateLocalFanField(${idx}, 'pwm_channel', parseInt(this.value))">
                    ${pwmOptions}
                </select>
            </td>
            <td>
                <select class="mapping-select" onchange="updateLocalFanField(${idx}, 'fan_channel', parseInt(this.value))">
                    ${rpmOptions}
                </select>
            </td>
            <td>
                <button type="button" class="glass-btn btn-sm btn-danger" onclick="deleteLocalFan(${idx})">Remove</button>
            </td>
        `;
        tbody.appendChild(row);
    });
}

function updateLocalFanField(index, field, value) {
    localMappedFans[index][field] = value;
    if (field === 'device_name') {
        renderMappedFansTable();
    }
}

function addNewMappedFan() {
    localMappedFans.push({
        id: `fan_${Date.now().toString().slice(-4)}`,
        label: 'New Fan',
        device_name: '',
        pwm_channel: 1,
        fan_channel: 1
    });
    renderMappedFansTable();
}

function deleteLocalFan(index) {
    localMappedFans.splice(index, 1);
    renderMappedFansTable();
}

async function saveHardwareMapping() {
    const ids = localMappedFans.map(f => f.id.trim());
    if (ids.some(id => !id)) {
        showToast('Fan IDs cannot be empty.', 'error');
        return;
    }
    const duplicates = ids.filter((item, index) => ids.indexOf(item) !== index);
    if (duplicates.length > 0) {
        showToast(`Duplicate Fan IDs found: ${duplicates.join(', ')}`, 'error');
        return;
    }
    if (localMappedFans.some(f => !f.device_name)) {
        showToast('Please select a device for all mapped fans.', 'error');
        return;
    }

    const fansConfig = {};
    localMappedFans.forEach(f => {
        fansConfig[f.id] = {
            label: f.label,
            device_name: f.device_name,
            pwm_channel: f.pwm_channel,
            fan_channel: f.fan_channel
        };
    });

    try {
        const res = await fetch('/api/setup-hardware', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ fans: fansConfig })
        });
        const data = await res.json();
        
        if (data.success) {
            showToast('Hardware mapping applied successfully!');
            toggleSettingsModal(false);
            await fetchConfig();
            
            const fanIds = Object.keys(config.fans || {});
            if (fanIds.length > 0) {
                if (fanIds.includes(activeFanId)) {
                    selectFan(activeFanId);
                } else {
                    selectFan(fanIds[0]);
                }
            } else {
                activeFanId = null;
                document.getElementById('editor-active-fan-name').textContent = 'Select a Fan to Edit';
                document.getElementById('editor-fan-tabs').innerHTML = '';
            }
        } else {
            showToast(`Failed to save mapping: ${data.error}`, 'error');
        }
    } catch (e) {
        showToast('Network error saving mappings', 'error');
    }
}

function toggleIdentifyFan(event, fanId, enable) {
    if (event) {
        event.stopPropagation();
    }
    
    fetch('/api/toggle-identify', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ fan_id: fanId, identify: enable })
    })
    .then(res => res.json())
    .then(data => {
        if (!data.success) {
            showToast(`Failed to toggle finder: ${data.error}`, 'error');
        } else {
            showToast(enable ? `Fan finder active (runs at 100% for 20s)` : `Fan finder stopped`);
            fetchStatus(); // Force status reload
        }
    })
    .catch(() => {
        showToast('Network error toggling finder', 'error');
    });
}
