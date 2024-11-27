const recordsPerPage = 250;
let currentPage = 1;
let totalRecords = 0;
let currentFilters = {};

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
    const recoveryModuleList = document.getElementById('recovery-module-list');
    const validMailModuleList = document.getElementById('vm-module-list');

    function loadModules() {
        fetch('/get_modules')
            .then(response => response.json())
            .then(data => {
                const recoveryModules = data.modules;
                const validMailModules = data.validmail_modules;

                recoveryModuleList.innerHTML = '';
                validMailModuleList.innerHTML = '';

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

async function performValidMailCheck() {
    const selectedModules = Array.from(document.querySelectorAll('#validmail-module-selection-body input[type="checkbox"]:checked'))
        .map(checkbox => checkbox.value);

    if (selectedModules.length === 0) {
        alert('Please select at least one module to run.');
        return;
    }

    const selectedEmails = getSelectedEmails();
    if (selectedEmails.length === 0) {
        alert('Please select at least one email to perform the check.');
        return;
    }

    const threads = document.getElementById('threads').value;

    $('#validMailCheckModal').modal('hide');

    try {
        const response = await fetch('/perform_vm_check', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                threads: threads,
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

document.getElementById('validmail-modal-submit-btn').addEventListener('click', performValidMailCheck);


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

function exportToCSV() {
    getFilteredRecords().then(records => {
        if (records.length === 0) {
            alert('No records to export!');
            return;
        }

        const csvRows = [];
        const headers = ['Email', 'Status', 'Name', 'Phone Numbers', 'Address', 'DOB'];

        const validMailModules = new Set();
        records.forEach(record => {
            if (record.validmail_results) {
                Object.keys(record.validmail_results).forEach(module => validMailModules.add(module));
            }
        });

        const validMailHeaders = Array.from(validMailModules);
        csvRows.push([...headers, ...validMailHeaders].join('\t'));

        records.forEach(record => {
            const phoneNumbers = Array.isArray(record.phone_numbers) ? record.phone_numbers.join(', ') : record.phone_numbers || 'N/A';
            const row = [
                record.email,
                record.status || 'N/A',
                record.name || 'N/A',
                phoneNumbers,
                record.address || 'N/A',
                record.dob || 'N/A'
            ];

            validMailHeaders.forEach(module => {
                row.push(record.validmail_results && module in record.validmail_results ?
                    (record.validmail_results[module] ? 'Valid' : 'Invalid') :
                    'N/A');
            });

            csvRows.push(row.join('\t'));
        });

        const blob = new Blob([csvRows.join('\n')], {
            type: 'text/csv'
        });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = 'filtered_emails_with_validmail_results.csv';
        a.click();
        URL.revokeObjectURL(url);
    }).catch(error => {
        console.error('Error during export:', error);
    });
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
    const threads = document.getElementById('threads').value;
    const executeAll = document.getElementById('execute-all').checked;
    showOverlay("Loading, please wait...");
    let selectedEmails = executeAll ? await getAllMatchingEmails() : getSelectedEmails();

    if (selectedEmails.length === 0) {
        closeOverlay();
        alert('Please select at least one email to perform lookup.');
        return;
    }

    try {
        const response = await fetch('/perform_lookup', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                threads,
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

function getSelectedEmails() {
    return Array.from(document.querySelectorAll('input[name="selected_emails"]:checked'))
        .filter(checkbox => checkbox.closest('tr').style.display !== 'none')
        .map(checkbox => checkbox.closest('tr').querySelector('td:nth-child(2)').textContent.trim());
}

function applyFilters() {
    const domain = document.getElementById('filter-domain').value;
    const status = document.getElementById('status-filter').value;

    const selectedModules = Array.from(document.getElementById('module-filter').selectedOptions).map(option => option.value);

    currentFilters = {};
    if (domain) currentFilters.domain = domain;
    if (status) currentFilters.status = status;
    if (selectedModules.length > 0) currentFilters.module_results = selectedModules.reduce((acc, module) => {
        acc[module] = true;
        return acc;
    }, {});

    fetchRecords(currentPage, currentFilters);
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
    const threads = document.getElementById('threads').value;
    const executeAll = document.getElementById('execute-all').checked;
    let selectedEmails = executeAll ? await getAllMatchingEmails() : getSelectedEmails();

    if (selectedEmails.length === 0) {
        alert('Please select at least one email to perform recovery check.');
        return;
    }

    showOverlay("Loading, please wait...");
    try {
        const response = await fetch('/perform_recovery_check', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                threads,
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
        updateProgress(data.status);
    });

    socket.on('email_result', function(result) {
        const resultString = JSON.stringify(result, null, 2);
        updateProgress(resultString);
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