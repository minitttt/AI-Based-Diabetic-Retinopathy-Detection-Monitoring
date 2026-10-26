const API_BASE = 'http://localhost:8001';
const CLASS_NAMES = ['No DR', 'Mild', 'Moderate', 'Severe', 'Proliferative DR'];
const GRADE_COLORS = ['#199b73', '#9aaf3c', '#d8853b', '#d45b4b', '#8c3d68'];
const LOADING_STEPS = [
    'Preprocessing fundus image…',
    'Applying CLAHE enhancement…',
    'Extracting retinal features…',
    'Running EfficientNet-B4-NS…',
    'Computing confidence scores…',
];
const REPORT_ARTIFACTS = {
    pdf: { field: 'pdf_url', label: 'PDF report', extension: 'pdf' },
    csv: { field: 'csv_url', label: 'CSV research export', extension: 'csv' },
    json: { field: 'json_url', label: 'JSON research export', extension: 'json' },
};

const byId = id => document.getElementById(id);
const dropZone = byId('drop-zone');
const fileInput = byId('file-input');
const uploadSection = byId('upload-section');
const loadingSection = byId('loading-section');
const resultsSection = byId('results-section');
const errorSection = byId('error-section');
const previewImage = byId('preview-image');
const scanPreviewLoad = byId('scan-preview-loading');
const drGrade = byId('dr-grade');
const gradeBadge = byId('grade-badge');
const confidenceFill = byId('confidence-fill');
const confidenceText = byId('confidence-text');
const probBars = byId('prob-bars');
const filenameLbl = byId('filename-label');
const loadingStep = byId('loading-step');
const resetBtn = byId('reset-btn');
const retryBtn = byId('retry-btn');
const downloadBtn = byId('download-btn');
const downloadCsvBtn = byId('download-csv-btn');
const downloadJsonBtn = byId('download-json-btn');
const apiStatusDot = byId('api-status-dot');
const apiStatusLabel = byId('api-status-label');
const diagnosisIcon = byId('diagnosis-icon');
const patientSelect = byId('patient-select');
const scanDate = byId('scan-date');
const scanEye = byId('scan-eye');
const scanNotes = byId('scan-notes');
const saveModeLabel = byId('save-mode-label');
const patientSelectError = byId('patient-select-error');
const predictionSaveStatus = byId('prediction-save-status');
const reportAvailabilityStatus = byId('report-availability-status');
const reportActionStatus = byId('report-action-status');
const reportPatientId = byId('report-patient-id');
const reportModelVersion = byId('report-model-version');
const reportTimestamp = byId('report-timestamp');
const reportImageQuality = byId('report-image-quality');
const gradcamImage = byId('gradcam-image');
const gradcamFallback = byId('gradcam-fallback');
const viewHistoryBtn = byId('view-history-btn');

const patientList = byId('patient-list');
const patientListStatus = byId('patient-list-status');
const patientCount = byId('patient-count');
const patientSearch = byId('patient-search');
const patientDetailEmpty = byId('patient-detail-empty');
const patientDetailLoading = byId('patient-detail-loading');
const patientDetailError = byId('patient-detail-error');
const patientDetailErrorMessage = byId('patient-detail-error-message');
const patientDetailContent = byId('patient-detail-content');
const patientAvatar = byId('patient-avatar');
const patientDetailHeading = byId('patient-detail-heading');
const patientDetailMeta = byId('patient-detail-meta');
const patientSummary = byId('patient-summary');
const timelineScanCount = byId('timeline-scan-count');
const timelineEmpty = byId('timeline-empty');
const timelineList = byId('timeline-list');
const patientDialog = byId('patient-dialog');
const patientForm = byId('patient-form');
const patientFormError = byId('patient-form-error');
const patientNameInput = byId('patient-name');
const patientIdInput = byId('patient-id-input');
const patientAgeInput = byId('patient-age');
const patientGenderInput = byId('patient-gender');
const patientDiabetesInput = byId('patient-diabetes-type');
const patientNameError = byId('patient-name-error');
const savePatientBtn = byId('save-patient-btn');

let lastFile = null;
let lastPrediction = null;
let lastReport = null;
let lastScanContext = null;
let scanRequestId = 0;
let stepInterval = null;
let patientLoadPromise = null;
const pages = ['diagnose', 'history', 'about'];
const patientState = {
    patients: [],
    loaded: false,
    loading: false,
    selectedId: '',
    selectedProfile: null,
    filter: '',
    profileRequest: 0,
};

function todayIso() {
    const now = new Date();
    const month = String(now.getMonth() + 1).padStart(2, '0');
    const day = String(now.getDate()).padStart(2, '0');
    return `${now.getFullYear()}-${month}-${day}`;
}

function normalizeId(value) {
    return value === null || value === undefined ? '' : String(value);
}

function patientById(id) {
    const normalized = normalizeId(id);
    return patientState.patients.find(patient => normalizeId(patient.patient_id) === normalized) || null;
}

function isHistoryVisible() {
    const page = byId('page-history');
    return Boolean(page && !page.classList.contains('hidden'));
}

function setHidden(element, hidden) {
    if (element) element.classList.toggle('hidden', hidden);
}

function formatApiDetail(detail) {
    if (Array.isArray(detail)) {
        return detail.map(item => {
            if (typeof item === 'string') return item;
            if (item && typeof item.msg === 'string') return item.msg;
            return JSON.stringify(item);
        }).join('; ');
    }
    if (detail && typeof detail === 'object') {
        if (typeof detail.message === 'string') return detail.message;
        return JSON.stringify(detail);
    }
    return typeof detail === 'string' ? detail : '';
}

function errorMessage(error, fallback = 'Something went wrong. Please try again.') {
    if (!error) return fallback;
    return error.message || fallback;
}

async function readApiResponse(response) {
    let payload = {};
    try {
        const parsed = await response.json();
        payload = parsed && typeof parsed === 'object' ? parsed : {};
    } catch {
        payload = {};
    }
    if (!response.ok) {
        const message = formatApiDetail(payload.detail) || `Request failed (${response.status})`;
        const error = new Error(message);
        error.status = response.status;
        error.payload = payload;
        throw error;
    }
    return payload;
}

async function apiRequest(path, options = {}) {
    let response;
    try {
        response = await fetch(`${API_BASE}${path}`, options);
    } catch (error) {
        if (error && error.name === 'AbortError') {
            throw new Error('The request timed out. Please try again.');
        }
        throw new Error(`Could not reach the AI backend at ${API_BASE}.`);
    }
    return readApiResponse(response);
}

function setWorkspaceStatus(message, state = '') {
    if (!patientListStatus) return;
    patientListStatus.className = `workspace-status${state ? ` ${state}` : ''}`;
    patientListStatus.textContent = message || '';
}

function gradeIndex(value, label = '') {
    if (typeof value === 'number' && Number.isFinite(value)) {
        return Math.max(0, Math.min(CLASS_NAMES.length - 1, Math.round(value)));
    }
    if (typeof value === 'string' && value.trim() !== '') {
        const number = Number(value);
        if (Number.isFinite(number)) return Math.max(0, Math.min(CLASS_NAMES.length - 1, Math.round(number)));
        const lower = value.trim().toLowerCase();
        const gradeMatch = lower.match(/grade\s*([0-4])/);
        if (gradeMatch) return Number(gradeMatch[1]);
        const byName = CLASS_NAMES.findIndex(name => name.toLowerCase() === lower);
        if (byName >= 0) return byName;
        const partial = CLASS_NAMES.findIndex(name => lower.includes(name.toLowerCase()));
        if (partial >= 0) return partial;
    }
    if (typeof label === 'string' && label.trim() !== '') return gradeIndex(label);
    return null;
}

function gradeInfo(value, label = '') {
    const index = gradeIndex(value, label);
    if (index === null) {
        return { index: null, name: label || (value === null || value === undefined ? 'Not available' : String(value)) };
    }
    return { index, name: CLASS_NAMES[index] };
}

function formatDate(value, includeTime = false) {
    if (!value) return 'Date not recorded';
    const raw = String(value);
    const date = /^\d{4}-\d{2}-\d{2}$/.test(raw)
        ? new Date(`${raw}T12:00:00`)
        : new Date(raw);
    if (Number.isNaN(date.getTime())) return raw;
    return new Intl.DateTimeFormat(undefined, {
        year: 'numeric',
        month: 'short',
        day: 'numeric',
        ...(includeTime ? { hour: 'numeric', minute: '2-digit' } : {}),
    }).format(date);
}

function resolveReportUrl(value) {
    if (value === null || value === undefined || String(value).trim() === '') return '';
    try {
        const url = new URL(String(value), `${API_BASE}/`);
        return ['http:', 'https:'].includes(url.protocol) ? url.toString() : '';
    } catch {
        return '';
    }
}

function formatReportValue(value, fallback = 'Not available') {
    if (value === null || value === undefined || String(value).trim() === '') return fallback;
    return String(value);
}

function formatImageQualityScore(value) {
    const score = Number(value);
    if (!Number.isFinite(score)) return 'Not available';
    const normalized = Math.max(0, Math.min(1, score > 1 ? score / 100 : score));
    return `${(normalized * 100).toFixed(1)}%`;
}

function formatConfidence(value) {
    const number = Number(value);
    if (!Number.isFinite(number)) return 'Confidence not recorded';
    const normalized = Math.max(0, Math.min(1, number > 1 ? number / 100 : number));
    return `${(normalized * 100).toFixed(1)}% confidence`;
}

function formatCount(value, singular, plural = `${singular}s`) {
    const count = Number(value);
    if (!Number.isFinite(count)) return `0 ${plural}`;
    return `${count} ${count === 1 ? singular : plural}`;
}

function initials(name) {
    const parts = String(name || 'Patient').trim().split(/\s+/).filter(Boolean);
    return parts.slice(0, 2).map(part => part[0]).join('').toUpperCase() || 'P';
}

function scanSortValue(scan) {
    const value = scan && (scan.scan_date || scan.created_at);
    const time = value ? new Date(value).getTime() : 0;
    return Number.isFinite(time) ? time : 0;
}

function sortedScans(scans) {
    return (Array.isArray(scans) ? scans : []).slice().sort((a, b) => scanSortValue(a) - scanSortValue(b));
}

function renderPatientSelector() {
    if (!patientSelect) return;
    const selected = normalizeId(patientState.selectedId);
    patientSelect.replaceChildren();
    const quickOption = document.createElement('option');
    quickOption.value = '';
    quickOption.textContent = 'Quick analysis — do not save';
    patientSelect.appendChild(quickOption);
    patientState.patients.forEach(patient => {
        const option = document.createElement('option');
        option.value = normalizeId(patient.patient_id);
        const id = patient.patient_id ? ` · ID ${patient.patient_id}` : '';
        option.textContent = `${patient.name || 'Unnamed patient'}${id}`;
        patientSelect.appendChild(option);
    });
    patientSelect.value = patientState.patients.some(patient => normalizeId(patient.patient_id) === selected)
        ? selected
        : '';
    updateScanSaveMode();
}

function updateScanSaveMode() {
    if (!patientSelect) return;
    const saving = Boolean(patientSelect.value);
    if (saveModeLabel) {
        saveModeLabel.textContent = saving ? 'Saved to the selected patient' : 'Quick analysis is not saved';
        saveModeLabel.classList.toggle('is-saving', saving);
        saveModeLabel.classList.toggle('is-quick', !saving);
    }
    if (patientSelectError && saving) {
        setHidden(patientSelectError, true);
        patientSelectError.textContent = '';
        patientSelect.removeAttribute('aria-invalid');
    }
}

function renderPatientList() {
    if (patientCount) patientCount.textContent = String(patientState.patients.length);
    if (!patientList) return;
    patientList.replaceChildren();
    const query = patientState.filter.trim().toLowerCase();
    const filtered = patientState.patients.filter(patient => {
        if (!query) return true;
        return [patient.name, patient.patient_id, patient.gender, patient.diabetes_type]
            .filter(value => value !== null && value !== undefined)
            .some(value => String(value).toLowerCase().includes(query));
    });

    if (patientState.loading) {
        setWorkspaceStatus('Loading patient profiles…', 'loading');
    } else if (!patientState.patients.length) {
        setWorkspaceStatus('No patient profiles yet. Create one to begin monitoring.');
    } else if (!filtered.length) {
        setWorkspaceStatus('No patients match this search.');
    } else {
        setWorkspaceStatus('');
    }

    filtered.forEach(patient => {
        const id = normalizeId(patient.patient_id);
        const wrapper = document.createElement('div');
        wrapper.setAttribute('role', 'listitem');
        const button = document.createElement('button');
        button.type = 'button';
        button.className = 'patient-card';
        button.setAttribute('aria-pressed', String(id === normalizeId(patientState.selectedId)));
        button.setAttribute('aria-label', `Open patient ${patient.name || id || 'profile'}`);

        const avatar = document.createElement('span');
        avatar.className = 'patient-card-avatar';
        avatar.textContent = initials(patient.name);
        const copy = document.createElement('span');
        copy.className = 'patient-card-copy';
        const name = document.createElement('span');
        name.className = 'patient-card-name';
        name.textContent = patient.name || 'Unnamed patient';
        const meta = document.createElement('span');
        meta.className = 'patient-card-meta';
        const age = patient.age ? `${patient.age} yrs` : '';
        const gender = patient.gender || '';
        const metaParts = [age, gender, patient.last_scan_date ? `Last ${formatDate(patient.last_scan_date)}` : 'No scans'];
        meta.textContent = metaParts.filter(Boolean).join(' · ');
        copy.append(name, meta);

        const stats = document.createElement('span');
        stats.className = 'patient-card-stats';
        const scanCount = document.createElement('span');
        scanCount.className = 'patient-card-scan-count';
        scanCount.textContent = formatCount(patient.scan_count || 0, 'scan');
        const lastGrade = gradeInfo(patient.last_grade, patient.last_label);
        const grade = document.createElement('span');
        grade.className = `patient-card-grade ${lastGrade.index === null ? 'grade-unknown' : `grade-${lastGrade.index}`}`;
        grade.textContent = lastGrade.index === null && lastGrade.name === 'Not available' ? 'No grade' : lastGrade.name;
        stats.append(scanCount, grade);
        button.append(avatar, copy, stats);
        button.addEventListener('click', () => selectPatient(id));
        wrapper.appendChild(button);
        patientList.appendChild(wrapper);
    });
}

function showDetailState(state) {
    setHidden(patientDetailEmpty, state !== 'empty');
    setHidden(patientDetailLoading, state !== 'loading');
    setHidden(patientDetailError, state !== 'error');
    setHidden(patientDetailContent, state !== 'content');
}

function renderPatientDetailError(error) {
    showDetailState('error');
    if (patientDetailErrorMessage) {
        patientDetailErrorMessage.textContent = errorMessage(error, 'We could not load this patient right now.');
    }
}

function buildSummaryCard(label, value, detail, className = '') {
    const card = document.createElement('div');
    card.className = 'summary-card';
    const labelEl = document.createElement('span');
    labelEl.className = 'summary-label';
    labelEl.textContent = label;
    const valueEl = document.createElement('strong');
    valueEl.className = `summary-value${className ? ` ${className}` : ''}`;
    valueEl.textContent = value;
    const detailEl = document.createElement('span');
    detailEl.className = 'summary-detail';
    detailEl.textContent = detail || '';
    card.append(labelEl, valueEl, detailEl);
    return card;
}

function trendInfo(rawTrend, change) {
    const raw = String(rawTrend || '').trim().toLowerCase();
    if (raw.includes('wors') || raw.includes('progress')) return { label: 'Worsening', className: 'trend-worsening' };
    if (raw.includes('improv') || raw.includes('better')) return { label: 'Improving', className: 'trend-improving' };
    if (raw.includes('stable') || raw.includes('unchanged')) return { label: 'Stable', className: 'trend-stable' };
    if (Number(change) > 0) return { label: 'Worsening', className: 'trend-worsening' };
    if (Number(change) < 0) return { label: 'Improving', className: 'trend-improving' };
    return { label: 'Stable', className: 'trend-stable' };
}

function renderTimeline(scans) {
    if (!timelineList || !timelineEmpty) return;
    timelineList.replaceChildren();
    const ordered = sortedScans(scans);
    setHidden(timelineEmpty, ordered.length > 0);
    if (timelineScanCount) timelineScanCount.textContent = formatCount(ordered.length, 'saved scan');
    ordered.forEach((scan, index) => {
        const info = gradeInfo(scan.predicted_grade, scan.predicted_label);
        const item = document.createElement('li');
        item.className = `timeline-item ${info.index === null ? '' : `grade-${info.index}`}`.trim();
        const card = document.createElement('article');
        card.className = 'timeline-card';
        const header = document.createElement('div');
        header.className = 'timeline-card-header';
        const heading = document.createElement('div');
        const date = document.createElement('h3');
        date.className = 'timeline-date';
        date.textContent = formatDate(scan.scan_date || scan.created_at);
        const eye = document.createElement('p');
        eye.className = 'timeline-eye';
        eye.textContent = `Eye: ${scan.eye || 'Unknown'}`;
        heading.append(date, eye);
        const side = document.createElement('div');
        side.className = 'timeline-card-side';
        const grade = document.createElement('span');
        grade.className = `grade-pill ${info.index === null ? 'grade-unknown' : `grade-${info.index}`}`;
        grade.textContent = info.name;
        const confidence = document.createElement('span');
        confidence.className = 'confidence-pill';
        confidence.textContent = formatConfidence(scan.confidence);
        side.append(grade, confidence);
        header.append(heading, side);
        card.appendChild(header);
        if (scan.notes) {
            const notes = document.createElement('p');
            notes.className = 'timeline-notes';
            const notesLabel = document.createElement('strong');
            notesLabel.textContent = 'Notes';
            notes.append(notesLabel, document.createTextNode(` ${scan.notes}`));
            card.appendChild(notes);
        }
        if (scan.scan_id !== null && scan.scan_id !== undefined) {
            const scanId = document.createElement('span');
            scanId.className = 'timeline-id';
            scanId.textContent = `Scan ${scan.scan_id}${index === 0 ? ' · baseline record' : ''}`;
            card.appendChild(scanId);
        }
        item.appendChild(card);
        timelineList.appendChild(item);
    });
}

function renderPatientDetail(data) {
    const fallback = patientById(patientState.selectedId) || {};
    const patient = data && data.patient ? data.patient : fallback;
    const scans = sortedScans(data && data.scans);
    const providedProgression = data && data.progression ? data.progression : {};
    const baseline = gradeInfo(
        providedProgression.baseline_grade !== undefined ? providedProgression.baseline_grade : scans[0] && scans[0].predicted_grade,
        scans[0] && scans[0].predicted_label,
    );
    const current = gradeInfo(
        providedProgression.current_grade !== undefined ? providedProgression.current_grade : scans[scans.length - 1] && scans[scans.length - 1].predicted_grade,
        scans[scans.length - 1] && scans[scans.length - 1].predicted_label,
    );
    const computedChange = baseline.index !== null && current.index !== null ? current.index - baseline.index : null;
    const rawChange = Number(providedProgression.change);
    const change = Number.isFinite(rawChange) ? rawChange : computedChange;
    const trend = trendInfo(providedProgression.trend, change);

    showDetailState('content');
    if (patientAvatar) patientAvatar.textContent = initials(patient.name);
    if (patientDetailHeading) patientDetailHeading.textContent = patient.name || 'Unnamed patient';
    if (patientDetailMeta) {
        const details = [
            patient.patient_id ? `ID ${patient.patient_id}` : '',
            patient.age ? `${patient.age} years` : '',
            patient.gender || '',
            patient.diabetes_type || '',
        ].filter(Boolean);
        patientDetailMeta.textContent = details.length ? details.join(' · ') : 'Profile details not provided';
    }
    if (patientSummary) {
        patientSummary.replaceChildren();
        const scanCount = Number(providedProgression.scan_count);
        patientSummary.append(
            buildSummaryCard('Baseline grade', baseline.index === null ? 'Not available' : baseline.name, scans.length ? formatDate(scans[0].scan_date || scans[0].created_at) : 'Awaiting first scan', baseline.index === null ? '' : `grade-${baseline.index}`),
            buildSummaryCard('Current grade', current.index === null ? 'Not available' : current.name, providedProgression.latest_date ? formatDate(providedProgression.latest_date) : scans.length ? formatDate(scans[scans.length - 1].scan_date || scans[scans.length - 1].created_at) : 'Awaiting first scan', current.index === null ? '' : `grade-${current.index}`),
            buildSummaryCard('Ordinal change', change === null ? '—' : `${change > 0 ? '+' : ''}${change}`, change === null ? 'Requires two scans' : 'Current minus baseline grade'),
            buildSummaryCard('Model-observed trend', scans.length < 2 ? 'Awaiting scans' : trend.label, `${Number.isFinite(scanCount) ? scanCount : scans.length} total`, scans.length < 2 ? '' : trend.className),
        );
    }
    renderTimeline(scans);
}

async function loadPatientProfile(id) {
    const normalized = normalizeId(id);
    if (!normalized) {
        showDetailState('empty');
        return;
    }
    const requestId = ++patientState.profileRequest;
    showDetailState('loading');
    try {
        const data = await apiRequest(`/patients/${encodeURIComponent(normalized)}`);
        if (requestId !== patientState.profileRequest || normalized !== normalizeId(patientState.selectedId)) return;
        patientState.selectedProfile = data;
        renderPatientDetail(data);
    } catch (error) {
        if (requestId !== patientState.profileRequest) return;
        patientState.selectedProfile = null;
        renderPatientDetailError(error);
    }
}

async function selectPatient(id, { loadProfile = true } = {}) {
    const normalized = normalizeId(id);
    if (!normalized || !patientById(normalized)) return;
    patientState.selectedId = normalized;
    patientState.selectedProfile = null;
    renderPatientList();
    renderPatientSelector();
    if (loadProfile && isHistoryVisible()) await loadPatientProfile(normalized);
}

async function loadPatients({ selectId = '', selectFirst = false, force = false } = {}) {
    if (patientState.loading) {
        if (patientLoadPromise) await patientLoadPromise;
        if (force || selectId || selectFirst) return loadPatients({ selectId, selectFirst, force });
        return true;
    }
    if (patientState.loaded && !force && !selectId && !(selectFirst && !patientState.selectedId)) {
        renderPatientList();
        renderPatientSelector();
        return true;
    }
    patientState.loading = true;
    renderPatientList();
    const requestPromise = (async () => {
        try {
            const data = await apiRequest('/patients');
            const patients = Array.isArray(data && data.patients) ? data.patients : [];
            patientState.patients = patients;
            patientState.loaded = true;
            patientState.loading = false;
            const requested = normalizeId(selectId);
            const current = normalizeId(patientState.selectedId);
            const selected = patients.some(patient => normalizeId(patient.patient_id) === requested)
                ? requested
                : patients.some(patient => normalizeId(patient.patient_id) === current)
                    ? current
                    : selectFirst && patients.length
                        ? normalizeId(patients[0].patient_id)
                        : '';
            patientState.selectedId = selected;
            if (!selected) patientState.selectedProfile = null;
            renderPatientList();
            renderPatientSelector();
            if (isHistoryVisible() && selected && (!patientState.selectedProfile || requested === selected || force)) {
                await loadPatientProfile(selected);
            } else if (isHistoryVisible() && !selected) {
                showDetailState('empty');
            }
            return true;
        } catch (error) {
            patientState.loading = false;
            patientState.loaded = false;
            renderPatientList();
            setWorkspaceStatus(errorMessage(error, 'Unable to load patient profiles.'), 'error');
            if (isHistoryVisible() && !patientState.selectedId) showDetailState('empty');
            return false;
        }
    })();
    patientLoadPromise = requestPromise;
    try {
        return await requestPromise;
    } finally {
        if (patientLoadPromise === requestPromise) patientLoadPromise = null;
    }
}

function openPatientDialog() {
    if (!patientDialog) return;
    if (patientDialog.open) return;
    clearPatientFormErrors();
    if (patientForm) patientForm.reset();
    if (typeof patientDialog.showModal === 'function') patientDialog.showModal();
    else patientDialog.setAttribute('open', '');
    window.setTimeout(() => patientNameInput && patientNameInput.focus(), 0);
}

function closePatientDialog() {
    if (!patientDialog) return;
    if (typeof patientDialog.close === 'function' && patientDialog.open) patientDialog.close();
    else patientDialog.removeAttribute('open');
}

function clearPatientFormErrors() {
    setHidden(patientFormError, true);
    if (patientFormError) patientFormError.textContent = '';
    setHidden(patientNameError, true);
    if (patientNameError) patientNameError.textContent = '';
    patientNameInput && patientNameInput.removeAttribute('aria-invalid');
}

function showPatientFormError(message, field = '') {
    if (field === 'name' && patientNameError) {
        patientNameError.textContent = message;
        setHidden(patientNameError, false);
        patientNameInput && patientNameInput.setAttribute('aria-invalid', 'true');
        patientNameInput && patientNameInput.focus();
        return;
    }
    if (patientFormError) {
        patientFormError.textContent = message;
        setHidden(patientFormError, false);
    }
}

async function createPatient(event) {
    event.preventDefault();
    clearPatientFormErrors();
    const name = patientNameInput ? patientNameInput.value.trim() : '';
    if (!name) {
        showPatientFormError('Enter the patient name to create a profile.', 'name');
        return;
    }
    const payload = { name };
    const id = patientIdInput && patientIdInput.value.trim();
    const age = patientAgeInput && patientAgeInput.value.trim();
    const gender = patientGenderInput && patientGenderInput.value;
    const diabetesType = patientDiabetesInput && patientDiabetesInput.value;
    if (id) payload.patient_id = id;
    if (age) {
        const parsedAge = Number(age);
        if (!Number.isInteger(parsedAge) || parsedAge < 0 || parsedAge > 130) {
            showPatientFormError('Age must be a whole number between 0 and 130.');
            return;
        }
        payload.age = parsedAge;
    }
    if (gender) payload.gender = gender;
    if (diabetesType) payload.diabetes_type = diabetesType;

    if (savePatientBtn) {
        savePatientBtn.disabled = true;
        savePatientBtn.textContent = 'Creating…';
    }
    try {
        const data = await apiRequest('/patients', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload),
        });
        const created = data && data.patient ? data.patient : data;
        const createdId = normalizeId(created && created.patient_id);
        if (!createdId) throw new Error('The API created the profile but did not return a patient ID.');
        await loadPatients({ selectId: createdId, selectFirst: true, force: true });
        if (!patientById(createdId)) throw new Error('The profile was created, but the patient list could not be refreshed.');
        await selectPatient(createdId);
        closePatientDialog();
    } catch (error) {
        showPatientFormError(errorMessage(error, 'Unable to create this patient profile.'));
    } finally {
        if (savePatientBtn) {
            savePatientBtn.disabled = false;
            savePatientBtn.textContent = 'Create patient';
        }
    }
}

function setPredictionSaveStatus(message, state = 'info') {
    if (!predictionSaveStatus) return;
    predictionSaveStatus.className = `prediction-save-status ${state}`;
    predictionSaveStatus.textContent = message;
    setHidden(predictionSaveStatus, false);
}

function setReportAvailabilityStatus(message, state = '') {
    if (!reportAvailabilityStatus) return;
    reportAvailabilityStatus.className = `report-availability-status${state ? ` ${state}` : ''}`;
    reportAvailabilityStatus.textContent = message;
}

function setReportActionStatus(message, state = 'info') {
    if (!reportActionStatus) return;
    reportActionStatus.className = `report-action-status ${state}`;
    reportActionStatus.textContent = message;
    setHidden(reportActionStatus, false);
}

function setReportButtonsBusy(busy) {
    [downloadBtn, downloadCsvBtn, downloadJsonBtn].forEach(button => {
        if (!button) return;
        button.disabled = busy;
        button.setAttribute('aria-busy', String(busy));
    });
}

function renderGradcam(report) {
    if (!gradcamImage || !gradcamFallback) return;
    const defaultFallback = 'No Grad-CAM attention preview is available for this analysis.';
    const imageUrl = resolveReportUrl(report && (report.gradcam_url || report.attention_url || report.explanation_image_url));

    gradcamImage.onload = null;
    gradcamImage.onerror = null;
    gradcamImage.removeAttribute('src');
    gradcamImage.alt = 'Grad-CAM attention preview unavailable for this analysis';
    setHidden(gradcamImage, true);
    setHidden(gradcamFallback, false);
    gradcamFallback.textContent = defaultFallback;

    if (!imageUrl) return;

    gradcamImage.alt = 'Grad-CAM attention preview showing model attention regions for the analyzed retinal scan';
    gradcamImage.onload = () => {
        setHidden(gradcamImage, false);
        setHidden(gradcamFallback, true);
    };
    gradcamImage.onerror = () => {
        setHidden(gradcamImage, true);
        setHidden(gradcamFallback, false);
        gradcamFallback.textContent = 'The Grad-CAM attention preview could not be loaded.';
    };
    gradcamImage.src = imageUrl;
}

function renderReport(report) {
    lastReport = report && typeof report === 'object' && !Array.isArray(report) ? report : null;
    const metadata = lastReport || {};
    if (reportPatientId) reportPatientId.textContent = formatReportValue(metadata.patient_id || metadata.patient_label, 'Not assigned');
    if (reportModelVersion) reportModelVersion.textContent = formatReportValue(metadata.model_version);
    if (reportTimestamp) {
        reportTimestamp.textContent = metadata.timestamp
            ? formatDate(metadata.timestamp, true)
            : 'Not available';
    }
    if (reportImageQuality) reportImageQuality.textContent = formatImageQualityScore(metadata.image_quality_score);
    renderGradcam(lastReport);

    const availableArtifacts = lastReport
        ? Object.values(REPORT_ARTIFACTS).filter(artifact => resolveReportUrl(lastReport[artifact.field]))
        : [];
    const metadataComplete = lastReport
        ? ['model_version', 'timestamp', 'image_quality_score']
            .every(field => metadata[field] !== null && metadata[field] !== undefined && String(metadata[field]).trim() !== '')
        : false;
    const attentionAvailable = Boolean(resolveReportUrl(metadata.gradcam_url || metadata.attention_url || metadata.explanation_image_url));
    if (!lastReport) {
        setReportAvailabilityStatus('Report metadata unavailable', 'error');
        setReportActionStatus('This analysis did not return report metadata. PDF, CSV, and JSON downloads are unavailable.', 'error');
    } else if (!availableArtifacts.length) {
        setReportAvailabilityStatus('Report metadata returned · no downloads available', 'error');
        setReportActionStatus('Report metadata was returned, but the backend did not provide download URLs for this analysis.', 'error');
    } else {
        const artifactCount = availableArtifacts.length;
        const attentionMessage = attentionAvailable ? '' : ' · attention preview unavailable';
        const metadataMessage = metadataComplete ? '' : ' · some metadata unavailable';
        setReportAvailabilityStatus(`${artifactCount} report artifact${artifactCount === 1 ? '' : 's'} available${attentionMessage}${metadataMessage}`, metadataComplete ? 'ready' : 'error');
        setReportActionStatus(
            metadataComplete
                ? 'Report metadata loaded. Choose an artifact to download.'
                : 'Report metadata is incomplete; unavailable fields are marked accordingly. Choose an artifact to download.',
            metadataComplete ? 'info' : 'error',
        );
    }
}

async function refreshAfterSavedScan(patientId) {
    const normalized = normalizeId(patientId);
    patientState.selectedId = normalized;
    await loadPatients({ selectId: normalized, selectFirst: true, force: true });
    if (!patientState.loaded || !patientById(normalized)) throw new Error('The patient list could not be refreshed.');
    await loadPatientProfile(normalized);
    if (!patientState.selectedProfile) throw new Error('The patient profile could not be refreshed.');
}

function handlePersistenceResponse(data, context, requestId = scanRequestId) {
    const isCurrentScan = () => requestId === scanRequestId;
    if (!context.saveScan) {
        if (!isCurrentScan()) return;
        setPredictionSaveStatus('Quick analysis complete. No patient profile was selected, so this scan was not saved.', 'info');
        setHidden(viewHistoryBtn, true);
        return;
    }
    const scan = data && data.scan && typeof data.scan === 'object' ? data.scan : data;
    const saved = Boolean(
        (scan && (scan.saved === true || scan.saved === 'true'))
        || (data && (data.saved === true || data.saved === 'true'))
    );
    if (!isCurrentScan()) return;
    if (!scan || !saved) {
        setPredictionSaveStatus('Analysis completed, but the API did not confirm that this scan was saved. It is not shown in patient history.', 'error');
        setHidden(viewHistoryBtn, true);
        return;
    }
    const patient = patientById(context.patientId);
    setPredictionSaveStatus(`Saved to ${patient ? patient.name : `patient ${context.patientId}`}. Patient history is refreshing.`, 'success');
    setHidden(viewHistoryBtn, false);
    void refreshAfterSavedScan(context.patientId).then(() => {
        if (!isCurrentScan()) return;
        // Monitoring refreshes must not replace the active diagnosis result.
        showSection(resultsSection);
        setPredictionSaveStatus(`Saved to ${patient ? patient.name : `patient ${context.patientId}`}. History is up to date.`, 'success');
    }).catch(error => {
        if (!isCurrentScan()) return;
        showSection(resultsSection);
        setPredictionSaveStatus(`The API confirmed the scan save, but history could not refresh: ${errorMessage(error)}`, 'error');
    });
}

function getScanContext() {
    const patientId = patientSelect ? patientSelect.value : '';
    return {
        patientId: patientId || '',
        scanDate: scanDate && scanDate.value ? scanDate.value : todayIso(),
        eye: scanEye && scanEye.value ? scanEye.value : 'Unknown',
        notes: scanNotes ? scanNotes.value.trim() : '',
        saveScan: Boolean(patientId),
    };
}

function showSection(section) {
    [uploadSection, loadingSection, resultsSection, errorSection].filter(Boolean).forEach(item => item.classList.add('hidden'));
    if (section) section.classList.remove('hidden');
}

function startLoadingSteps() {
    let index = 0;
    if (loadingStep) loadingStep.textContent = LOADING_STEPS[0];
    stopLoadingSteps();
    stepInterval = window.setInterval(() => {
        index = (index + 1) % LOADING_STEPS.length;
        if (loadingStep) loadingStep.textContent = LOADING_STEPS[index];
    }, 1200);
}

function stopLoadingSteps() {
    if (stepInterval !== null) window.clearInterval(stepInterval);
    stepInterval = null;
}

async function handleFile(file) {
    const fileType = file && typeof file.type === 'string' ? file.type : '';
    if (!file || !fileType.startsWith('image/')) {
        showError('Invalid File', 'Please upload a retinal fundus image (JPG, PNG, or BMP).');
        return;
    }
    if (file.size > 20 * 1024 * 1024) {
        showError('File Too Large', 'Maximum allowed file size is 20 MB.');
        return;
    }

    const requestId = ++scanRequestId;
    lastFile = file;
    lastReport = null;
    setReportButtonsBusy(false);
    lastScanContext = getScanContext();
    const reader = new FileReader();
    reader.onload = event => {
        const source = event && event.target ? event.target.result : '';
        if (previewImage) previewImage.src = source;
        if (scanPreviewLoad) scanPreviewLoad.src = source;
    };
    reader.readAsDataURL(file);

    showSection(loadingSection);
    startLoadingSteps();
    const formData = new FormData();
    formData.append('file', file);
    if (lastScanContext.patientId) formData.append('patient_id', lastScanContext.patientId);
    if (lastScanContext.scanDate) formData.append('scan_date', lastScanContext.scanDate);
    if (lastScanContext.eye) formData.append('eye', lastScanContext.eye);
    if (lastScanContext.notes) formData.append('notes', lastScanContext.notes);
    formData.append('save_scan', String(lastScanContext.saveScan));

    try {
        const data = await apiRequest('/predict', { method: 'POST', body: formData });
        if (requestId !== scanRequestId) return;
        stopLoadingSteps();
        if (!data || !data.prediction) throw new Error('The API response did not include a prediction.');
        lastPrediction = data.prediction;
        if (filenameLbl) filenameLbl.textContent = file.name;
        showResults(data.prediction);
        renderReport(data.report);
        handlePersistenceResponse(data, lastScanContext, requestId);
    } catch (error) {
        if (requestId !== scanRequestId) return;
        stopLoadingSteps();
        console.error(error);
        showError('Image Not Accepted', errorMessage(error, `Could not reach the AI backend at ${API_BASE}.`));
    }
}

function showResults(prediction) {
    const gradeIdx = gradeIndex(prediction && prediction.grade_idx, prediction && prediction.grade_name) ?? 0;
    const gradeName = prediction && prediction.grade_name ? prediction.grade_name : CLASS_NAMES[gradeIdx];
    const color = GRADE_COLORS[gradeIdx] || GRADE_COLORS[0];
    if (drGrade) {
        drGrade.textContent = gradeName;
        drGrade.className = `dr-grade grade-${gradeIdx}`;
    }
    if (gradeBadge) gradeBadge.textContent = `Grade ${gradeIdx}`;
    if (diagnosisIcon) {
        diagnosisIcon.style.background = `${color}1a`;
        diagnosisIcon.style.borderColor = `${color}40`;
        const icon = diagnosisIcon.querySelector('svg');
        if (icon) icon.style.color = color;
    }
    const confidence = Number(prediction && prediction.confidence);
    const normalizedConfidence = Number.isFinite(confidence) ? Math.max(0, Math.min(1, confidence > 1 ? confidence / 100 : confidence)) : 0;
    const pct = (normalizedConfidence * 100).toFixed(1);
    if (confidenceFill) confidenceFill.style.width = '0%';
    if (confidenceText) confidenceText.textContent = `${pct}%`;
    window.setTimeout(() => confidenceFill && (confidenceFill.style.width = `${pct}%`), 120);

    if (probBars) {
        probBars.replaceChildren();
        const probabilities = Array.isArray(prediction && prediction.probabilities) ? prediction.probabilities : [];
        probabilities.forEach((probability, index) => {
            const number = Number(probability);
            const normalized = Number.isFinite(number) ? Math.max(0, Math.min(1, number > 1 ? number / 100 : number)) : 0;
            const pPct = (normalized * 100).toFixed(1);
            const isTop = index === gradeIdx;
            const row = document.createElement('div');
            row.className = 'prob-row';
            const name = document.createElement('span');
            name.className = 'prob-name';
            name.textContent = CLASS_NAMES[index] || `Grade ${index}`;
            if (isTop) {
                name.style.color = GRADE_COLORS[index] || color;
                name.style.fontWeight = '800';
            }
            const track = document.createElement('div');
            track.className = 'prob-track';
            const fill = document.createElement('div');
            fill.className = 'prob-fill';
            fill.dataset.pct = pPct;
            fill.style.background = `${GRADE_COLORS[index] || color}${isTop ? '' : '77'}`;
            track.appendChild(fill);
            const percent = document.createElement('span');
            percent.className = 'prob-pct';
            percent.textContent = `${pPct}%`;
            if (isTop) percent.style.color = GRADE_COLORS[index] || color;
            row.append(name, track, percent);
            probBars.appendChild(row);
        });
        showSection(resultsSection);
        requestAnimationFrame(() => requestAnimationFrame(() => {
            probBars.querySelectorAll('.prob-fill').forEach(fill => {
                fill.style.width = `${fill.dataset.pct}%`;
            });
        }));
    } else {
        showSection(resultsSection);
    }
}

function showError(title, message) {
    const titleEl = byId('error-title');
    const messageEl = byId('error-msg');
    if (titleEl) titleEl.textContent = title;
    if (messageEl) messageEl.textContent = message;
    showSection(errorSection);
}

function reset() {
    scanRequestId += 1;
    stopLoadingSteps();
    showSection(uploadSection);
    if (fileInput) fileInput.value = '';
    if (predictionSaveStatus) setHidden(predictionSaveStatus, true);
    if (reportActionStatus) setHidden(reportActionStatus, true);
    setReportButtonsBusy(false);
    setHidden(viewHistoryBtn, true);
    lastFile = null;
    lastPrediction = null;
    lastReport = null;
    lastScanContext = null;
}

function reportFilename(report, artifact) {
    const rawId = normalizeId(report && report.report_id);
    const safeId = rawId.replace(/[^a-z0-9._-]+/gi, '_').replace(/^\.+|\.+$/g, '').slice(0, 80);
    const id = safeId || String(Date.now());
    return `retinascan_${artifact.extension === 'pdf' ? 'report' : 'research'}_${id}.${artifact.extension}`;
}

async function downloadArtifact(type) {
    const artifact = REPORT_ARTIFACTS[type];
    if (!artifact) return;
    const requestId = scanRequestId;
    const report = lastReport;
    if (!report) {
        setReportActionStatus(`The ${artifact.label} is unavailable because report metadata was not returned for this analysis.`, 'error');
        return;
    }
    const url = resolveReportUrl(report[artifact.field]);
    if (!url) {
        setReportActionStatus(`The ${artifact.label} is unavailable because the backend did not provide a download URL.`, 'error');
        return;
    }

    setReportButtonsBusy(true);
    setReportActionStatus(`Preparing ${artifact.label}…`, 'info');
    try {
        const response = await fetch(url);
        if (!response.ok) throw new Error(`The backend returned status ${response.status}.`);
        const blob = await response.blob();
        if (!blob || blob.size === 0) throw new Error('The backend returned an empty file.');
        const objectUrl = URL.createObjectURL(blob);
        const anchor = document.createElement('a');
        anchor.href = objectUrl;
        anchor.download = reportFilename(report, artifact);
        document.body.appendChild(anchor);
        anchor.click();
        anchor.remove();
        window.setTimeout(() => URL.revokeObjectURL(objectUrl), 0);
        if (requestId === scanRequestId) setReportActionStatus(`${artifact.label} download started.`, 'success');
    } catch (error) {
        if (requestId === scanRequestId) {
            setReportActionStatus(`${artifact.label} download failed. ${errorMessage(error, 'Please try again.')}`, 'error');
        }
    } finally {
        if (requestId === scanRequestId) setReportButtonsBusy(false);
    }
}

function downloadReport() {
    return downloadArtifact('pdf');
}

function downloadCsvExport() {
    return downloadArtifact('csv');
}

function downloadJsonExport() {
    return downloadArtifact('json');
}

function startNewScan() {
    scanRequestId += 1;
    stopLoadingSteps();
    const selected = normalizeId(patientState.selectedId);
    if (selected) {
        patientState.selectedId = selected;
        renderPatientSelector();
        renderPatientList();
    }
    switchPage('diagnose');
    showSection(uploadSection);
    window.setTimeout(() => dropZone && dropZone.focus(), 0);
}

function switchPage(name) {
    const pageName = pages.includes(name) ? name : pages[0];
    pages.forEach(pageNameItem => {
        const page = byId(`page-${pageNameItem}`);
        if (page) page.classList.toggle('hidden', pageNameItem !== pageName);
    });
    document.querySelectorAll('[data-page]').forEach(nav => {
        const isActive = nav.dataset.page === pageName;
        nav.classList.toggle('active', isActive);
        if (isActive) nav.setAttribute('aria-current', 'page');
        else nav.removeAttribute('aria-current');
    });
    if (pageName === 'about') drawCharts();
    if (pageName === 'history') {
        void loadPatients({ selectFirst: true }).then(() => {
            if (patientState.selectedId && patientState.selectedProfile) renderPatientDetail(patientState.selectedProfile);
            else if (patientState.selectedId) void loadPatientProfile(patientState.selectedId);
        });
    }
}

window.switchPage = switchPage;

document.addEventListener('click', event => {
    const target = event.target;
    const nav = target && typeof target.closest === 'function' ? target.closest('[data-page]') : null;
    if (!nav || !nav.dataset.page) return;
    event.preventDefault();
    switchPage(nav.dataset.page);
});

async function checkApiHealth() {
    if (!apiStatusDot || !apiStatusLabel) return;
    try {
        const options = typeof AbortSignal !== 'undefined' && typeof AbortSignal.timeout === 'function'
            ? { signal: AbortSignal.timeout(4000) }
            : {};
        const response = await fetch(`${API_BASE}/`, options);
        if (!response.ok) throw new Error('bad status');
        apiStatusDot.className = 'status-dot online';
        apiStatusLabel.textContent = 'API Online';
    } catch {
        apiStatusDot.className = 'status-dot offline';
        apiStatusLabel.textContent = 'API Offline';
    }
}

if (scanDate && !scanDate.value) scanDate.value = todayIso();
updateScanSaveMode();

if (patientSelect) patientSelect.addEventListener('change', () => {
    patientState.selectedId = patientSelect.value;
    patientState.selectedProfile = null;
    renderPatientList();
    updateScanSaveMode();
    if (patientState.selectedId && isHistoryVisible()) void loadPatientProfile(patientState.selectedId);
});
if (patientSearch) patientSearch.addEventListener('input', () => {
    patientState.filter = patientSearch.value;
    renderPatientList();
});
['new-patient-btn', 'sidebar-new-patient-btn', 'empty-create-patient-btn'].forEach(id => {
    const button = byId(id);
    if (button) button.addEventListener('click', openPatientDialog);
});
const closeDialogBtn = byId('close-patient-dialog-btn');
const cancelDialogBtn = byId('cancel-patient-btn');
if (closeDialogBtn) closeDialogBtn.addEventListener('click', closePatientDialog);
if (cancelDialogBtn) cancelDialogBtn.addEventListener('click', closePatientDialog);
if (patientForm) patientForm.addEventListener('submit', createPatient);
const refreshPatientsBtn = byId('refresh-patients-btn');
if (refreshPatientsBtn) refreshPatientsBtn.addEventListener('click', () => loadPatients({ selectFirst: true, force: true }));
const retryPatientBtn = byId('retry-patient-btn');
if (retryPatientBtn) retryPatientBtn.addEventListener('click', () => loadPatientProfile(patientState.selectedId));
const patientBackBtn = byId('patient-back-btn');
if (patientBackBtn) patientBackBtn.addEventListener('click', () => {
    patientState.selectedId = '';
    patientState.selectedProfile = null;
    renderPatientList();
    renderPatientSelector();
    showDetailState('empty');
});
const newScanBtn = byId('new-scan-btn');
if (newScanBtn) newScanBtn.addEventListener('click', startNewScan);
if (viewHistoryBtn) viewHistoryBtn.addEventListener('click', () => {
    switchPage('history');
    if (patientState.selectedId) void loadPatientProfile(patientState.selectedId);
});

if (dropZone && fileInput) {
    dropZone.addEventListener('click', () => fileInput.click());
    dropZone.addEventListener('keydown', event => {
        if (event.key === 'Enter' || event.key === ' ') {
            event.preventDefault();
            fileInput.click();
        }
    });
    dropZone.addEventListener('dragover', event => { event.preventDefault(); dropZone.classList.add('dragover'); });
    dropZone.addEventListener('dragleave', () => dropZone.classList.remove('dragover'));
    dropZone.addEventListener('drop', event => {
        event.preventDefault();
        dropZone.classList.remove('dragover');
        const file = event.dataTransfer && event.dataTransfer.files ? event.dataTransfer.files[0] : null;
        if (file) void handleFile(file);
    });
    fileInput.addEventListener('change', event => {
        const file = event.target && event.target.files ? event.target.files[0] : null;
        if (file) void handleFile(file);
    });
}
if (resetBtn) resetBtn.addEventListener('click', reset);
if (retryBtn) retryBtn.addEventListener('click', () => {
    showSection(uploadSection);
    if (lastFile) void handleFile(lastFile);
});
if (downloadBtn) downloadBtn.addEventListener('click', downloadReport);
if (downloadCsvBtn) downloadCsvBtn.addEventListener('click', downloadCsvExport);
if (downloadJsonBtn) downloadJsonBtn.addEventListener('click', downloadJsonExport);

checkApiHealth();
window.setInterval(checkApiHealth, 15000);
void loadPatients({ selectFirst: false });

const TRAIN_DATA = {
    epochs: [1, 2, 3, 4, 5, 6, 7, 8, 9],
    trainLoss: [1.092, 0.741, 0.665, 0.638, 0.604, 0.633, 0.462, 0.371, 0.308],
    valLoss: [0.371, 0.336, 0.300, 0.299, 0.297, 0.304, 0.279, 0.300, 0.242],
    trainKappa: [0.417, 0.485, 0.491, 0.448, 0.503, 0.557, 0.677, 0.713, 0.751],
    valKappa: [0.578, 0.614, 0.612, 0.616, 0.652, 0.666, 0.689, 0.658, 0.701],
    trainAcc: [36.2, 38.4, 39.8, 38.5, 41.1, 40.7, 51.5, 56.5, 60.4],
    valAcc: [47.4, 44.4, 40.3, 43.9, 43.5, 37.3, 35.3, 44.6, 55.0],
};

function drawCharts() {
    drawLineChart('lossChart', [
        { label: 'Train Loss', data: TRAIN_DATA.trainLoss, color: GRADE_COLORS[0] },
        { label: 'Val Loss', data: TRAIN_DATA.valLoss, color: GRADE_COLORS[1] },
    ], { min: 0, max: 1.2, suffix: '' });
    drawLineChart('kappaChart', [
        { label: 'Train κ', data: TRAIN_DATA.trainKappa, color: GRADE_COLORS[2] },
        { label: 'Val κ', data: TRAIN_DATA.valKappa, color: GRADE_COLORS[3] },
    ], { min: 0, max: 1.0, suffix: '' });
    drawLineChart('accChart', [
        { label: 'Train Acc', data: TRAIN_DATA.trainAcc, color: GRADE_COLORS[4] },
        { label: 'Val Acc', data: TRAIN_DATA.valAcc, color: GRADE_COLORS[0] },
    ], { min: 0, max: 100, suffix: '%' });
}

function drawLineChart(canvasId, series, { min = 0, max = 1, suffix = '' } = {}) {
    const canvas = byId(canvasId);
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;
    const width = canvas.offsetWidth || 300;
    const height = canvas.offsetHeight || 160;
    const dpr = Math.max(window.devicePixelRatio || 1, 1);
    canvas.width = Math.max(1, Math.round(width * dpr));
    canvas.height = Math.max(1, Math.round(height * dpr));
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    const pad = { top: 16, right: 20, bottom: 32, left: 38 };
    const plotWidth = width - pad.left - pad.right;
    const plotHeight = height - pad.top - pad.bottom;
    const n = TRAIN_DATA.epochs.length;
    ctx.fillStyle = 'rgba(0,0,0,0)';
    ctx.fillRect(0, 0, width, height);
    const gridCount = 4;
    for (let i = 0; i <= gridCount; i += 1) {
        const y = pad.top + (plotHeight / gridCount) * i;
        ctx.strokeStyle = 'rgba(148,163,184,0.08)';
        ctx.lineWidth = 1;
        ctx.beginPath();
        ctx.moveTo(pad.left, y);
        ctx.lineTo(pad.left + plotWidth, y);
        ctx.stroke();
        const value = max - ((max - min) / gridCount) * i;
        ctx.fillStyle = 'rgba(100,130,160,0.8)';
        ctx.font = '9px Inter, sans-serif';
        ctx.textAlign = 'right';
        ctx.fillText(value.toFixed(suffix === '%' ? 0 : 2) + suffix, pad.left - 5, y + 3);
    }
    ctx.fillStyle = 'rgba(100,130,160,0.8)';
    ctx.textAlign = 'center';
    TRAIN_DATA.epochs.forEach((epoch, index) => {
        const x = pad.left + (plotWidth / (n - 1)) * index;
        ctx.fillText(epoch, x, height - pad.bottom + 14);
    });
    ctx.fillStyle = 'rgba(100,130,160,0.5)';
    ctx.font = '9px Inter, sans-serif';
    ctx.fillText('Epoch', pad.left + plotWidth / 2, height - 4);
    series.forEach(({ data, color }) => {
        const xOf = index => pad.left + (plotWidth / (n - 1)) * index;
        const yOf = value => pad.top + plotHeight - ((value - min) / (max - min)) * plotHeight;
        const gradient = ctx.createLinearGradient(0, pad.top, 0, pad.top + plotHeight);
        gradient.addColorStop(0, `${color}33`);
        gradient.addColorStop(1, `${color}00`);
        ctx.beginPath();
        ctx.moveTo(xOf(0), yOf(data[0]));
        for (let i = 1; i < n; i += 1) ctx.lineTo(xOf(i), yOf(data[i]));
        ctx.lineTo(xOf(n - 1), pad.top + plotHeight);
        ctx.lineTo(xOf(0), pad.top + plotHeight);
        ctx.closePath();
        ctx.fillStyle = gradient;
        ctx.fill();
        ctx.beginPath();
        ctx.strokeStyle = color;
        ctx.lineWidth = 2.2;
        ctx.lineJoin = 'round';
        ctx.lineCap = 'round';
        ctx.moveTo(xOf(0), yOf(data[0]));
        for (let i = 1; i < n; i += 1) ctx.lineTo(xOf(i), yOf(data[i]));
        ctx.stroke();
        data.forEach((value, index) => {
            ctx.beginPath();
            ctx.arc(xOf(index), yOf(value), index === n - 1 ? 4 : 3, 0, Math.PI * 2);
            ctx.fillStyle = index === n - 1 ? color : 'rgba(6,10,26,0.9)';
            ctx.strokeStyle = color;
            ctx.lineWidth = 1.8;
            ctx.fill();
            ctx.stroke();
        });
    });
    const legendX = pad.left + plotWidth - series.length * 75 + 10;
    series.forEach(({ label, color }, index) => {
        const x = legendX + index * 75;
        ctx.beginPath();
        ctx.strokeStyle = color;
        ctx.lineWidth = 2;
        ctx.moveTo(x, pad.top + 6);
        ctx.lineTo(x + 14, pad.top + 6);
        ctx.stroke();
        ctx.fillStyle = 'rgba(100,130,160,0.9)';
        ctx.textAlign = 'left';
        ctx.font = '9px Inter, sans-serif';
        ctx.fillText(label, x + 18, pad.top + 10);
    });
}

let chartResizeFrame = null;
window.addEventListener('resize', () => {
    if (chartResizeFrame !== null) cancelAnimationFrame(chartResizeFrame);
    chartResizeFrame = requestAnimationFrame(() => {
        chartResizeFrame = null;
        const aboutPage = byId('page-about');
        if (aboutPage && !aboutPage.classList.contains('hidden')) drawCharts();
    });
});

const initialNav = Array.from(document.querySelectorAll('[data-page]')).find(nav => nav.classList.contains('active'));
switchPage(initialNav ? initialNav.dataset.page : pages[0]);
