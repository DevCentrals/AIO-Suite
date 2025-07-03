const recordsPerPage = 250;
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


const openPanelBtn = document.getElementById('open-panel-btn');
const modulePanel = document.getElementById('module-panel');
const closePanelBtn = document.getElementById('close-panel-btn');
const moduleList = document.getElementById('module-list');
document.getElementById('export-csv-btn').onclick = showExportFormatModal;

dropArea.addEventListener("dragover", (event) => {
    event.preventDefault();
    dropArea.style.borderColor = "#0056b3";
});

dropArea.addEventListener("dragleave", () => {
    dropArea.style.borderColor = "#007bff";
});

dropArea.addEventListener("drop", (event) => {
    event.preventDefault();
    dropArea.style.borderColor = "#007bff";

    const file = event.dataTransfer.files[0];
    if (file) {
        emailInputField.files = event.dataTransfer.files;
        fileNameSpan.textContent = file.name;
        fileNameDisplay.style.display = "block";
        uploadBtn.style.display = "inline-block";
        uploadForm.style.display = "block";
    }
});

dropArea.addEventListener("click", () => {
    fileInput.click();
});

fileInput.addEventListener("change", () => {
    if (fileInput.files.length > 0) {
        emailInputField.files = fileInput.files;
        const file = fileInput.files[0];
        fileNameSpan.textContent = file.name;
        fileNameDisplay.style.display = "block";
        uploadBtn.style.display = "inline-block";
        uploadForm.style.display = "block";
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
        alert('Please select at least one module to run.');
        return;
    }

    const selectedEmails = executeAll ? await getAllMatchingEmails() : getSelectedEmails();
    if (selectedEmails.length === 0) {
        alert('Please select at least one email to perform the check.');
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
            alert('Valid-mail check completed.');
        } else {
            alert('An error occurred during the valid-mail check.');
        }
    } catch (error) {
        console.error('Error during valid-mail check:', error);
        alert('An error occurred. Please try again.');
    }
}


document.getElementById('perform-validmailcheck-btn').addEventListener('click', showValidMailCheckModal);
document.getElementById('perform-search-btn').addEventListener('click', showSearchModal);
document.getElementById('validmail-modal-submit-btn').addEventListener('click', performValidMailCheck);
document.getElementById('search-modal-submit-btn').addEventListener('click', performLookup);

async function fetchRecords(page = 1, filters = currentFilters) {
    try {
        const response = await fetch(`/get_emails?page=${page}&records_per_page=${recordsPerPage}&filters=${JSON.stringify(filters)}`);
        const data = await response.json();

        tableBody.innerHTML = data.records.map(record => {
            const formattedValidmailResults = record.validmail_results ?
                Object.entries(record.validmail_results).map(([module, result]) => {
                    return `<strong>${module}</strong>: ${result ? 'Valid' : 'Invalid'}`;
                }).join('<br>') :
                'N/A';

            const row = `
                <tr id="email-${CSS.escape(record.email)}" data-email="${CSS.escape(record.email)}">
                    <td><input type="checkbox" name="selected_emails" value="${record.id}"></td>
                    <td>${record.email}</td>
                    <td id="status-${CSS.escape(record.email)}">${record.status || 'N/A'}</td>
                    <td id="name-${CSS.escape(record.email)}">${record.name || 'N/A'}</td>
                    <td id="phone_numbers-${CSS.escape(record.email)}">${record.phone_numbers || 'N/A'}</td>
                    <td id="address-${CSS.escape(record.email)}">${record.address || 'N/A'}</td>
                    <td id="dob-${CSS.escape(record.email)}">${record.dob || 'N/A'}</td>
                    <td id="validmail_results-${CSS.escape(record.email)}">${formattedValidmailResults}</td>
                </tr>`;
            return row;
        }).join('');

        totalRecords = data.total;
        totalRecordsElem.textContent = `Total Records: ${totalRecords}`;
        updatePagination();
        populateStatusOptions(data.statuses);
        populateModuleFilter();
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

        // Attach event listener to the Export button
        const exportButton = document.getElementById('exportButton');
        exportButton.addEventListener('click', async (event) => {
            console.log('Export button clicked, isTrusted:', event.isTrusted);
            try {
                // Disable the button to prevent multiple clicks
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
    // Show loading indicator
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
        // Fetch records
        const records = await getFilteredRecords();
        if (records.length === 0) {
            alert('No records to export!');
            return;
        }

        // Prepare file content
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
        
        // Prepare headers
        const headers = selectedColumns.map(col => {
            switch (col) {
                case 'name': return 'Full Name';
                case 'phone_numbers': return 'Phone Numbers';
                case 'validmail_results': return 'ValidMail Results';
                default: return col.charAt(0).toUpperCase() + col.slice(1);
            }
        });
        rows.push(headers.join(separator));

        // Process each record
        records.forEach(record => {
            const row = selectedColumns.map(col => {
                let value = record[col] || 'N/A';
                
                // Format specific fields
                if (col === 'phone_numbers') {
                    value = Array.isArray(value) ? 
                        value.join('; ').replace(/\r?\n|\r/g, ' ') : 
                        value.toString().replace(/\r?\n|\r/g, ' ');
                } else if (col === 'validmail_results') {
                    value = value ? Object.entries(value)
                        .map(([module, result]) => `${module}:${result ? 'Valid' : 'Invalid'}`)
                        .join('; ') : 'N/A';
                }

                // Clean up the value
                value = value.toString()
                    .replace(/\r?\n|\r/g, ' ')  // Replace newlines with spaces
                    .replace(/\s+/g, ' ')        // Collapse multiple spaces
                    .trim();                     // Trim whitespace

                // Handle CSV escaping
                if (format === 'csv') {
                    if (value.includes('"')) {
                        value = value.replace(/"/g, '""'); // Escape double quotes
                    }
                    if (value.includes(',')) {
                        value = `"${value}"`; // Wrap in quotes if contains separator
                    }
                }

                return value;
            });
            rows.push(row.join(separator));
        });

        const fileContent = rows.join('\n');
        const fileType = format === 'csv' ? 'text/csv' : 'text/plain';
        const fileExtension = format === 'csv' ? 'csv' : format === 'tsv' ? 'tsv' : 'txt';

        // Prompt user to confirm file save
        const confirmSave = confirm(`Export data is ready (${records.length} records). Click OK to save as ${fileExtension.toUpperCase()} file.`);
        if (!confirmSave) {
            alert('Export canceled.');
            return;
        }

        // Save file
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
                // Fallback for browsers without File System Access API
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
        // Remove loading indicator
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
    // Fetch records
    const records = await getFilteredRecords();
    if (records.length === 0) {
        alert('No records to export!');
        return;
    }

    // Get export settings
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
    
    // Prepare headers
    const headers = selectedColumns.map(col => {
        switch (col) {
            case 'name': return 'Full Name';
            case 'phone_numbers': return 'Phone Numbers';
            case 'validmail_results': return 'ValidMail Results';
            default: return col.charAt(0).toUpperCase() + col.slice(1);
        }
    });
    rows.push(headers.join(separator));

    // Process each record
    records.forEach(record => {
        const row = selectedColumns.map(col => {
            let value = record[col] || 'N/A';
            
            // Format specific fields
            if (col === 'phone_numbers') {
                value = Array.isArray(value) ? 
                    value.join('; ').replace(/\r?\n|\r/g, ' ') : 
                    value.toString().replace(/\r?\n|\r/g, ' ');
            } else if (col === 'validmail_results') {
                value = value ? Object.entries(value)
                    .map(([module, result]) => `${module}:${result ? 'Valid' : 'Invalid'}`)
                    .join('; ') : 'N/A';
            }

            // Clean up the value
            value = value.toString()
                .replace(/\r?\n|\r/g, ' ')  // Replace newlines with spaces
                .replace(/\s+/g, ' ')        // Collapse multiple spaces
                .trim();                     // Trim whitespace

            // Handle CSV escaping
            if (format === 'csv') {
                if (value.includes('"')) {
                    value = value.replace(/"/g, '""'); // Escape double quotes
                }
                if (value.includes(',')) {
                    value = `"${value}"`; // Wrap in quotes if contains separator
                }
            }

            return value;
        });
        rows.push(row.join(separator));
    });

    const fileContent = rows.join('\n');
    const fileType = format === 'csv' ? 'text/csv' : 'text/plain';
    const fileExtension = format === 'csv' ? 'csv' : format === 'tsv' ? 'tsv' : 'txt';

    // Save file
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
            // Fallback for browsers without File System Access API
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

    // Close modal
    const modal = bootstrap.Modal.getInstance(document.getElementById('exportFormatModal'));
    modal.hide();
}


async function getFilteredRecords() {
    const filters = {
        ...currentFilters
    };

    try {
        const response = await fetch(`/get_emails?filters=${JSON.stringify(filters)}&fetch_all=true`);
        const data = await response.json();
        return data.records || [];
    } catch (error) {
        console.error('Error fetching filtered records:', error);
        return [];
    }
}

function loadSettings() {
    fetch('/get_settings')
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                const settingsContent = document.getElementById('settings-content');
                settingsContent.innerHTML = '';
                for (const [key, value] of Object.entries(data.settings)) {
                    const formGroup = `
                        <div class="mb-3">
                            <label for="${key}" class="form-label">${key}</label>
                            <input type="text" class="form-control" id="${key}" name="${key}" value="${value}">
                        </div>`;
                    settingsContent.innerHTML += formGroup;
                }
            } else {
                alert('Failed to load settings: ' + data.message);
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
    const executeAll = document.getElementById('execute-all').checked;
    const selectedModules = Array.from(document.querySelectorAll('#search-module-selection-body input[type="checkbox"]:checked'))
        .map(checkbox => checkbox.value);

    if (selectedModules.length === 0) {
        alert('Please select at least one module to run.');
        return;
    }

    showOverlay("Loading, please wait...");
    const selectedEmails = executeAll ? await getAllMatchingEmails() : getSelectedEmails();
    console.log(selectedEmails);
    initializeStats(selectedEmails.length);

    if (selectedEmails.length === 0) {
        closeOverlay();
        alert('Please select at least one email to perform the check.');
        return;
    }

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
            alert('Search completed.');
        } else {
            alert('An error occurred during the search.');
        }
    } catch (error) {
        console.error('Error during Search:', error);
        alert('An error occurred. Please try again.');
    } finally {
        closeOverlay();
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
  
  document.getElementById('vm-status').value = '';
  document.getElementById('module-filter').selectedIndex = -1;
  
  currentFilters = {};
  fetchRecords(1);
}

function applyFilters() {
    currentFilters = {};
    
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
    
    const vmStatus = document.getElementById('vm-status').value;
    if (vmStatus) {
      currentFilters.vm_status = vmStatus;
    }
    
    const selectedModules = Array.from(document.getElementById('module-filter').selectedOptions)
      .map(option => option.value);
    
    if (selectedModules.length > 0) {
      currentFilters.module_results = {};
      selectedModules.forEach(module => {
        currentFilters.module_results[module] = true; // Default to valid
      });
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
  
          return `
            <tr id="email-${CSS.escape(record.email)}" data-email="${CSS.escape(record.email)}">
              <td><input type="checkbox" name="selected_emails" value="${record.id}"></td>
              <td>${record.email}</td>
              <td id="status-${CSS.escape(record.email)}">${record.status || 'N/A'}</td>
              <td id="name-${CSS.escape(record.email)}">${record.name || 'N/A'}</td>
              <td id="phone_numbers-${CSS.escape(record.email)}">${record.phone_numbers || 'N/A'}</td>
              <td id="address-${CSS.escape(record.email)}">${record.address || 'N/A'}</td>
              <td id="dob-${CSS.escape(record.email)}">${record.dob || 'N/A'}</td>
              <td id="validmail_results-${CSS.escape(record.email)}">${formattedValidmailResults}</td>
            </tr>`;
        }).join('');
  
        totalRecords = data.total;
        totalRecordsElem.textContent = `Total Records: ${totalRecords}`;
        updatePagination();
        populateStatusOptions(data.statuses);
        populateModuleFilter();
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
            fetchRecords(currentPage, currentFilters); // Refresh the table
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
            fetchRecords(1, currentFilters); // Reset to first page and refresh
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
            fetchRecords(1); // Reset to first page with no filters
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

        moduleFilter.innerHTML = '';

        data.validmail_modules.forEach(module => {
            const option = document.createElement('option');
            option.value = module.module_name;
            option.textContent = module.name;
            moduleFilter.appendChild(option);
        });
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
    const filters = {
        domain: document.getElementById('filter-domain').value,
        status: statusFilter.value
    };
    const url = `/get_emails?filters=${JSON.stringify(filters)}&fetch_all=${fetchAll}`;

    return fetch(url)
        .then(response => response.json())
        .then(data => data.records.map(record => record.email))
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
    fetchRecords();

    const socket = io();

    socket.on('task_status', function(data) {
        if (data.status === 'started') {
            initializeStats(data.total);
        }
        updateProgress(data.status);
    });

    socket.on('email_result', function(result) {
        const resultString = JSON.stringify(result, null, 2);
        updateProgress(resultString);
        updateStats(result.success !== false);
        
        const escapedEmail = CSS.escape(result.email);
        const row = document.getElementById(`email-${escapedEmail}`);

        if (row) {

            const statusCell = document.getElementById(`status-${escapedEmail}`);
            const nameCell = document.getElementById(`name-${escapedEmail}`);
            const phoneNumbersCell = document.getElementById(`phone_numbers-${escapedEmail}`);
            const addressCell = document.getElementById(`address-${escapedEmail}`);
            const dobCell = document.getElementById(`dob-${escapedEmail}`);
            const validmailResultsCell = document.getElementById(`validmail_results-${escapedEmail}`);

            if (statusCell) statusCell.textContent = result.status || 'Autodoxed';
            if (nameCell) nameCell.textContent = result.name || 'N/A';
            if (phoneNumbersCell) phoneNumbersCell.textContent = result.phone_numbers ? result.phone_numbers.join(', ') : 'N/A';
            if (addressCell) addressCell.textContent = result.address || 'N/A';
            if (dobCell) dobCell.textContent = result.dob || 'N/A';

            if (validmailResultsCell) {
                if (result.validmail_results) {
                    const formattedValidmailResults = Object.entries(result.validmail_results).map(([module, result]) => {
                        return `<strong>${module}</strong>: ${result ? 'Valid' : 'Invalid'}`;
                    }).join('<br>');
                    validmailResultsCell.innerHTML = formattedValidmailResults;
                } else {
                    validmailResultsCell.textContent = 'N/A';
                }
            }

        } else {
            console.warn(`No row found for email: ${result.email}`);
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