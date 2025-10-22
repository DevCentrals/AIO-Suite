const recordsPerPage = 50;
let currentPage = 1;
let totalRecords = 0;
let currentFilters = {};

let statsStartTime = null;
let statsInterval = null;
let totalTasks = 0;
let completedTasks = 0;
let successfulTasks = 0;

const tableBody = document.getElementById('email-table-body');
const totalRecordsElem = document.getElementById('total-records');
const statusMessage = document.getElementById('status-message');
const statusFilter = document.getElementById('status-filter');
const pagination = document.getElementById('pagination');
const selectAllCheckbox = document.getElementById("select_all");

const dropArea = document.getElementById("drop-area");
const fileInput = document.getElementById("email_file");
const uploadBtn = document.getElementById("upload-btn");
const uploadForm = document.getElementById("upload-form");
const emailInputField = document.getElementById("email-input");
const fileNameDisplay = document.getElementById("file-name-display");
const fileNameSpan = document.getElementById("file-name");

function getStatusBadge(status) {
    const statusMap = {
        'pending': { class: 'bg-secondary', text: 'Pending' },
        'searched': { class: 'bg-success', text: 'Searched' },
        'valid-mail-checked': { class: 'bg-info', text: 'VM Checked' },
        'recovery-checked': { class: 'bg-warning', text: 'Recovery Checked' },
        'error': { class: 'bg-danger', text: 'Error' },
        'not-found': { class: 'bg-dark', text: 'Not Found' }
    };
    
    const statusInfo = statusMap[status.toLowerCase()] || { class: 'bg-secondary', text: status };
    return `<span class="badge ${statusInfo.class}">${statusInfo.text}</span>`;
}

function showToast(type, title, message, duration = 5000) {
    const toastContainer = document.getElementById('toast-container');
    const toastId = 'toast-' + Date.now();
    
    const iconMap = {
        'success': 'fas fa-check-circle',
        'error': 'fas fa-exclamation-circle',
        'warning': 'fas fa-exclamation-triangle',
        'info': 'fas fa-info-circle'
    };
    
    const toastHTML = `
        <div id="${toastId}" class="toast toast-${type}" role="alert" aria-live="assertive" aria-atomic="true">
            <div class="toast-header">
                <i class="${iconMap[type]} me-2"></i>
                <strong class="me-auto">${title}</strong>
                <button type="button" class="btn-close" data-bs-dismiss="toast" aria-label="Close"></button>
            </div>
            <div class="toast-body">
                ${message}
            </div>
        </div>
    `;
    
    toastContainer.insertAdjacentHTML('beforeend', toastHTML);
    
    const toastElement = document.getElementById(toastId);
    const toast = new bootstrap.Toast(toastElement, {
        autohide: true,
        delay: duration
    });
    
    toast.show();
    
    toastElement.addEventListener('hidden.bs.toast', () => {
        toastElement.remove();
    });
}

function showAlert(type, message, title = null) {
    const titleMap = {
        'success': 'Success',
        'error': 'Error',
        'warning': 'Warning',
        'info': 'Information'
    };
    
    showToast(type, title || titleMap[type], message);
}

function setButtonLoading(button, loading = true) {
    if (loading) {
        button.disabled = true;
        button.dataset.originalText = button.innerHTML;
        button.innerHTML = '<i class="fas fa-spinner fa-spin me-2"></i>Loading...';
    } else {
        button.disabled = false;
        button.innerHTML = button.dataset.originalText || button.innerHTML;
    }
}

function updateProgressWithDetails(message, progress = null) {
    const progressMessageElem = document.getElementById('progress-message');
    if (progressMessageElem) {
        progressMessageElem.textContent = message;
    }
    
    if (progress !== null) {
        const progressBar = document.getElementById('progress-bar');
        if (progressBar) {
            progressBar.style.width = `${progress}%`;
            progressBar.setAttribute('aria-valuenow', progress);
        }
    }
}

function toggleDarkMode() {
    const html = document.documentElement;
    const themeIcon = document.getElementById('theme-icon');
    const themeText = document.getElementById('theme-text');
    
    if (html.getAttribute('data-theme') === 'dark') {
        html.removeAttribute('data-theme');
        themeIcon.className = 'fas fa-moon';
        themeText.textContent = 'Dark Mode';
        localStorage.setItem('theme', 'light');
        showAlert('info', 'Switched to light mode');
    } else {
        html.setAttribute('data-theme', 'dark');
        themeIcon.className = 'fas fa-sun';
        themeText.textContent = 'Light Mode';
        localStorage.setItem('theme', 'dark');
        showAlert('info', 'Switched to dark mode');
    }
}

function initializeTheme() {
    const savedTheme = localStorage.getItem('theme');
    const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
    
    if (savedTheme === 'dark' || (!savedTheme && prefersDark)) {
        document.documentElement.setAttribute('data-theme', 'dark');
        const themeIcon = document.getElementById('theme-icon');
        const themeText = document.getElementById('theme-text');
        if (themeIcon && themeText) {
            themeIcon.className = 'fas fa-sun';
            themeText.textContent = 'Light Mode';
        }
    }
}

const openPanelBtn = document.getElementById('open-panel-btn');
const modulePanel = document.getElementById('module-panel');
const closePanelBtn = document.getElementById('close-panel-btn');
const moduleList = document.getElementById('module-list');
document.getElementById('export-csv-btn').onclick = showExportFormatModal;

dropArea.addEventListener("dragover", (event) => {
    event.preventDefault();
    dropArea.classList.add("dragover");
});

dropArea.addEventListener("dragleave", (event) => {
    if (!dropArea.contains(event.relatedTarget)) {
        dropArea.classList.remove("dragover");
    }
});

dropArea.addEventListener("drop", (event) => {
    event.preventDefault();
    dropArea.classList.remove("dragover");

    const file = event.dataTransfer.files[0];
    if (file) {
        handleFileSelection(file);
    }
});

dropArea.addEventListener("click", () => {
    fileInput.click();
});

function handleFileSelection(file) {
    const allowedTypes = ['text/plain', 'text/csv', 'application/csv'];
    const fileExtension = file.name.split('.').pop().toLowerCase();
    
    if (!allowedTypes.includes(file.type) && !['txt', 'csv'].includes(fileExtension)) {
        alert('Please select a valid file (.txt or .csv)');
        return;
    }
    
    const dataTransfer = new DataTransfer();
    dataTransfer.items.add(file);
    
    fileInput.files = dataTransfer.files;
    emailInputField.files = dataTransfer.files;
    
    fileNameSpan.textContent = file.name;
    fileNameDisplay.style.display = "block";
    uploadBtn.style.display = "inline-block";
    uploadForm.style.display = "block";
}

fileInput.addEventListener("change", () => {
    if (fileInput.files.length > 0) {
        const dataTransfer = new DataTransfer();
        for (let i = 0; i < fileInput.files.length; i++) {
            dataTransfer.items.add(fileInput.files[i]);
        }
        emailInputField.files = dataTransfer.files;
        
        handleFileSelection(fileInput.files[0]);
    }
});

document.getElementById('mobile-menu-toggle').addEventListener('click', function() {
    document.getElementById('sidebar').classList.add('open');
});

document.getElementById('sidebar-close').addEventListener('click', function() {
    document.getElementById('sidebar').classList.remove('open');
});

document.addEventListener('click', function(event) {
    const sidebar = document.getElementById('sidebar');
    const mobileToggle = document.getElementById('mobile-menu-toggle');
    
    if (window.innerWidth <= 768 && 
        sidebar.classList.contains('open') && 
        !sidebar.contains(event.target) && 
        !mobileToggle.contains(event.target)) {
        sidebar.classList.remove('open');
    }
});

document.getElementById('open-panel-btn').addEventListener('click', function() {
    document.getElementById('module-panel').classList.add('open');
    this.style.display = 'none';
});

document.getElementById('close-panel-btn').addEventListener('click', function() {
    document.getElementById('module-panel').classList.remove('open');
    document.getElementById('open-panel-btn').style.display = 'block';
});

document.addEventListener('DOMContentLoaded', function() {
    const searchModuleList = document.getElementById('search-module-list');
    const recoveryModuleList = document.getElementById('recovery-module-list');
    const validMailModuleList = document.getElementById('vm-module-list');

    function loadModules() {
        fetch('/get_modules')
            .then(response => response.json())
            .then(data => {
                const recoveryModules = data.modules;
                const validMailModules = data.validmail_modules;
                const searchModules = data.search_modules

                searchModuleList.innerHTML = '';
                recoveryModuleList.innerHTML = '';
                validMailModuleList.innerHTML = '';

                searchModules.forEach(module => {
                    const li = document.createElement('li');
                    li.innerHTML = `<strong>${module.name}</strong> <small>by</small> <em>${module.developer}</em>`;
                    li.style.padding = '8px 0';
                    li.style.borderBottom = '1px solid #ddd';
                    searchModuleList.appendChild(li);
                });

                recoveryModules.forEach(module => {
                    const li = document.createElement('li');
                    li.innerHTML = `<strong>${module.name}</strong> <small>by</small> <em>${module.developer}</em>`;
                    li.style.padding = '8px 0';
                    li.style.borderBottom = '1px solid #ddd';
                    recoveryModuleList.appendChild(li);
                });

                validMailModules.forEach(module => {
                    const li = document.createElement('li');
                    li.innerHTML = `<strong>${module.name}</strong> <small>by</small> <em>${module.developer}</em>`;
                    li.style.padding = '8px 0';
                    li.style.borderBottom = '1px solid #ddd';
                    validMailModuleList.appendChild(li);
                });
            })
            .catch(error => {
                console.error('Error loading modules:', error);
            });
    }

    loadModules();
});

function showValidMailCheckModal() {
    fetch('/get_modules')
        .then(response => response.json())
        .then(data => {
            const validMailModules = data.validmail_modules;
            const modalBody = document.getElementById('validmail-module-selection-body');
            modalBody.innerHTML = '';

            validMailModules.forEach(module => {
                const moduleItem = document.createElement('div');
                moduleItem.classList.add('form-check');
                moduleItem.innerHTML = `  
                    <input class="form-check-input" type="checkbox" value="${module.module_name}" id="module-${module.module_name}">
                    <label class="form-check-label" for="module-${module.module_name}">
                        <strong>${module.name}</strong> by <em>${module.developer}</em>
                    </label>
                `;
                modalBody.appendChild(moduleItem);
            });

            $('#validMailCheckModal').modal('show');
        })
        .catch(error => {
            console.error('Error fetching module list:', error);
        });
}

function showSearchModal() {
    fetch('/get_modules')
        .then(response => response.json())
        .then(data => {
            const searchModules = data.search_modules;
            const modalBody = document.getElementById('search-module-selection-body');
            modalBody.innerHTML = '';

            searchModules.forEach(module => {
                const moduleItem = document.createElement('div');
                moduleItem.classList.add('form-check');
                moduleItem.innerHTML = `  
                    <input class="form-check-input" type="checkbox" value="${module.module_name}" id="module-${module.module_name}">
                    <label class="form-check-label" for="module-${module.module_name}">
                        <strong>${module.name}</strong> by <em>${module.developer}</em>
                    </label>
                `;
                modalBody.appendChild(moduleItem);
            });

            $('#searchkModal').modal('show');
        })
        .catch(error => {
            console.error('Error fetching module list:', error);
        });
}

async function performValidMailCheck() {
    const executeAll = document.getElementById('execute-all').checked;
    const selectedModules = Array.from(document.querySelectorAll('#validmail-module-selection-body input[type="checkbox"]:checked'))
        .map(checkbox => checkbox.value);

    if (selectedModules.length === 0) {
        showAlert('warning', 'Please select at least one module to run.');
        return;
    }

    const selectedEmails = executeAll ? await getAllMatchingEmails() : getSelectedEmails();
    if (selectedEmails.length === 0) {
        showAlert('warning', 'Please select at least one email to perform the check.');
        return;
    }

    initializeStats(selectedEmails.length);
    
    $('#validMailCheckModal').modal('hide');

    try {
        const response = await fetch('/perform_vm_check', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                selected_emails: selectedEmails,
                selected_modules: selectedModules
            })
        });

        const result = await response.json();
        if (response.ok) {
            showAlert('success', 'Valid-mail check completed successfully!');
        } else {
            showAlert('error', 'An error occurred during the valid-mail check.');
        }
    } catch (error) {
        console.error('Error during valid-mail check:', error);
        showAlert('error', 'An error occurred. Please try again.');
    }
}


document.getElementById('perform-validmailcheck-btn').addEventListener('click', showValidMailCheckModal);
document.getElementById('perform-search-btn').addEventListener('click', showSearchModal);
document.getElementById('validmail-modal-submit-btn').addEventListener('click', performValidMailCheck);
document.getElementById('search-modal-submit-btn').addEventListener('click', performLookup);

async function fetchRecords(page = 1, filters = currentFilters) {
        try {
            if (page === 1) {
                tableBody.innerHTML = '<tr><td colspan="8" class="text-center"><div class="spinner-border" role="status"><span class="visually-hidden">Loading...</span></div></td></tr>';
            }
        
        const response = await fetch(`/get_emails?page=${page}&records_per_page=${recordsPerPage}&filters=${JSON.stringify(filters)}`);
        const data = await response.json();

        tableBody.innerHTML = data.records.map(record => {
            const statusBadge = getStatusBadge(record.status || 'pending');

            const formattedValidmailResults = record.validmail_results ?
                Object.entries(record.validmail_results).map(([module, result]) => {
                    const badgeClass = result ? 'bg-success' : 'bg-danger';
                    return `<span class="badge ${badgeClass} me-1 mb-1">${module}: ${result ? 'Valid' : 'Invalid'}</span>`;
                }).join('') :
                '<span class="text-muted">Not checked</span>';

            const altNamesDisplay = record.alternative_names && record.alternative_names.length > 0 ?
                record.alternative_names.slice(0, 2).join(', ') + (record.alternative_names.length > 2 ? ` +${record.alternative_names.length - 2} more` : '') : 
                'N/A';

            const addresses = record.addresses_list && record.addresses_list.length > 0 ? record.addresses_list : [record.address || 'N/A'];
            const zestimates = record.zestimate_values && record.zestimate_values.length > 0 ? record.zestimate_values : [null];
            
            const addressDisplay = addresses.length > 0 ? 
                addresses.slice(0, 1).map(address => 
                    `<div class="text-truncate" style="max-width: 200px;" title="${address}">${address}</div>`
                ).join('') + (addresses.length > 1 ? `<small class="text-muted">+${addresses.length - 1} more</small>` : '') :
                '<span class="text-muted">N/A</span>';
            
            const zestimateDisplay = zestimates.length > 0 && zestimates[0] !== null && zestimates[0] !== undefined && zestimates[0] !== 'None' ? 
                `<span class="text-success fw-bold">$${zestimates[0].toLocaleString()}</span>` + 
                (zestimates.length > 1 ? `<br><small class="text-muted">+${zestimates.length - 1} more</small>` : '') :
                '<span class="text-muted">N/A</span>';

            const phoneDisplay = record.phone_numbers ? 
                (Array.isArray(record.phone_numbers) ? record.phone_numbers.join(', ') : record.phone_numbers) :
                '<span class="text-muted">N/A</span>';

            return `
                <tr id="email-${CSS.escape(record.email)}" data-email="${CSS.escape(record.email)}">
                    <td><input type="checkbox" name="selected_emails" value="${record.id}" class="form-check-input"></td>
                    <td><div class="text-truncate fw-medium" style="max-width: 250px;" title="${record.email}">${record.email}</div></td>
                    <td>${statusBadge}</td>
                    <td><div class="text-truncate" style="max-width: 150px;" title="${record.name || 'N/A'}">${record.name || '<span class="text-muted">N/A</span>'}</div></td>
                    <td><div class="text-truncate" style="max-width: 150px;" title="${phoneDisplay}">${phoneDisplay}</div></td>
                    <td>${addressDisplay}</td>
                    <td><div class="text-truncate" style="max-width: 100px;" title="${record.dob || 'N/A'}">${record.dob || '<span class="text-muted">N/A</span>'}</div></td>
                    <td>${zestimateDisplay}</td>
                    <td><div class="text-truncate" style="max-width: 150px;" title="${altNamesDisplay}">${altNamesDisplay === 'N/A' ? '<span class="text-muted">N/A</span>' : altNamesDisplay}</div></td>
                    <td><div style="max-width: 200px;">${formattedValidmailResults}</div></td>
                </tr>`;
        }).join('');

        totalRecords = data.total;
        totalRecordsElem.textContent = totalRecords;
        updatePagination();
        populateStatusOptions(data.statuses);
        if (document.getElementById('module-filter') && document.getElementById('vm-module-filter')) {
            populateModuleFilter();
        }
        statusFilter.value = filters.status || "";

    } catch (error) {
        console.error('Error fetching records:', error);
    }
}

function showOverlay(message) {
    const overlay = document.getElementById('overlay');
    const messageElem = overlay.querySelector('.message');
    const progressMessageElem = overlay.querySelector('#progress-message');

    messageElem.textContent = message;
    progressMessageElem.textContent = "Initializing...";
    overlay.style.display = 'flex';
}

function closeOverlay() {
    const overlay = document.getElementById('overlay');
    overlay.style.display = 'none';
}

function showStatusMessage(message) {
    const statusElement = document.getElementById("total-records");
    statusElement.innerText = message;
}

function updateProgress(message) {
    const progressMessageElem = document.getElementById('progress-message');
    progressMessageElem.textContent = message;
}

async function showExportFormatModal() {
    const modalHTML = `
    <div class="modal fade" id="exportFormatModal" tabindex="-1" aria-hidden="true">
        <div class="modal-dialog">
            <div class="modal-content">
                <div class="modal-header">
                    <h5 class="modal-title">Export Settings</h5>
                    <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
                </div>
                <div class="modal-body">
                    <div class="mb-3">
                        <label class="form-label">Select Format</label>
                        <select class="form-select" id="exportFormat">
                            <option value="csv">CSV (.csv)</option>
                            <option value="tsv">Tab Separated (.tsv)</option>
                            <option value="txt">Text File (.txt)</option>
                        </select>
                    </div>
                    <div class="mb-3">
                        <label class="form-label">Select and Order Columns</label>
                        <p class="text-muted small">Drag and drop to reorder columns. Uncheck to exclude.</p>
                        <div id="columnSelection" class="d-flex flex-column gap-2">
                            <div class="list-group" id="sortableColumns">
                                <div class="list-group-item d-flex align-items-center" draggable="true" data-column="email">
                                    <span class="drag-handle me-2">☰</span>
                                    <input class="form-check-input me-2" type="checkbox" value="email" id="col-email" checked>
                                    <label class="form-check-label flex-grow-1" for="col-email">Email</label>
                                </div>
                                <div class="list-group-item d-flex align-items-center" draggable="true" data-column="name">
                                    <span class="drag-handle me-2">☰</span>
                                    <input class="form-check-input me-2" type="checkbox" value="name" id="col-name" checked>
                                    <label class="form-check-label flex-grow-1" for="col-name">Full Name</label>
                                </div>
                                <div class="list-group-item d-flex align-items-center" draggable="true" data-column="phone_numbers">
                                    <span class="drag-handle me-2">☰</span>
                                    <input class="form-check-input me-2" type="checkbox" value="phone_numbers" id="col-phone" checked>
                                    <label class="form-check-label flex-grow-1" for="col-phone">Phone Numbers</label>
                                </div>
                                <div class="list-group-item d-flex align-items-center" draggable="true" data-column="address">
                                    <span class="drag-handle me-2">☰</span>
                                    <input class="form-check-input me-2" type="checkbox" value="address" id="col-address" checked>
                                    <label class="form-check-label flex-grow-1" for="col-address">Address</label>
                                </div>
                                <div class="list-group-item d-flex align-items-center" draggable="true" data-column="dob">
                                    <span class="drag-handle me-2">☰</span>
                                    <input class="form-check-input me-2" type="checkbox" value="dob" id="col-dob" checked>
                                    <label class="form-check-label flex-grow-1" for="col-dob">Date of Birth</label>
                                </div>
                                <div class="list-group-item d-flex align-items-center" draggable="true" data-column="status">
                                    <span class="drag-handle me-2">☰</span>
                                    <input class="form-check-input me-2" type="checkbox" value="status" id="col-status" checked>
                                    <label class="form-check-label flex-grow-1" for="col-status">Status</label>
                                </div>
                                <div class="list-group-item d-flex align-items-center" draggable="true" data-column="validmail_results">
                                    <span class="drag-handle me-2">☰</span>
                                    <input class="form-check-input me-2" type="checkbox" value="validmail_results" id="col-validmail" checked>
                                    <label class="form-check-label flex-grow-1" for="col-validmail">ValidMail Results</label>
                                </div>
                                <div class="list-group-item d-flex align-items-center" draggable="true" data-column="addresses_list">
                                    <span class="drag-handle me-2">☰</span>
                                    <input class="form-check-input me-2" type="checkbox" value="addresses_list" id="col-addresses" checked>
                                    <label class="form-check-label flex-grow-1" for="col-addresses">Multiple Addresses</label>
                                </div>
                                <div class="list-group-item d-flex align-items-center" draggable="true" data-column="zestimate_values">
                                    <span class="drag-handle me-2">☰</span>
                                    <input class="form-check-input me-2" type="checkbox" value="zestimate_values" id="col-zestimate" checked>
                                    <label class="form-check-label flex-grow-1" for="col-zestimate">Zestimate Values</label>
                                </div>
                                <div class="list-group-item d-flex align-items-center" draggable="true" data-column="property_details">
                                    <span class="drag-handle me-2">☰</span>
                                    <input class="form-check-input me-2" type="checkbox" value="property_details" id="col-property" checked>
                                    <label class="form-check-label flex-grow-1" for="col-property">Property Details</label>
                                </div>
                                <div class="list-group-item d-flex align-items-center" draggable="true" data-column="alternative_names">
                                    <span class="drag-handle me-2">☰</span>
                                    <input class="form-check-input me-2" type="checkbox" value="alternative_names" id="col-altnames" checked>
                                    <label class="form-check-label flex-grow-1" for="col-altnames">Alternative Names</label>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
                <div class="modal-footer">
                    <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Cancel</button>
                    <button type="button" class="btn btn-primary" id="exportButton">Export</button>
                </div>
            </div>
        </div>
    </div>`;

    if (!document.getElementById('exportFormatModal')) {
        document.body.insertAdjacentHTML('beforeend', modalHTML);
        initializeDragAndDrop();

        const exportButton = document.getElementById('exportButton');
        exportButton.addEventListener('click', async (event) => {
            try {
                exportButton.disabled = true;
                await prepareAndSaveExport();
            } catch (error) {
                console.error('Export failed:', error);
                alert('Failed to export. Please try again.');
            } finally {
                exportButton.disabled = false;
            }
        });
    }

    const modal = new bootstrap.Modal(document.getElementById('exportFormatModal'));
    modal.show();
}

async function prepareAndSaveExport() {
    const loadingIndicator = document.createElement('div');
    loadingIndicator.textContent = 'Preparing export...';
    loadingIndicator.style.position = 'fixed';
    loadingIndicator.style.top = '50%';
    loadingIndicator.style.left = '50%';
    loadingIndicator.style.transform = 'translate(-50%, -50%)';
    loadingIndicator.style.background = 'rgba(0,0,0,0.7)';
    loadingIndicator.style.color = 'white';
    loadingIndicator.style.padding = '20px';
    loadingIndicator.style.borderRadius = '5px';
    document.body.appendChild(loadingIndicator);

    try {
        const records = await getFilteredRecords();
        
        if (records.length === 0) {
            alert('No records to export!');
            return;
        }

        const format = document.getElementById('exportFormat').value;
        const columnElements = Array.from(document.getElementById('sortableColumns').children);

        const selectedColumns = columnElements
            .filter(el => el.querySelector('input[type="checkbox"]').checked)
            .map(el => el.dataset.column);

        if (selectedColumns.length === 0) {
            alert('Please select at least one column to export!');
            return;
        }

        const separator = format === 'tsv' ? '\t' : format === 'csv' ? ',' : ' | ';
        const rows = [];
        
        const headers = selectedColumns.map(col => {
            switch (col) {
                case 'name': return 'Full Name';
                case 'phone_numbers': return 'Phone Numbers';
                case 'validmail_results': return 'ValidMail Results';
                default: return col.charAt(0).toUpperCase() + col.slice(1);
            }
        });
        rows.push(headers.join(separator));

        records.forEach((record, index) => {
            const row = selectedColumns.map(col => {
                let value = record[col] || 'N/A';
                
                if (col === 'phone_numbers') {
                    value = Array.isArray(value) ? 
                        value.join('; ').replace(/\r?\n|\r/g, ' ') : 
                        value.toString().replace(/\r?\n|\r/g, ' ');
                } else if (col === 'validmail_results') {
                    value = value ? Object.entries(value)
                        .map(([module, result]) => `${module}:${result ? 'Valid' : 'Invalid'}`)
                        .join('; ') : 'N/A';
                }

                value = value.toString()
                    .replace(/\r?\n|\r/g, ' ')
                    .replace(/\s+/g, ' ')
                    .trim();

                if (format === 'csv') {
                    if (value.includes('"')) {
                        value = value.replace(/"/g, '""');
                    }
                    if (value.includes(',')) {
                        value = `"${value}"`;
                    }
                }

                return value;
            });
            rows.push(row.join(separator));
        });

        const fileContent = rows.join('\n');
        const fileType = format === 'csv' ? 'text/csv' : 'text/plain';
        const fileExtension = format === 'csv' ? 'csv' : format === 'tsv' ? 'tsv' : 'txt';

        const confirmSave = confirm(`Export data is ready (${records.length} records). Click OK to save as ${fileExtension.toUpperCase()} file.`);
        if (!confirmSave) {
            alert('Export canceled.');
            return;
        }

        try {
            if ('showSaveFilePicker' in window) {
                const fileHandle = await window.showSaveFilePicker({
                    suggestedName: `export_${new Date().toISOString().slice(0,10)}.${fileExtension}`,
                    types: [{
                        description: `${fileExtension.toUpperCase()} File`,
                        accept: { [fileType]: [`.${fileExtension}`] }
                    }]
                });
                const writableStream = await fileHandle.createWritable();
                await writableStream.write(fileContent);
                await writableStream.close();
            } else {
                const blob = new Blob([fileContent], { type: `${fileType};charset=utf-8;` });
                const url = URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = url;
                a.download = `export_${new Date().toISOString().slice(0,10)}.${fileExtension}`;
                document.body.appendChild(a);
                a.click();
                setTimeout(() => {
                    document.body.removeChild(a);
                    URL.revokeObjectURL(url);
                }, 100);
            }

            alert(`File saved successfully with ${records.length} records!`);
            const modal = bootstrap.Modal.getInstance(document.getElementById('exportFormatModal'));
            modal.hide();
        } catch (error) {
            if (error.name !== 'AbortError') {
                console.error('Error saving file:', error);
                alert('Failed to save the file. Please try again.');
            }
        }
    } finally {
        document.body.removeChild(loadingIndicator);
    }
}

function initializeDragAndDrop() {
    const sortableList = document.getElementById('sortableColumns');
    let draggedItem = null;

    const style = document.createElement('style');
    style.textContent = `
        .drag-handle { cursor: move; user-select: none; }
        .list-group-item { cursor: move; background: white; }
        .list-group-item.dragging { opacity: 0.5; }
        .list-group-item.drag-over { border-top: 2px solid #0d6efd; }
    `;
    document.head.appendChild(style);

    const items = sortableList.getElementsByClassName('list-group-item');
    Array.from(items).forEach(item => {
        item.addEventListener('dragstart', handleDragStart);
        item.addEventListener('dragend', handleDragEnd);
        item.addEventListener('dragover', handleDragOver);
        item.addEventListener('drop', handleDrop);
    });

    function handleDragStart(e) {
        draggedItem = this;
        this.classList.add('dragging');
    }

    function handleDragEnd(e) {
        draggedItem.classList.remove('dragging');
        Array.from(items).forEach(item => {
            item.classList.remove('drag-over');
        });
    }

    function handleDragOver(e) {
        e.preventDefault();
        this.classList.add('drag-over');
    }

    function handleDrop(e) {
        e.preventDefault();
        if (this !== draggedItem) {
            const allItems = [...items];
            const draggedIndex = allItems.indexOf(draggedItem);
            const droppedIndex = allItems.indexOf(this);

            if (draggedIndex > droppedIndex) {
                this.parentNode.insertBefore(draggedItem, this);
            } else {
                this.parentNode.insertBefore(draggedItem, this.nextSibling);
            }
        }
        this.classList.remove('drag-over');
    }
}

async function executeExport() {
    const records = await getFilteredRecords();
    if (records.length === 0) {
        alert('No records to export!');
        return;
    }

    const format = document.getElementById('exportFormat').value;
    const columnElements = Array.from(document.getElementById('sortableColumns').children);

    const selectedColumns = columnElements
        .filter(el => el.querySelector('input[type="checkbox"]').checked)
        .map(el => el.dataset.column);

    if (selectedColumns.length === 0) {
        alert('Please select at least one column to export!');
        return;
    }

    const separator = format === 'tsv' ? '\t' : format === 'csv' ? ',' : ' | ';
    const rows = [];
    
    const headers = selectedColumns.map(col => {
        switch (col) {
            case 'name': return 'Full Name';
            case 'phone_numbers': return 'Phone Numbers';
            case 'validmail_results': return 'ValidMail Results';
            default: return col.charAt(0).toUpperCase() + col.slice(1);
        }
    });
    rows.push(headers.join(separator));

    records.forEach(record => {
        const row = selectedColumns.map(col => {
            let value = record[col] || 'N/A';
            
            if (col === 'phone_numbers') {
                value = Array.isArray(value) ? 
                    value.join('; ').replace(/\r?\n|\r/g, ' ') : 
                    value.toString().replace(/\r?\n|\r/g, ' ');
            } else if (col === 'validmail_results') {
                value = value ? Object.entries(value)
                    .map(([module, result]) => `${module}:${result ? 'Valid' : 'Invalid'}`)
                    .join('; ') : 'N/A';
            }

            value = value.toString()
                .replace(/\r?\n|\r/g, ' ')
                .replace(/\s+/g, ' ')
                .trim();

            if (format === 'csv') {
                if (value.includes('"')) {
                    value = value.replace(/"/g, '""');
                }
                if (value.includes(',')) {
                    value = `"${value}"`;
                }
            }

            return value;
        });
        rows.push(row.join(separator));
    });

    const fileContent = rows.join('\n');
    const fileType = format === 'csv' ? 'text/csv' : 'text/plain';
    const fileExtension = format === 'csv' ? 'csv' : format === 'tsv' ? 'tsv' : 'txt';

    try {
        if ('showSaveFilePicker' in window) {
            const fileHandle = await window.showSaveFilePicker({
                suggestedName: `export_${new Date().toISOString().slice(0,10)}.${fileExtension}`,
                types: [{
                    description: `${fileExtension.toUpperCase()} File`,
                    accept: { [fileType]: [`.${fileExtension}`] }
                }]
            });
            const writableStream = await fileHandle.createWritable();
            await writableStream.write(fileContent);
            await writableStream.close();
        } else {
            const blob = new Blob([fileContent], { type: `${fileType};charset=utf-8;` });
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = `export_${new Date().toISOString().slice(0,10)}.${fileExtension}`;
            document.body.appendChild(a);
            a.click();
            setTimeout(() => {
                document.body.removeChild(a);
                URL.revokeObjectURL(url);
            }, 100);
        }

        alert(`Exported ${records.length} records successfully!`);
    } catch (error) {
        if (error.name !== 'AbortError') {
            console.error('Error saving file:', error);
            alert('Failed to save the file. Please try again.');
        }
    }

    const modal = bootstrap.Modal.getInstance(document.getElementById('exportFormatModal'));
    modal.hide();
}


async function getFilteredRecords() {
    const filters = {
        ...currentFilters
    };

    try {
        const url = `/get_emails?filters=${JSON.stringify(filters)}&fetch_all=true`;
        
        const response = await fetch(url);
        const data = await response.json();
        
        return data.records || [];
    } catch (error) {
        console.error('Error fetching filtered records:', error);
        return [];
    }
}

function loadSettings() {
    Promise.all([
        fetch('/get_settings').then(response => response.json()),
        fetch('/get_modules').then(response => response.json())
    ])
    .then(([settingsData, modulesData]) => {
        if (settingsData.success) {
            const settingsContent = document.getElementById('settings-content');
            settingsContent.innerHTML = '';
            
            const moduleSettings = {};
            const generalSettings = {};
            
            for (const [key, value] of Object.entries(settingsData.settings)) {
                if (key === 'house_value' || key === 'search_api_key') {
                    moduleSettings['SearchAPI'] = moduleSettings['SearchAPI'] || {};
                    moduleSettings['SearchAPI'][key] = value;
                } else if (key === 'threads') {
                    generalSettings[key] = value;
                } else {
                    generalSettings[key] = value;
                }
            }
            
            
            if (moduleSettings['SearchAPI']) {
                const searchAPISettings = moduleSettings['SearchAPI'];
                const searchAPIModule = modulesData.search_modules?.find(m => m.module_name === 'SearchAPI');
                
                let searchAPICard = `
                    <div class="card mb-4">
                        <div class="card-header">
                            <h5 class="mb-0">
                                <i class="fas fa-search me-2"></i>
                                <strong>${searchAPIModule?.name || 'SearchAPI'}</strong>
                                <small class="text-muted">by ${searchAPIModule?.developer || '@CPUCycle'}</small>
                            </h5>
                        </div>
                        <div class="card-body">
                `;
                
                if (searchAPISettings['search_api_key'] !== undefined) {
                    searchAPICard += `
                        <div class="mb-3">
                            <label for="search_api_key" class="form-label">Search API Key</label>
                            <input type="text" class="form-control" id="search_api_key" name="search_api_key" value="${searchAPISettings['search_api_key'] || ''}">
                            <small class="text-muted">API key for SearchAPI service</small>
                        </div>
                    `;
                }
                
                if (searchAPISettings['house_value'] !== undefined) {
                    const houseValue = searchAPISettings['house_value'] || '';
                    const isChecked = houseValue && ['true', '1', 'yes', 'on'].includes(houseValue.toLowerCase());
                    searchAPICard += `
                        <div class="mb-3">
                            <div class="form-check form-switch">
                                <input class="form-check-input" type="checkbox" id="house_value" name="house_value" ${isChecked ? 'checked' : ''}>
                                <label class="form-check-label" for="house_value">
                                    <strong>House Value Features</strong>
                                    <small class="text-muted d-block">Enable zestimate and property details extraction</small>
                                </label>
                            </div>
                        </div>
                    `;
                }
                
                searchAPICard += `
                        </div>
                    </div>
                `;
                
                settingsContent.innerHTML += searchAPICard;
            }
            
            for (const [moduleName, settings] of Object.entries(moduleSettings)) {
                if (moduleName === 'SearchAPI') continue;
                
                const module = modulesData.search_modules?.find(m => m.module_name === moduleName) || 
                              modulesData.validmail_modules?.find(m => m.module_name === moduleName);
                
                if (module) {
                    let moduleCard = `
                        <div class="card mb-4">
                            <div class="card-header">
                                <h5 class="mb-0">
                                    <i class="fas fa-cog me-2"></i>
                                    <strong>${module.name}</strong>
                                    <small class="text-muted">by ${module.developer}</small>
                                </h5>
                            </div>
                            <div class="card-body">
                    `;
                    
                    for (const [key, value] of Object.entries(settings)) {
                        moduleCard += `
                            <div class="mb-3">
                                <label for="${key}" class="form-label">${key.replace('_', ' ').replace(/\b\w/g, l => l.toUpperCase())}</label>
                                <input type="text" class="form-control" id="${key}" name="${key}" value="${value || ''}">
                            </div>
                        `;
                    }
                    
                    moduleCard += `
                            </div>
                        </div>
                    `;
                    
                    settingsContent.innerHTML += moduleCard;
                }
            }
            
            if (Object.keys(generalSettings).length > 0) {
                let generalCard = `
                    <div class="card mb-4">
                        <div class="card-header">
                            <h5 class="mb-0">
                                <i class="fas fa-cogs me-2"></i>
                                <strong>General Settings</strong>
                            </h5>
                        </div>
                        <div class="card-body">
                `;
                
                for (const [key, value] of Object.entries(generalSettings)) {
                    generalCard += `
                        <div class="mb-3">
                            <label for="${key}" class="form-label">${key.replace('_', ' ').replace(/\b\w/g, l => l.toUpperCase())}</label>
                            <input type="text" class="form-control" id="${key}" name="${key}" value="${value || ''}">
                        </div>
                    `;
                }
                
                generalCard += `
                        </div>
                    </div>
                `;
                
                settingsContent.innerHTML += generalCard;
            }
        } else {
            alert('Failed to load settings: ' + settingsData.message);
        }
    })
    .catch(error => {
        console.error('Error fetching settings:', error);
        alert('An error occurred while loading settings.');
    });
}

function saveSettings() {
    const formData = new FormData(document.getElementById('settings-form'));
    const settings = {};
    formData.forEach((value, key) => {
        settings[key] = value;
    });
    
    const checkboxes = document.querySelectorAll('#settings-content input[type="checkbox"]');
    checkboxes.forEach(checkbox => {
        settings[checkbox.name] = checkbox.checked ? 'true' : 'false';
    });

    fetch('/update_settings', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(settings),
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                alert('Settings updated successfully!');
                document.getElementById('settingsModal').querySelector('.btn-close').click();
            } else {
                alert('Failed to update settings: ' + data.message);
            }
        })
        .catch(error => {
            console.error('Error updating settings:', error);
            alert('An error occurred while updating settings.');
        });
}


function updatePagination() {
    const totalPages = Math.ceil(totalRecords / recordsPerPage);
    const maxPagesToShow = 11;
    const halfRange = Math.floor(maxPagesToShow / 2);

    let startPage = Math.max(currentPage - halfRange, 1);
    let endPage = Math.min(currentPage + halfRange, totalPages);

    if (currentPage <= halfRange) {
        endPage = Math.min(maxPagesToShow, totalPages);
    } else if (currentPage > totalPages - halfRange) {
        startPage = Math.max(totalPages - maxPagesToShow + 1, 1);
    }

    let paginationHTML = '';
    if (startPage > 1) paginationHTML += `<li class="page-item"><a class="page-link" href="#" onclick="navigateToPage(1)">First</a></li>`;
    if (currentPage > 1) paginationHTML += `<li class="page-item"><a class="page-link" href="#" onclick="navigateToPage(${currentPage - 1})">Previous</a></li>`;

    for (let i = startPage; i <= endPage; i++) {
        const activeClass = i === currentPage ? 'active' : '';
        paginationHTML += `<li class="page-item ${activeClass}"><a class="page-link" href="#" onclick="navigateToPage(${i})">${i}</a></li>`;
    }

    if (currentPage < totalPages) paginationHTML += `<li class="page-item"><a class="page-link" href="#" onclick="navigateToPage(${currentPage + 1})">Next</a></li>`;
    if (endPage < totalPages) paginationHTML += `<li class="page-item"><a class="page-link" href="#" onclick="navigateToPage(${totalPages})">Last</a></li>`;

    pagination.innerHTML = paginationHTML;
}

function navigateToPage(page) {
    currentPage = page;
    fetchRecords(currentPage);
}

function toggleSelectAll() {
    const checkboxes = document.querySelectorAll('input[name="selected_emails"]');
    checkboxes.forEach(checkbox => {
        if (checkbox.closest('tr').style.display !== 'none') {
            checkbox.checked = selectAllCheckbox.checked;
        }
    });
}

async function performLookup() {
    showOverlay("Starting email lookup...");
    
    const executeAll = document.getElementById('execute-all').checked;
    const selectedModules = Array.from(document.querySelectorAll('#search-module-selection-body input[type="checkbox"]:checked'))
        .map(checkbox => checkbox.value);

    if (selectedModules.length === 0) {
        closeOverlay();
        showAlert('warning', 'Please select at least one module to run.');
        return;
    }

    const selectedEmails = executeAll ? await getAllMatchingEmails() : getSelectedEmails();
    if (selectedEmails.length === 0) {
        closeOverlay();
        showAlert('warning', 'Please select at least one email to perform the check.');
        return;
    }
    const submitBtn = document.getElementById('search-modal-submit-btn');
    setButtonLoading(submitBtn, true);

    initializeStats(selectedEmails.length);
    $('#searchModal').modal('hide');

    try {
        const response = await fetch('/perform_lookup', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                selected_emails: selectedEmails,
                selected_modules: selectedModules
            })
        });

        const result = await response.json();
        if (response.ok) {
            showAlert('success', `Search completed! Processing ${selectedEmails.length} emails.`);
        } else {
            closeOverlay();
            showAlert('error', 'An error occurred during the search.');
        }
    } catch (error) {
        console.error('Error during Search:', error);
        closeOverlay();
        showAlert('error', 'An error occurred. Please try again.');
    } finally {
        setButtonLoading(submitBtn, false);
    }
}


function getSelectedEmails() {
    return Array.from(document.querySelectorAll('input[name="selected_emails"]:checked'))
        .filter(checkbox => checkbox.closest('tr').style.display !== 'none')
        .map(checkbox => checkbox.closest('tr').querySelector('td:nth-child(2)').textContent.trim());
}

function resetFilters() {
  document.getElementById('filter-domain').value = '';
  document.getElementById('status-filter').value = '';
  
  document.getElementById('has-name').checked = false;
  document.getElementById('has-phone').checked = false;
  document.getElementById('has-address').checked = false;
  document.getElementById('has-dob').checked = false;
  
  document.getElementById('has-zestimate').checked = false;
  document.getElementById('has-alternative-names').checked = false;
  document.getElementById('has-multiple-addresses').checked = false;
  document.getElementById('zestimate-min').value = '';
  document.getElementById('zestimate-max').value = '';
  
  document.getElementById('vm-status').value = '';
  document.getElementById('module-filter').selectedIndex = -1;
  document.getElementById('vm-module-filter').selectedIndex = -1;
  document.getElementById('vm-module-status').value = '';
  
  currentFilters = {};
  fetchRecords(1);
}

function applyFilters() {
    currentFilters = {};
    
    const moduleFilter = document.getElementById('module-filter');
    const vmModuleFilter = document.getElementById('vm-module-filter');
    if ((moduleFilter && moduleFilter.children.length === 0) || (vmModuleFilter && vmModuleFilter.children.length === 0)) {
        populateModuleFilter();
    }
    
    const domain = document.getElementById('filter-domain').value;
    const status = document.getElementById('status-filter').value;
    
    if (domain) currentFilters.domain = domain;
    if (status) currentFilters.status = status;
    
    if (document.getElementById('has-name').checked) {
      currentFilters.has_name = true;
    }
    if (document.getElementById('has-phone').checked) {
      currentFilters.has_phone = true;
    }
    if (document.getElementById('has-address').checked) {
      currentFilters.has_address = true;
    }
    if (document.getElementById('has-dob').checked) {
      currentFilters.has_dob = true;
    }
    
    if (document.getElementById('has-zestimate').checked) {
      currentFilters.has_zestimate = true;
    }
    if (document.getElementById('has-alternative-names').checked) {
      currentFilters.has_alternative_names = true;
    }
    if (document.getElementById('has-multiple-addresses').checked) {
      currentFilters.has_multiple_addresses = true;
    }
    
    const zestimateMin = document.getElementById('zestimate-min').value;
    const zestimateMax = document.getElementById('zestimate-max').value;
    if (zestimateMin) currentFilters.zestimate_min = zestimateMin;
    if (zestimateMax) currentFilters.zestimate_max = zestimateMax;
    
    const vmStatus = document.getElementById('vm-status').value;
    if (vmStatus) {
      currentFilters.vm_status = vmStatus;
    }
    
    if (moduleFilter) {
      const selectedModules = Array.from(moduleFilter.selectedOptions)
        .map(option => option.value);
      
      if (selectedModules.length > 0) {
        currentFilters.module_results = {};
        selectedModules.forEach(module => {
          currentFilters.module_results[module] = true;
        });
      }
    }
    
    const vmModuleStatusElement = document.getElementById('vm-module-status');
    
    if (vmModuleFilter && vmModuleStatusElement) {
      const selectedVmModules = Array.from(vmModuleFilter.selectedOptions)
        .map(option => option.value);
      const vmModuleStatus = vmModuleStatusElement.value;
      
      if (selectedVmModules.length > 0 && vmModuleStatus) {
        currentFilters.vm_module_results = {};
        selectedVmModules.forEach(module => {
          currentFilters.vm_module_results[module] = vmModuleStatus === 'valid';
        });
      }
    }
    
    const filtersParam = encodeURIComponent(JSON.stringify(currentFilters));
    
    fetch(`/get_emails?page=1&records_per_page=${recordsPerPage}&filters=${filtersParam}`)
      .then(response => response.json())
      .then(data => {
        tableBody.innerHTML = data.records.map(record => {
          const formattedValidmailResults = record.validmail_results ?
            Object.entries(record.validmail_results).map(([module, result]) => {
              return `<strong>${module}</strong>: ${result ? 'Valid' : 'Invalid'}`;
            }).join('<br>') :
            'N/A';

          const altNamesDisplay = record.alternative_names && record.alternative_names.length > 0 ?
              record.alternative_names.slice(0, 2).join(', ') + (record.alternative_names.length > 2 ? ` +${record.alternative_names.length - 2} more` : '') : 
              'N/A';
  
          const addresses = record.addresses_list && record.addresses_list.length > 0 ? record.addresses_list : [record.address || 'N/A'];
          const zestimates = record.zestimate_values && record.zestimate_values.length > 0 ? record.zestimate_values : [null];
          
          const addressDisplay = addresses.map((address, index) => 
              `<div class="address-item"><strong>Address ${index + 1}:</strong> ${address}</div>`
          ).join('');
          
          const zestimateDisplay = zestimates.map((zestimate, index) => {
              const zestimateValue = (zestimate !== null && zestimate !== undefined && zestimate !== 'None') ? 
                  `$${zestimate.toLocaleString()}` : 'N/A';
              return `<div class="zestimate-item"><strong>Address ${index + 1}:</strong> ${zestimateValue}</div>`;
          }).join('');

          return `
              <tr id="email-${CSS.escape(record.email)}" data-email="${CSS.escape(record.email)}">
                  <td><input type="checkbox" name="selected_emails" value="${record.id}"></td>
                  <td>${record.email}</td>
                  <td>${record.status || 'N/A'}</td>
                  <td>${record.name || 'N/A'}</td>
                  <td>${record.phone_numbers || 'N/A'}</td>
                  <td>${addressDisplay}</td>
                  <td>${record.dob || 'N/A'}</td>
                  <td>${zestimateDisplay}</td>
                  <td><div class="text-truncate" style="max-width: 150px;" title="${altNamesDisplay}">${altNamesDisplay === 'N/A' ? '<span class="text-muted">N/A</span>' : altNamesDisplay}</div></td>
                  <td>${formattedValidmailResults}</td>
              </tr>`;
        }).join('');
  
        totalRecords = data.total;
        totalRecordsElem.textContent = totalRecords;
        updatePagination();
        populateStatusOptions(data.statuses);
        if (document.getElementById('module-filter') && document.getElementById('vm-module-filter')) {
            populateModuleFilter();
        }
      })
      .catch(error => {
        console.error('Error fetching filtered records:', error);
      });
  
    $('#filterModal').modal('hide');
  }

async function deleteSelectedRecords() {
    const selectedEmails = getSelectedEmails();
    
    if (selectedEmails.length === 0) {
        alert('Please select at least one record to delete.');
        return;
    }

    if (!confirm(`Are you sure you want to delete ${selectedEmails.length} selected record(s)?`)) {
        return;
    }

    try {
        const response = await fetch('/delete_records', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                emails: selectedEmails,
                delete_type: 'selected'
            })
        });

        const result = await response.json();
        if (result.success) {
            alert(`Successfully deleted ${result.deleted_count} record(s)`);
            fetchRecords(currentPage, currentFilters);
        } else {
            alert('Error deleting records: ' + result.message);
        }
    } catch (error) {
        console.error('Error deleting records:', error);
        alert('An error occurred while deleting records.');
    }

    $('#deleteModal').modal('hide');
}

async function deleteFilteredRecords() {
    if (!confirm('Are you sure you want to delete all filtered records?')) {
        return;
    }

    try {
        const response = await fetch('/delete_records', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                filters: currentFilters,
                delete_type: 'filtered'
            })
        });

        const result = await response.json();
        if (result.success) {
            alert(`Successfully deleted ${result.deleted_count} record(s)`);
            fetchRecords(1, currentFilters);
        } else {
            alert('Error deleting records: ' + result.message);
        }
    } catch (error) {
        console.error('Error deleting filtered records:', error);
        alert('An error occurred while deleting records.');
    }

    $('#deleteModal').modal('hide');
}

async function clearAllRecords() {
    try {
        const response = await fetch('/delete_records', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                delete_type: 'all'
            })
        });

        const result = await response.json();
        if (result.success) {
            alert('Successfully cleared all records');
            fetchRecords(1);
        } else {
            alert('Error clearing records: ' + result.message);
        }
    } catch (error) {
        console.error('Error clearing all records:', error);
        alert('An error occurred while clearing records.');
    }

    $('#confirmClearAllModal').modal('hide');
    $('#deleteModal').modal('hide');
}

async function populateModuleFilter() {
    try {
        const response = await fetch('/get_modules');
        const data = await response.json();
        const moduleFilter = document.getElementById('module-filter');
        const vmModuleFilter = document.getElementById('vm-module-filter');

        if (moduleFilter) {
            moduleFilter.innerHTML = '';
        }
        if (vmModuleFilter) {
            vmModuleFilter.innerHTML = '';
        }

        if (data.validmail_modules) {
            data.validmail_modules.forEach(module => {
                if (moduleFilter) {
                    const option = document.createElement('option');
                    option.value = module.module_name;
                    option.textContent = module.name;
                    moduleFilter.appendChild(option);
                }
                
                if (vmModuleFilter) {
                    const vmOption = document.createElement('option');
                    vmOption.value = module.module_name;
                    vmOption.textContent = module.name;
                    vmModuleFilter.appendChild(vmOption);
                }
            });
        }
    } catch (error) {
        console.error('Error fetching modules:', error);
    }
}

function populateStatusOptions(statuses) {
    statusFilter.innerHTML = '<option value="">-- All Statuses --</option>';
    statuses.forEach(status => {
        const option = document.createElement('option');
        option.value = status;
        option.textContent = status;
        statusFilter.appendChild(option);
    });
}

async function performRecoveryCheck() {
    const executeAll = document.getElementById('execute-all').checked;
    const selectedEmails = executeAll ? await getAllMatchingEmails() : getSelectedEmails();

    if (selectedEmails.length === 0) {
        alert('Please select at least one email to perform recovery check.');
        return;
    }

    showOverlay("Loading, please wait...");
    initializeStats(selectedEmails.length);
    
    try {
        const response = await fetch('/perform_recovery_check', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                selected_emails: selectedEmails
            })
        });
        const data = await response.json();
        updateTable(data);
    } catch (error) {
        console.error('Error:', error);
    } finally {
        closeOverlay();
    }
}

function getAllMatchingEmails(fetchAll = true) {
    const filters = currentFilters || {};
    const url = `/get_emails?filters=${encodeURIComponent(JSON.stringify(filters))}&fetch_all=${fetchAll}`;

    return fetch(url)
        .then(response => response.json())
        .then(data => {
            const emails = data.records.map(record => record.email);
            return emails;
        })
        .catch(error => {
            console.error('Error fetching matching emails:', error);
            return [];
        });
}

function updateTable(data) {
    data.forEach(item => {
        const row = document.getElementById(`email-${item.id}`);
        if (row) {
            row.querySelector(`#status-${item.id}`).textContent = item.status || 'Processed';
            row.querySelector(`#name-${item.id}`).textContent = item.name || 'N/A';
            row.querySelector(`#phone_numbers-${item.id}`).textContent = item.phone_numbers.join(', ') || 'N/A';
            row.querySelector(`#address-${item.id}`).textContent = item.address || 'N/A';
            row.querySelector(`#dob-${item.id}`).textContent = item.dob || 'N/A';
        }
    });
}

document.addEventListener("DOMContentLoaded", () => {
    fetchThreadsSetting();
});

function fetchThreadsSetting() {
    fetch('/api/settings/threads')
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                const threadsInput = document.getElementById('threads');
                if (threadsInput) {
                    threadsInput.value = data.value;
                }
            } else {
                console.error(data.message || 'Failed to fetch threads setting.');
            }
        })
        .catch(err => console.error('Error fetching threads setting:', err));
}

document.addEventListener('DOMContentLoaded', () => {
    initializeTheme();
    
    fetchRecords();

    const filterModal = document.getElementById('filterModal');
    if (filterModal) {
        filterModal.addEventListener('shown.bs.modal', function () {
            populateModuleFilter();
        });
    } else {
        console.warn('Filter modal element not found');
    }

    const socket = io();

    socket.on('task_status', function(data) {
        if (data.status === 'started') {
            initializeStats(data.total);
        }
        updateProgress(data.status);
        
        if (data.status && (data.status.includes('completed') || data.status.includes('finished'))) {
            setTimeout(() => {
                closeOverlay();
            }, 1000);
        }
    });

    socket.on('email_result', function(result) {
        const resultString = JSON.stringify(result, null, 2);
        updateProgress(resultString);
        updateStats(result.success !== false);
        
        const escapedEmail = CSS.escape(result.email);
        const row = document.getElementById(`email-${escapedEmail}`);

        if (row) {
            const cells = row.querySelectorAll('td');
            
            if (cells[2]) {
                const statusBadge = getStatusBadge(result.status || 'pending');
                cells[2].innerHTML = statusBadge;
            }
            
            if (cells[3]) {
                const nameDisplay = result.name || 'N/A';
                cells[3].innerHTML = `<div class="text-truncate" style="max-width: 150px;" title="${nameDisplay}">${nameDisplay === 'N/A' ? '<span class="text-muted">N/A</span>' : nameDisplay}</div>`;
            }
            
            if (cells[4]) {
                const phoneDisplay = result.phone_numbers ? 
                    (Array.isArray(result.phone_numbers) ? result.phone_numbers.join(', ') : result.phone_numbers) :
                    'N/A';
                cells[4].innerHTML = `<div class="text-truncate" style="max-width: 150px;" title="${phoneDisplay}">${phoneDisplay === 'N/A' ? '<span class="text-muted">N/A</span>' : phoneDisplay}</div>`;
            }
            
            if (cells[5]) {
                const addresses = result.addresses_list && result.addresses_list.length > 0 ? result.addresses_list : [result.address || 'N/A'];
                const addressDisplay = addresses.length > 0 ? 
                    addresses.slice(0, 1).map(address => 
                        `<div class="text-truncate" style="max-width: 200px;" title="${address}">${address}</div>`
                    ).join('') + (addresses.length > 1 ? `<small class="text-muted">+${addresses.length - 1} more</small>` : '') :
                    '<span class="text-muted">N/A</span>';
                cells[5].innerHTML = addressDisplay;
            }
            
            if (cells[6]) {
                const dobDisplay = result.dob || 'N/A';
                cells[6].innerHTML = `<div class="text-truncate" style="max-width: 100px;" title="${dobDisplay}">${dobDisplay === 'N/A' ? '<span class="text-muted">N/A</span>' : dobDisplay}</div>`;
            }
            
            if (cells[7]) {
                const zestimates = result.zestimate_values && result.zestimate_values.length > 0 ? result.zestimate_values : [null];
                const zestimateDisplay = zestimates.length > 0 && zestimates[0] !== null && zestimates[0] !== undefined && zestimates[0] !== 'None' ? 
                    `<span class="text-success fw-bold">$${zestimates[0].toLocaleString()}</span>` + 
                    (zestimates.length > 1 ? `<br><small class="text-muted">+${zestimates.length - 1} more</small>` : '') :
                    '<span class="text-muted">N/A</span>';
                cells[7].innerHTML = zestimateDisplay;
            }
            
            if (cells[8]) {
                const altNamesDisplay = result.alternative_names && result.alternative_names.length > 0 ?
                    result.alternative_names.slice(0, 2).join(', ') + (result.alternative_names.length > 2 ? ` +${result.alternative_names.length - 2} more` : '') : 
                    'N/A';
                cells[8].innerHTML = `<div class="text-truncate" style="max-width: 150px;" title="${altNamesDisplay}">${altNamesDisplay === 'N/A' ? '<span class="text-muted">N/A</span>' : altNamesDisplay}</div>`;
            }
            
            if (cells[9]) {
                if (result.validmail_results) {
                    const formattedValidmailResults = Object.entries(result.validmail_results).map(([module, result]) => {
                        const badgeClass = result ? 'bg-success' : 'bg-danger';
                        return `<span class="badge ${badgeClass} me-1 mb-1">${module}: ${result ? 'Valid' : 'Invalid'}</span>`;
                    }).join('');
                    cells[9].innerHTML = `<div style="max-width: 200px;">${formattedValidmailResults}</div>`;
                } else {
                    cells[9].innerHTML = '<span class="text-muted">Not checked</span>';
                }
            }

        } else {
            console.warn(`No row found for email: ${result.email}`);
        }
        
        if (completedTasks >= totalTasks && totalTasks > 0) {
            setTimeout(() => {
                closeOverlay();
            }, 1000);
        }
    });

});

function initializeStats(total) {
    totalTasks = total;
    completedTasks = 0;
    successfulTasks = 0;
    statsStartTime = new Date();
    
    document.getElementById('stats-panel').style.display = 'block';
    
    document.getElementById('total-tasks').textContent = totalTasks;
    document.getElementById('completed-tasks').textContent = '0';
    document.getElementById('success-rate').textContent = '0%';
    document.getElementById('progress-bar').style.width = '0%';
    
    if (statsInterval) clearInterval(statsInterval);
    statsInterval = setInterval(updateTimeElapsed, 1000);
}

function updateStats(success = true) {
    completedTasks++;
    if (success) successfulTasks++;
    
    const successRate = ((successfulTasks / completedTasks) * 100).toFixed(1);
    const progress = ((completedTasks / totalTasks) * 100).toFixed(1);
    
    document.getElementById('completed-tasks').textContent = completedTasks;
    document.getElementById('success-rate').textContent = `${successRate}%`;
    document.getElementById('progress-bar').style.width = `${progress}%`;
    
    if (completedTasks >= totalTasks) {
        clearInterval(statsInterval);
        setTimeout(() => {
            document.getElementById('stats-panel').style.display = 'none';
        }, 5000);
    }
}

function updateTimeElapsed() {
    if (!statsStartTime) return;
    
    const now = new Date();
    const diff = now - statsStartTime;
    const hours = Math.floor(diff / 3600000);
    const minutes = Math.floor((diff % 3600000) / 60000);
    const seconds = Math.floor((diff % 60000) / 1000);
    
    document.getElementById('time-elapsed').textContent = 
        `${String(hours).padStart(2, '0')}:${String(minutes).padStart(2, '0')}:${String(seconds).padStart(2, '0')}`;
}