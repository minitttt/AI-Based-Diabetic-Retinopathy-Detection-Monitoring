const API_BASE = 'https://ai-based-diabetic-retinopathy-detection.onrender.com';
const CLASS_NAMES  = ['No DR', 'Mild', 'Moderate', 'Severe', 'Proliferative DR'];
const GRADE_COLORS = ['#22c55e', '#eab308', '#f97316', '#ef4444', '#a855f7'];
const LOADING_STEPS = [
    'Preprocessing fundus image…',
    'Applying CLAHE enhancement…',
    'Extracting retinal features…',
    'Running EfficientNet-B4-NS…',
    'Computing confidence scores…',
];
const dropZone         = document.getElementById('drop-zone');
const fileInput        = document.getElementById('file-input');
const uploadSection    = document.getElementById('upload-section');
const loadingSection   = document.getElementById('loading-section');
const resultsSection   = document.getElementById('results-section');
const errorSection     = document.getElementById('error-section');
const previewImage     = document.getElementById('preview-image');
const scanPreviewLoad  = document.getElementById('scan-preview-loading');
const drGrade          = document.getElementById('dr-grade');
const gradeBadge       = document.getElementById('grade-badge');
const confidenceFill   = document.getElementById('confidence-fill');
const confidenceText   = document.getElementById('confidence-text');
const probBars         = document.getElementById('prob-bars');
const filenameLbl      = document.getElementById('filename-label');
const loadingStep      = document.getElementById('loading-step');
const resetBtn         = document.getElementById('reset-btn');
const retryBtn         = document.getElementById('retry-btn');
const downloadBtn      = document.getElementById('download-btn');
const apiStatusDot     = document.getElementById('api-status-dot');
const apiStatusLabel   = document.getElementById('api-status-label');
const diagnosisIcon    = document.getElementById('diagnosis-icon');

let lastFile = null;
let lastPrediction = null;
const pages = ['diagnose', 'history', 'about'];

function switchPage(name) {
    pages.forEach(p => {
        const page = document.getElementById(`page-${p}`);
        const nav  = document.getElementById(`nav-${p}`);
        if (!page || !nav) return;
        const isActive = p === name;
        page.classList.toggle('hidden', !isActive);
        nav.classList.toggle('active', isActive);
    });

    // Draw charts when About tab is opened
    if (name === 'about') {
        drawCharts();
    }
}

// Wire nav items
pages.forEach(p => {
    const el = document.getElementById(`nav-${p}`);
    if (el) {
        el.addEventListener('click', (e) => {
            e.preventDefault();
            switchPage(p);
        });
    }
});

// Allow History's "Start Diagnosing" button
window.switchPage = switchPage;
async function checkApiHealth() {
    try {
        const r = await fetch(`${API_BASE}/`, { signal: AbortSignal.timeout(4000) });
        if (r.ok) {
            apiStatusDot.className = 'status-dot online';
            apiStatusLabel.textContent = 'API Online';
        } else {
            throw new Error('bad status');
        }
    } catch {
        apiStatusDot.className = 'status-dot offline';
        apiStatusLabel.textContent = 'API Offline';
    }
}

checkApiHealth();
setInterval(checkApiHealth, 15000);
dropZone.addEventListener('click', () => fileInput.click());
dropZone.addEventListener('keydown', e => { if (e.key === 'Enter' || e.key === ' ') fileInput.click(); });

dropZone.addEventListener('dragover',  e => { e.preventDefault(); dropZone.classList.add('dragover'); });
dropZone.addEventListener('dragleave', ()  => dropZone.classList.remove('dragover'));
dropZone.addEventListener('drop', e => {
    e.preventDefault();
    dropZone.classList.remove('dragover');
    const f = e.dataTransfer.files[0];
    if (f) handleFile(f);
});

fileInput.addEventListener('change', e => {
    if (e.target.files[0]) handleFile(e.target.files[0]);
});
resetBtn.addEventListener('click', reset);
retryBtn.addEventListener('click', () => {
    showSection(uploadSection);
    if (lastFile) handleFile(lastFile);
});
downloadBtn.addEventListener('click', downloadReport);

function reset() {
    showSection(uploadSection);
    fileInput.value = '';
    lastFile = null;
    lastPrediction = null;
}
function showSection(section) {
    [uploadSection, loadingSection, resultsSection, errorSection].forEach(s =>
        s.classList.add('hidden')
    );
    section.classList.remove('hidden');
}
let stepInterval = null;

function startLoadingSteps() {
    let i = 0;
    loadingStep.textContent = LOADING_STEPS[0];
    stepInterval = setInterval(() => {
        i = (i + 1) % LOADING_STEPS.length;
        loadingStep.textContent = LOADING_STEPS[i];
    }, 1200);
}

function stopLoadingSteps() { clearInterval(stepInterval); }
function handleFile(file) {
    if (!file.type.startsWith('image/')) {
        showError('Invalid File', 'Please upload a retinal fundus image (JPG, PNG, or BMP).');
        return;
    }
    if (file.size > 20 * 1024 * 1024) {
        showError('File Too Large', 'Maximum allowed file size is 20 MB.');
        return;
    }

    lastFile = file;

    const reader = new FileReader();
    reader.onload = e => {
        const src = e.target.result;
        previewImage.src = src;
        scanPreviewLoad.src = src;
    };
    reader.readAsDataURL(file);

    showSection(loadingSection);
    startLoadingSteps();

    const formData = new FormData();
    formData.append('file', file);

    fetch(`${API_BASE}/predict`, { method: 'POST', body: formData })
        .then(r => {
            if (!r.ok) throw new Error(`HTTP ${r.status}: ${r.statusText}`);
            return r.json();
        })
        .then(data => {
            stopLoadingSteps();
            lastPrediction = data.prediction;
            filenameLbl.textContent = file.name;
            showResults(data.prediction);
        })
        .catch(err => {
            stopLoadingSteps();
            console.error(err);
            showError(
                'Prediction Failed',
                `Could not reach the AI backend. Make sure the server is running at ${API_BASE}.`
            );
        });
}
function showResults(pred) {
    const gradeIdx  = pred.grade_idx;
    const gradeName = CLASS_NAMES[gradeIdx] || pred.grade_name;
    const color     = GRADE_COLORS[gradeIdx];

    drGrade.textContent = gradeName;
    drGrade.className   = `dr-grade grade-${gradeIdx}`;
    gradeBadge.textContent = `Grade ${gradeIdx}`;

    diagnosisIcon.style.background   = `${color}1a`;
    diagnosisIcon.style.borderColor  = `${color}40`;
    diagnosisIcon.querySelector('svg').style.color = color;

    const pct = (pred.confidence * 100).toFixed(1);
    setTimeout(() => {
        confidenceFill.style.width  = `${pct}%`;
        confidenceText.textContent  = `${pct}%`;
    }, 120);

    probBars.innerHTML = '';
    pred.probabilities.forEach((p, i) => {
        const pPct  = (p * 100).toFixed(1);
        const isTop = i === gradeIdx;
        const row   = document.createElement('div');
        row.className = 'prob-row';
        row.innerHTML = `
            <span class="prob-name" style="${isTop ? `color:${GRADE_COLORS[i]};font-weight:800` : ''}">${CLASS_NAMES[i]}</span>
            <div class="prob-track">
                <div class="prob-fill" data-pct="${pPct}" style="background:${GRADE_COLORS[i]}${isTop ? '' : '77'}"></div>
            </div>
            <span class="prob-pct" style="${isTop ? `color:${GRADE_COLORS[i]}` : ''}">${pPct}%</span>
        `;
        probBars.appendChild(row);
    });

    showSection(resultsSection);
    requestAnimationFrame(() => requestAnimationFrame(() => {
        probBars.querySelectorAll('.prob-fill').forEach(el => {
            el.style.width = `${el.dataset.pct}%`;
        });
    }));
}
function showError(title, msg) {
    document.getElementById('error-title').textContent = title;
    document.getElementById('error-msg').textContent   = msg;
    showSection(errorSection);
}
function downloadReport() {
    if (!lastPrediction) return;
    const p   = lastPrediction;
    const now = new Date().toLocaleString();
    const lines = [
        '╔══════════════════════════════════════╗',
        '║     RetinaScan AI — DR Report        ║',
        '╚══════════════════════════════════════╝',
        '',
        `Date/Time  : ${now}`,
        `File       : ${lastFile ? lastFile.name : 'N/A'}`,
        '',
        `DR Grade   : ${CLASS_NAMES[p.grade_idx]} (Grade ${p.grade_idx})`,
        `Confidence : ${(p.confidence * 100).toFixed(1)}%`,
        '',
        'Class Probabilities:',
        ...p.probabilities.map((prob, i) =>
            `  ${CLASS_NAMES[i].padEnd(18)} ${(prob * 100).toFixed(2)}%`
        ),
        '',
        '--- Generated by RetinaScan AI ---',
        'For clinical use, consult a qualified ophthalmologist.',
    ];
    const blob = new Blob([lines.join('\n')], { type: 'text/plain' });
    const a = document.createElement('a');
    a.href     = URL.createObjectURL(blob);
    a.download = `retinascan_report_${Date.now()}.txt`;
    a.click();
}
const TRAIN_DATA = {
    epochs:     [1, 2, 3, 4, 5, 6, 7, 8, 9],
    trainLoss:  [1.092, 0.741, 0.665, 0.638, 0.604, 0.633, 0.462, 0.371, 0.308],
    valLoss:    [0.371, 0.336, 0.300, 0.299, 0.297, 0.304, 0.279, 0.300, 0.242],
    trainKappa: [0.417, 0.485, 0.491, 0.448, 0.503, 0.557, 0.677, 0.713, 0.751],
    valKappa:   [0.578, 0.614, 0.612, 0.616, 0.652, 0.666, 0.689, 0.658, 0.701],
    trainAcc:   [36.2, 38.4, 39.8, 38.5, 41.1, 40.7, 51.5, 56.5, 60.4],
    valAcc:     [47.4, 44.4, 40.3, 43.9, 43.5, 37.3, 35.3, 44.6, 55.0],
};

let chartsDrawn = false;

function drawCharts() {
    if (chartsDrawn) return;
    chartsDrawn = true;

    drawLineChart('lossChart',  [
        { label: 'Train Loss', data: TRAIN_DATA.trainLoss,  color: '#38bdf8' },
        { label: 'Val Loss',   data: TRAIN_DATA.valLoss,    color: '#818cf8' },
    ], { min: 0, max: 1.2, suffix: '' });

    drawLineChart('kappaChart', [
        { label: 'Train κ', data: TRAIN_DATA.trainKappa, color: '#22c55e' },
        { label: 'Val κ',   data: TRAIN_DATA.valKappa,   color: '#a855f7' },
    ], { min: 0, max: 1.0, suffix: '' });

    drawLineChart('accChart', [
        { label: 'Train Acc', data: TRAIN_DATA.trainAcc, color: '#f97316' },
        { label: 'Val Acc',   data: TRAIN_DATA.valAcc,   color: '#eab308' },
    ], { min: 0, max: 100, suffix: '%' });
}

function drawLineChart(canvasId, series, { min = 0, max = 1, suffix = '' } = {}) {
    const canvas = document.getElementById(canvasId);
    if (!canvas) return;
    const ctx    = canvas.getContext('2d');
    const W      = canvas.offsetWidth  || 300;
    const H      = canvas.offsetHeight || 160;
    canvas.width  = W * window.devicePixelRatio;
    canvas.height = H * window.devicePixelRatio;
    ctx.scale(window.devicePixelRatio, window.devicePixelRatio);

    const pad  = { top: 16, right: 20, bottom: 32, left: 38 };
    const plotW = W - pad.left - pad.right;
    const plotH = H - pad.top  - pad.bottom;
    const n     = TRAIN_DATA.epochs.length;

    // Background
    ctx.fillStyle = 'rgba(0,0,0,0)';
    ctx.fillRect(0, 0, W, H);

    // Grid lines
    const gridCount = 4;
    for (let i = 0; i <= gridCount; i++) {
        const y = pad.top + (plotH / gridCount) * i;
        ctx.strokeStyle = 'rgba(148,163,184,0.08)';
        ctx.lineWidth   = 1;
        ctx.beginPath();
        ctx.moveTo(pad.left, y);
        ctx.lineTo(pad.left + plotW, y);
        ctx.stroke();
        // Y label
        const val = max - ((max - min) / gridCount) * i;
        ctx.fillStyle = 'rgba(100,130,160,0.8)';
        ctx.font      = `${9 * window.devicePixelRatio / window.devicePixelRatio}px Inter, sans-serif`;
        ctx.textAlign = 'right';
        ctx.fillText(val.toFixed(suffix === '%' ? 0 : 2) + suffix, pad.left - 5, y + 3);
    }

    // X labels
    ctx.fillStyle = 'rgba(100,130,160,0.8)';
    ctx.textAlign = 'center';
    TRAIN_DATA.epochs.forEach((ep, i) => {
        const x = pad.left + (plotW / (n - 1)) * i;
        ctx.fillText(ep, x, H - pad.bottom + 14);
    });

    // X axis label
    ctx.fillStyle = 'rgba(100,130,160,0.5)';
    ctx.font = `9px Inter, sans-serif`;
    ctx.textAlign = 'center';
    ctx.fillText('Epoch', pad.left + plotW / 2, H - 4);

    // Draw each series
    series.forEach(({ data, color }, si) => {
        const xOf = i => pad.left + (plotW / (n - 1)) * i;
        const yOf = v => pad.top + plotH - ((v - min) / (max - min)) * plotH;

        // Gradient fill
        const grad = ctx.createLinearGradient(0, pad.top, 0, pad.top + plotH);
        grad.addColorStop(0,   color + '33');
        grad.addColorStop(1,   color + '00');
        ctx.beginPath();
        ctx.moveTo(xOf(0), yOf(data[0]));
        for (let i = 1; i < n; i++) ctx.lineTo(xOf(i), yOf(data[i]));
        ctx.lineTo(xOf(n - 1), pad.top + plotH);
        ctx.lineTo(xOf(0),     pad.top + plotH);
        ctx.closePath();
        ctx.fillStyle = grad;
        ctx.fill();

        // Line
        ctx.beginPath();
        ctx.strokeStyle = color;
        ctx.lineWidth   = 2.2;
        ctx.lineJoin    = 'round';
        ctx.lineCap     = 'round';
        ctx.moveTo(xOf(0), yOf(data[0]));
        for (let i = 1; i < n; i++) ctx.lineTo(xOf(i), yOf(data[i]));
        ctx.stroke();

        // Dots
        data.forEach((v, i) => {
            ctx.beginPath();
            ctx.arc(xOf(i), yOf(v), i === n - 1 ? 4 : 3, 0, Math.PI * 2);
            ctx.fillStyle   = i === n - 1 ? color : 'rgba(6,10,26,0.9)';
            ctx.strokeStyle = color;
            ctx.lineWidth   = 1.8;
            ctx.fill();
            ctx.stroke();
        });
    });

    // Legend
    const legendX = pad.left + plotW - series.length * 75 + 10;
    series.forEach(({ label, color }, i) => {
        const lx = legendX + i * 75;
        ctx.beginPath();
        ctx.strokeStyle = color;
        ctx.lineWidth   = 2;
        ctx.moveTo(lx, pad.top + 6);
        ctx.lineTo(lx + 14, pad.top + 6);
        ctx.stroke();
        ctx.fillStyle = 'rgba(148,163,184,0.9)';
        ctx.textAlign = 'left';
        ctx.font = `9px Inter, sans-serif`;
        ctx.fillText(label, lx + 18, pad.top + 10);
    });
}
