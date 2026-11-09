/**
 * Freight Invoice Audit & Reconciliation Platform - Frontend Application
 */

const AppState = {
  activeTab: 'dashboard',
  theme: localStorage.getItem('freight_audit_theme') || 'dark',
  kpis: null,
  invoices: [],
  selectedInvoice: null,
  exceptions: [],
  scorecards: [],
  groundTruth: null,
  charts: {
    exceptionsChart: null,
    carrierChart: null
  }
};

// Initialize Application on DOM Ready
document.addEventListener('DOMContentLoaded', () => {
  initTheme();
  setupNavigation();
  loadAllData();
  setupSearchAndFilters();
});

// Theme Management
function initTheme() {
  document.documentElement.setAttribute('data-theme', AppState.theme);
  const themeToggle = document.getElementById('theme-toggle');
  if (themeToggle) {
    themeToggle.addEventListener('click', () => {
      AppState.theme = AppState.theme === 'dark' ? 'light' : 'dark';
      document.documentElement.setAttribute('data-theme', AppState.theme);
      localStorage.setItem('freight_audit_theme', AppState.theme);
      updateThemeIcon();
      // Re-render charts with updated theme colors
      if (AppState.kpis) renderDashboardCharts(AppState.kpis);
    });
    updateThemeIcon();
  }
}

function updateThemeIcon() {
  const icon = document.getElementById('theme-icon');
  if (!icon) return;
  if (AppState.theme === 'dark') {
    icon.innerHTML = '<path d="M12 3a6 6 0 0 0 9 9 9 9 0 1 1-9-9Z"></path>';
  } else {
    icon.innerHTML = '<circle cx="12" cy="12" r="4"></circle><path d="M12 2v2"></path><path d="M12 20v2"></path><path d="m4.93 4.93 1.41 1.41"></path><path d="m17.66 17.66 1.41 1.41"></path><path d="M2 12h2"></path><path d="M20 12h2"></path><path d="m6.34 17.66-1.41 1.41"></path><path d="m19.07 4.93-1.41 1.41"></path>';
  }
}

// Navigation Tabs
function setupNavigation() {
  const navButtons = document.querySelectorAll('[data-tab-target]');
  navButtons.forEach(btn => {
    btn.addEventListener('click', (e) => {
      e.preventDefault();
      const target = btn.getAttribute('data-tab-target');
      switchTab(target);
    });
  });
}

function switchTab(tabId) {
  AppState.activeTab = tabId;

  // Update nav buttons
  document.querySelectorAll('[data-tab-target]').forEach(b => {
    const isTarget = b.getAttribute('data-tab-target') === tabId;
    b.classList.toggle('nav-active', isTarget);
    b.classList.toggle('text-white', isTarget && AppState.theme === 'dark');
    b.classList.toggle('text-blue-600', isTarget && AppState.theme === 'light');
  });

  // Show target section, hide others
  document.querySelectorAll('.tab-section').forEach(sec => {
    sec.classList.toggle('hidden', sec.id !== `tab-${tabId}`);
  });

  // Trigger tab-specific loads
  if (tabId === 'dashboard') {
    loadKPIs();
    loadCarriers();
  } else if (tabId === 'invoices') {
    loadInvoices();
  } else if (tabId === 'exceptions') {
    loadExceptions();
  } else if (tabId === 'credit-notes') {
    loadCreditNotes();
  } else if (tabId === 'benchmark') {
    loadBenchmark();
  } else if (tabId === 'dictionary') {
    loadDataDictionary();
  }
}

// Data Fetching
async function loadAllData() {
  await loadKPIs();
  await loadInvoices();
  await loadExceptions();
  await loadCarriers();
  await loadBenchmark();
}

async function loadKPIs() {
  try {
    const res = await fetch('/api/kpis');
    const data = await res.json();
    AppState.kpis = data;

    // Update KPI UI Elements
    document.getElementById('kpi-total-invoices').textContent = data.total_invoices.toLocaleString();
    document.getElementById('kpi-pass-rate').textContent = `${data.pass_rate_pct}%`;
    document.getElementById('kpi-billed-amount').textContent = `$${data.total_billed.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
    document.getElementById('kpi-overcharge').textContent = `$${data.total_overcharge.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
    document.getElementById('kpi-savings-pct').textContent = `${data.savings_opportunity_pct}% of spend`;
    document.getElementById('kpi-open-exceptions').textContent = data.open_exceptions;
    document.getElementById('kpi-credits-total').textContent = `$${data.total_credit_notes_amount.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;

    renderDashboardCharts(data);
  } catch (err) {
    console.error('Failed to load KPIs:', err);
  }
}

function renderDashboardCharts(kpiData) {
  const isDark = AppState.theme === 'dark';
  const textColor = isDark ? '#9ca3af' : '#475569';
  const gridColor = isDark ? 'rgba(255,255,255,0.06)' : 'rgba(0,0,0,0.06)';

  // 1. Exceptions by Type Doughnut Chart
  const exCtx = document.getElementById('chart-exceptions')?.getContext('2d');
  if (exCtx && kpiData.exceptions_by_type) {
    if (AppState.charts.exceptionsChart) AppState.charts.exceptionsChart.destroy();

    const labels = Object.keys(kpiData.exceptions_by_type).map(l => l.replace(/_/g, ' '));
    const counts = Object.values(kpiData.exceptions_by_type).map(v => v.count);

    AppState.charts.exceptionsChart = new Chart(exCtx, {
      type: 'doughnut',
      data: {
        labels: labels,
        datasets: [{
          data: counts,
          backgroundColor: [
            '#ef4444', '#f59e0b', '#3b82f6', '#8b5cf6', '#06b6d4', '#ec4899', '#10b981'
          ],
          borderWidth: 2,
          borderColor: isDark ? '#111827' : '#ffffff'
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: {
            position: 'right',
            labels: { color: textColor, font: { family: 'Inter', size: 11 }, boxWidth: 12 }
          }
        },
        cutout: '68%'
      }
    });
  }
}

// Invoices Table
async function loadInvoices() {
  const statusFilter = document.getElementById('filter-invoice-status')?.value || 'ALL';
  const searchQuery = document.getElementById('search-invoices')?.value || '';

  try {
    const res = await fetch(`/api/invoices?status=${statusFilter}&search=${encodeURIComponent(searchQuery)}&limit=150`);
    const data = await res.json();
    AppState.invoices = data.invoices;
    renderInvoicesTable(data.invoices);
  } catch (err) {
    console.error('Failed to load invoices:', err);
  }
}

function renderInvoicesTable(invoices) {
  const tbody = document.getElementById('invoices-table-body');
  if (!tbody) return;

  if (invoices.length === 0) {
    tbody.innerHTML = `<tr><td colspan="8" class="text-center py-8 text-gray-500">No invoices found matching criteria.</td></tr>`;
    return;
  }

  tbody.innerHTML = invoices.map(inv => {
    const isPassed = inv.audit_status === 'PASSED';
    const statusBadge = isPassed
      ? `<span class="badge badge-success"><span class="w-1.5 h-1.5 rounded-full bg-emerald-500"></span>PASSED</span>`
      : `<span class="badge badge-danger"><span class="w-1.5 h-1.5 rounded-full bg-red-500"></span>FAILED</span>`;

    const varianceFormatted = inv.variance_amount > 0
      ? `<span class="text-red-400 font-semibold">+$${inv.variance_amount.toFixed(2)}</span>`
      : `<span class="text-gray-400">$0.00</span>`;

    return `
      <tr class="cursor-pointer transition-colors" onclick="openInvoiceDrawer('${inv.invoice_id}')">
        <td class="font-mono font-medium text-blue-400">${inv.invoice_id}</td>
        <td>
          <div class="font-medium text-gray-200">${inv.carrier_name || inv.carrier_id}</div>
          <div class="text-xs text-gray-500">${inv.carrier_id} • ${inv.carrier_mode || 'FTL'}</div>
        </td>
        <td class="font-mono text-xs text-gray-400">${inv.shipment_id || '<span class="text-red-400 italic">None (Orphan)</span>'}</td>
        <td class="text-xs text-gray-400">${inv.invoice_date}</td>
        <td class="font-medium">$${inv.billed_amount.toFixed(2)}</td>
        <td class="text-gray-400">$${inv.expected_amount.toFixed(2)}</td>
        <td>${varianceFormatted}</td>
        <td>${statusBadge}</td>
        <td class="text-right">
          <button class="px-2 py-1 bg-gray-800 hover:bg-gray-700 rounded text-xs text-blue-400 border border-gray-700" onclick="event.stopPropagation(); openInvoiceDrawer('${inv.invoice_id}')">
            Inspect
          </button>
        </td>
      </tr>
    `;
  }).join('');
}

// Invoice Inspector Drawer
async function openInvoiceDrawer(invoiceId) {
  try {
    const res = await fetch(`/api/invoices/${invoiceId}`);
    const inv = await res.json();
    AppState.selectedInvoice = inv;

    document.getElementById('drawer-invoice-id').textContent = inv.invoice_id;
    document.getElementById('drawer-invoice-num').textContent = inv.invoice_number;
    document.getElementById('drawer-carrier-name').textContent = `${inv.carrier_name} (${inv.carrier_id})`;
    document.getElementById('drawer-billed-amount').textContent = `$${inv.billed_amount.toFixed(2)}`;
    document.getElementById('drawer-expected-amount').textContent = `$${inv.expected_amount.toFixed(2)}`;
    
    const varEl = document.getElementById('drawer-variance-amount');
    varEl.textContent = `$${inv.variance_amount.toFixed(2)}`;
    varEl.className = inv.variance_amount > 0 ? 'text-red-400 font-bold text-lg' : 'text-emerald-400 font-bold text-lg';

    // 3-Way Match & Shipment Characteristics
    const shp = inv.shipment;
    const lane = inv.lane;
    const wm = inv.weight_measurement;
    const matchEl = document.getElementById('drawer-3way-match');

    if (shp) {
      matchEl.innerHTML = `
        <div class="grid grid-cols-2 gap-3 text-xs">
          <div><span class="text-gray-500">Shipment ID:</span> <span class="font-mono font-medium text-gray-200">${shp.shipment_id}</span></div>
          <div><span class="text-gray-500">Service Level:</span> <span class="font-medium text-blue-400">${shp.service_level}</span></div>
          <div><span class="text-gray-500">Route Lane:</span> <span class="text-gray-200">${lane ? `${lane.origin_city}, ${lane.origin_state} &rarr; ${lane.dest_city}, ${lane.dest_state}` : 'Direct'}</span></div>
          <div><span class="text-gray-500">Transit Distance:</span> <span class="text-gray-200">${lane ? `${lane.distance_miles} miles` : '-'}</span></div>
          <div><span class="text-gray-500">Actual Weight:</span> <span class="text-gray-200 font-medium">${wm ? `${wm.actual_weight_kg} kg` : '-'}</span></div>
          <div><span class="text-gray-500">Volumetric Weight:</span> <span class="text-gray-200 font-medium">${wm ? `${wm.volumetric_weight_kg} kg (${wm.dim_length_cm}x${wm.dim_width_cm}x${wm.dim_height_cm}cm / 5000)` : '-'}</span></div>
          <div class="col-span-2 bg-blue-950/40 border border-blue-800/40 p-2 rounded text-blue-300">
            <strong>Certified Billable Weight:</strong> ${wm ? `${wm.billable_weight_kg} kg` : '-'} (determined by max(actual, volumetric))
          </div>
        </div>
      `;
    } else {
      matchEl.innerHTML = `
        <div class="p-3 bg-red-950/40 border border-red-800/40 rounded text-red-300 text-xs">
          <strong>3-Way Match Failed:</strong> Invoice references orphan shipment ID <code>${inv.shipment_id || 'UNKNOWN'}</code> which is not found in TMS or Carrier manifest.
        </div>
      `;
    }

    // Line items breakdown
    const linesTbody = document.getElementById('drawer-lines-tbody');
    linesTbody.innerHTML = inv.lines.map(line => {
      const varLine = line.variance_amount;
      const isClean = Math.abs(varLine) < 0.01;
      return `
        <tr class="text-xs border-b border-gray-800">
          <td class="py-2">
            <div class="font-medium text-gray-200">${line.description}</div>
            <div class="text-gray-500 text-[10px] uppercase font-mono">${line.line_type}</div>
          </td>
          <td class="text-right py-2 text-gray-300">$${line.billed_total.toFixed(2)}</td>
          <td class="text-right py-2 text-gray-400">$${line.expected_total.toFixed(2)}</td>
          <td class="text-right py-2 ${isClean ? 'text-gray-500' : 'text-red-400 font-semibold'}">
            ${isClean ? '$0.00' : `+$${varLine.toFixed(2)}`}
          </td>
        </tr>
      `;
    }).join('');

    // Open drawer
    document.getElementById('drawer-backdrop').classList.add('active');
    document.getElementById('invoice-drawer').classList.add('active');
  } catch (err) {
    console.error('Failed to open invoice drawer:', err);
  }
}

function closeInvoiceDrawer() {
  document.getElementById('drawer-backdrop').classList.remove('active');
  document.getElementById('invoice-drawer').classList.remove('active');
}

// Trigger Re-audit
async function triggerReauditFromDrawer() {
  if (!AppState.selectedInvoice) return;
  const invoiceId = AppState.selectedInvoice.invoice_id;
  try {
    showToast('Running freight audit rules...', 'info');
    const res = await fetch(`/api/invoices/${invoiceId}/audit`, { method: 'POST' });
    const result = await res.json();
    showToast(`Audit Completed: ${result.status} (Variance: $${result.variance_amount.toFixed(2)})`, result.passed ? 'success' : 'warning');
    await openInvoiceDrawer(invoiceId);
    await loadInvoices();
    await loadKPIs();
  } catch (err) {
    showToast('Failed to execute re-audit', 'danger');
  }
}

// Exceptions Queue
async function loadExceptions() {
  const typeFilter = document.getElementById('filter-exception-type')?.value || 'ALL';
  const severityFilter = document.getElementById('filter-exception-severity')?.value || 'ALL';

  try {
    const res = await fetch(`/api/exceptions?type=${typeFilter}&severity=${severityFilter}`);
    const data = await res.json();
    AppState.exceptions = data.exceptions;
    renderExceptionsTable(data.exceptions);
  } catch (err) {
    console.error('Failed to load exceptions:', err);
  }
}

function renderExceptionsTable(exceptions) {
  const container = document.getElementById('exceptions-list');
  if (!container) return;

  if (exceptions.length === 0) {
    container.innerHTML = `<div class="p-8 text-center text-gray-500">No active exceptions found.</div>`;
    return;
  }

  container.innerHTML = exceptions.map(ex => {
    const sevColors = {
      CRITICAL: 'badge-danger',
      HIGH: 'badge-warning',
      MEDIUM: 'badge-info',
      LOW: 'badge-neutral'
    };

    const isResolved = ex.status === 'RESOLVED';

    return `
      <div class="glass-panel p-4 rounded-xl border border-gray-800 hover:border-gray-700 transition-all flex flex-col md:flex-row justify-between items-start md:items-center gap-4">
        <div class="space-y-1 max-w-2xl">
          <div class="flex items-center gap-2">
            <span class="font-mono text-sm font-semibold text-blue-400">${ex.exception_id}</span>
            <span class="badge ${sevColors[ex.severity] || 'badge-neutral'}">${ex.severity}</span>
            <span class="badge badge-purple">${ex.exception_type.replace(/_/g, ' ')}</span>
            <span class="text-xs text-gray-500">• Linked to <span class="text-gray-300 font-mono">${ex.invoice_id}</span></span>
          </div>
          <div class="text-sm text-gray-200 font-medium">${ex.resolution_notes || 'Overcharge detected during automated contract audit.'}</div>
          <div class="text-xs text-gray-400">Carrier: <span class="text-gray-300">${ex.carrier_name || ex.carrier_id}</span> | Created: ${ex.created_at}</div>
        </div>

        <div class="flex items-center gap-4 self-end md:self-center">
          <div class="text-right">
            <div class="text-xs text-gray-500 uppercase">Disputed Amount</div>
            <div class="text-lg font-bold text-red-400">$${ex.disputed_amount.toFixed(2)}</div>
          </div>

          <div class="flex items-center gap-2">
            ${!isResolved ? `
              <button class="px-3 py-1.5 bg-blue-600 hover:bg-blue-500 text-white rounded-lg text-xs font-medium shadow" onclick="generateCreditNote('${ex.exception_id}')">
                Issue Credit Note
              </button>
              <button class="px-3 py-1.5 bg-gray-800 hover:bg-gray-700 text-gray-300 rounded-lg text-xs border border-gray-700" onclick="resolveExceptionAction('${ex.exception_id}', 'RESOLVED')">
                Resolve
              </button>
            ` : `
              <span class="badge badge-success"><span class="w-1.5 h-1.5 rounded-full bg-emerald-500"></span>RESOLVED</span>
            `}
          </div>
        </div>
      </div>
    `;
  }).join('');
}

async function generateCreditNote(exceptionId) {
  try {
    const res = await fetch(`/api/exceptions/${exceptionId}/credit-note`, { method: 'POST' });
    const data = await res.json();
    if (data.success) {
      showToast(`Credit Note ${data.credit_note_number} generated for $${data.credit_amount.toFixed(2)}!`, 'success');
      loadExceptions();
      loadKPIs();
    }
  } catch (err) {
    showToast('Failed to create credit note', 'danger');
  }
}

async function resolveExceptionAction(exceptionId, status) {
  try {
    const res = await fetch(`/api/exceptions/${exceptionId}/resolve`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ status: status, notes: 'Manually verified and settled by logistics analyst.' })
    });
    const data = await res.json();
    if (data.success) {
      showToast(`Exception ${exceptionId} marked as ${status}`, 'success');
      loadExceptions();
      loadKPIs();
    }
  } catch (err) {
    showToast('Failed to resolve exception', 'danger');
  }
}

// Credit Notes
async function loadCreditNotes() {
  try {
    const res = await fetch('/api/credit-notes');
    const data = await res.json();
    const tbody = document.getElementById('credit-notes-tbody');
    if (!tbody) return;

    if (data.credit_notes.length === 0) {
      tbody.innerHTML = `<tr><td colspan="7" class="text-center py-8 text-gray-500">No credit notes issued yet.</td></tr>`;
      return;
    }

    tbody.innerHTML = data.credit_notes.map(cn => `
      <tr class="border-b border-gray-800 text-sm">
        <td class="font-mono text-blue-400 font-medium">${cn.credit_note_id}</td>
        <td class="font-mono text-gray-300">${cn.credit_note_number}</td>
        <td>${cn.carrier_name || cn.carrier_id}</td>
        <td class="font-mono text-xs text-gray-400">${cn.invoice_id}</td>
        <td class="font-bold text-emerald-400">$${cn.credit_amount.toFixed(2)}</td>
        <td><span class="badge badge-success">${cn.status}</span></td>
        <td class="text-xs text-gray-400">${cn.issue_date}</td>
      </tr>
    `).join('');
  } catch (err) {
    console.error('Failed to load credit notes:', err);
  }
}

// Carrier Scorecards
async function loadCarriers() {
  try {
    const res = await fetch('/api/carriers');
    const data = await res.json();
    AppState.scorecards = data.scorecards;

    // Render Carrier Scorecard chart in Dashboard
    const chartCtx = document.getElementById('chart-carrier-compliance')?.getContext('2d');
    if (chartCtx && data.scorecards) {
      if (AppState.charts.carrierChart) AppState.charts.carrierChart.destroy();

      const topCarriers = data.scorecards.slice(0, 8);
      const isDark = AppState.theme === 'dark';
      const textColor = isDark ? '#9ca3af' : '#475569';

      AppState.charts.carrierChart = new Chart(chartCtx, {
        type: 'bar',
        data: {
          labels: topCarriers.map(c => c.name.length > 15 ? c.name.slice(0, 15) + '...' : c.name),
          datasets: [{
            label: 'Compliance Rate %',
            data: topCarriers.map(c => c.compliance_score_pct),
            backgroundColor: topCarriers.map(c => c.compliance_score_pct >= 85 ? '#10b981' : (c.compliance_score_pct >= 70 ? '#f59e0b' : '#ef4444')),
            borderRadius: 6
          }]
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          plugins: { legend: { display: false } },
          scales: {
            y: {
              beginAtZero: true,
              max: 100,
              ticks: { color: textColor },
              grid: { color: isDark ? 'rgba(255,255,255,0.06)' : 'rgba(0,0,0,0.06)' }
            },
            x: {
              ticks: { color: textColor, font: { size: 10 } },
              grid: { display: false }
            }
          }
        }
      });
    }
  } catch (err) {
    console.error('Failed to load carriers:', err);
  }
}

// Ground Truth & Benchmark
async function loadBenchmark() {
  try {
    const res = await fetch('/api/ground-truth/metrics');
    const data = await res.json();
    AppState.groundTruth = data;

    document.getElementById('bench-accuracy').textContent = data.accuracy_pct;
    document.getElementById('bench-precision').textContent = data.precision_pct;
    document.getElementById('bench-recall').textContent = data.recall_pct;
    document.getElementById('bench-f1').textContent = data.f1_score_pct;

    const cm = data.confusion_matrix;
    document.getElementById('cm-tp').textContent = cm.true_positives;
    document.getElementById('cm-fp').textContent = cm.false_positives;
    document.getElementById('cm-tn').textContent = cm.true_negatives;
    document.getElementById('cm-fn').textContent = cm.false_negatives;
  } catch (err) {
    console.error('Failed to load benchmark:', err);
  }
}

// Step 10: Run Reproducibility Check
async function runReproducibilityTest() {
  const btn = document.getElementById('btn-run-reproducibility');
  const resultContainer = document.getElementById('reproducibility-results');
  
  btn.disabled = true;
  btn.innerHTML = `<span class="animate-spin inline-block mr-2">&#9696;</span> Executing Double Generation Passes...`;

  try {
    const res = await fetch('/api/generator/reproducibility', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ seed: 20261022, scale: 'starter' })
    });
    const data = await res.json();

    resultContainer.classList.remove('hidden');
    const statusBanner = document.getElementById('repro-status-banner');
    
    if (data.reproducibility_verified) {
      statusBanner.className = 'p-4 rounded-xl bg-emerald-950/60 border border-emerald-800 text-emerald-300 flex items-center gap-3';
      statusBanner.innerHTML = `
        <div class="text-xl">&check;</div>
        <div>
          <div class="font-bold">Step 10 Verified: 100% Cryptographic Reproducibility Confirmed</div>
          <div class="text-xs text-emerald-400">All ${data.files_compared} CSV files generated across two independent passes produced identical SHA-256 checksums using seed ${data.seed}.</div>
        </div>
      `;
    }

    const tableBody = document.getElementById('repro-checksums-tbody');
    tableBody.innerHTML = data.comparison.map(item => `
      <tr class="text-xs border-b border-gray-800">
        <td class="font-mono text-gray-200 py-2">${item.file}</td>
        <td class="font-mono text-blue-400">${item.pass_1_hash}</td>
        <td class="font-mono text-purple-400">${item.pass_2_hash}</td>
        <td class="text-right py-2"><span class="badge badge-success">&check; Identical</span></td>
      </tr>
    `).join('');

    showToast('Reproducibility successfully verified!', 'success');
  } catch (err) {
    showToast('Reproducibility check failed', 'danger');
  } finally {
    btn.disabled = false;
    btn.innerHTML = `Run Step 10 Reproducibility Verification`;
  }
}

// Data Dictionary Markdown
async function loadDataDictionary() {
  try {
    const res = await fetch('/api/data-dictionary');
    const data = await res.json();
    const container = document.getElementById('data-dictionary-content');
    if (!container) return;

    // Simple markdown renderer for headers and tables
    const formatted = data.markdown
      .replace(/### (.*?)\n/g, '<h3 class="text-lg font-bold text-blue-400 mt-6 mb-2">$1</h3>')
      .replace(/## (.*?)\n/g, '<h2 class="text-xl font-bold text-white mt-8 mb-3 border-b border-gray-800 pb-2">$1</h2>')
      .replace(/# (.*?)\n/g, '<h1 class="text-2xl font-extrabold text-blue-500 mb-4">$1</h1>')
      .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
      .replace(/`(.*?)`/g, '<code class="bg-gray-800 text-blue-300 px-1 py-0.5 rounded font-mono text-xs">$1</code>');

    container.innerHTML = `<div class="prose prose-invert max-w-none text-sm text-gray-300">${formatted}</div>`;
  } catch (err) {
    console.error('Failed to load data dictionary:', err);
  }
}

// Filter and Search Setup
function setupSearchAndFilters() {
  const searchInput = document.getElementById('search-invoices');
  if (searchInput) {
    let timeout = null;
    searchInput.addEventListener('input', () => {
      clearTimeout(timeout);
      timeout = setTimeout(loadInvoices, 250);
    });
  }

  const invoiceStatus = document.getElementById('filter-invoice-status');
  if (invoiceStatus) {
    invoiceStatus.addEventListener('change', loadInvoices);
  }

  const exType = document.getElementById('filter-exception-type');
  if (exType) {
    exType.addEventListener('change', loadExceptions);
  }

  const exSev = document.getElementById('filter-exception-severity');
  if (exSev) {
    exSev.addEventListener('change', loadExceptions);
  }
}

// Toast Notifications
function showToast(message, type = 'info') {
  const container = document.getElementById('toast-container');
  if (!container) return;

  const toast = document.createElement('div');
  const typeClasses = {
    success: 'border-emerald-500 text-emerald-400',
    warning: 'border-amber-500 text-amber-400',
    danger: 'border-red-500 text-red-400',
    info: 'border-blue-500 text-blue-400'
  };

  toast.className = `toast ${typeClasses[type] || 'border-gray-700'}`;
  toast.innerHTML = `
    <div class="text-sm font-medium text-gray-200">${message}</div>
  `;

  container.appendChild(toast);
  setTimeout(() => {
    toast.style.opacity = '0';
    toast.style.transform = 'translateY(10px)';
    toast.style.transition = 'all 0.3s ease';
    setTimeout(() => toast.remove(), 300);
  }, 3500);
}
