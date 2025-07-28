let currentDatasetId = null;
let currentPage = 1;
let pageSize = 10;
let totalDatasets = 0;
let examplesPage = 1;
let examplesPageSize = 5;

document.addEventListener('DOMContentLoaded', function() {
    // Load datasets
    fetchDatasets(currentPage, pageSize);

    // Handle dataset creation form submission
    const submitCreateDatasetBtn = document.getElementById('submitCreateDataset');
    if (submitCreateDatasetBtn) {
        submitCreateDatasetBtn.addEventListener('click', function() {
            createDataset();
        });
    }

    // Handle example editing form submission
    const submitEditExampleBtn = document.getElementById('submitEditExample');
    if (submitEditExampleBtn) {
        submitEditExampleBtn.addEventListener('click', function() {
            updateExample();
        });
    }
});

async function fetchDatasets(page, limit) {
    const datasetsListContainer = document.getElementById('datasetsList');
    if (!datasetsListContainer) return;

    try {
        const response = await fetch(`/api/datasets?skip=${(page - 1) * limit}&limit=${limit}`);
        const data = await response.json();
        totalDatasets = data.total;

        if (data.datasets.length === 0) {
            datasetsListContainer.innerHTML = '<p>No datasets found. Create your first one!</p>';
            return;
        }

        let html = '<div class="table-responsive"><table class="table table-hover">';
        html += `
            <thead>
                <tr>
                    <th>Name</th>
                    <th>Description</th>
                    <th>Examples</th>
                    <th>Model</th>
                    <th>Created</th>
                    <th>Actions</th>
                </tr>
            </thead>
            <tbody>
        `;
        
        data.datasets.forEach(dataset => {
            html += `
                <tr class="dataset-item">
                    <td>${dataset.name}</td>
                    <td>${dataset.description || '<em>No description</em>'}</td>
                    <td>${dataset.total_examples}</td>
                    <td>${dataset.model}</td>
                    <td>${new Date(dataset.created_at).toLocaleDateString()}</td>
                    <td>
                        <button class="btn btn-sm btn-primary view-examples-btn" data-dataset-id="${dataset.id}">
                            View Examples
                        </button>
                        <button class="btn btn-sm btn-danger delete-dataset-btn" data-dataset-id="${dataset.id}">
                            Delete
                        </button>
                    </td>
                </tr>
            `;
        });
        
        html += '</tbody></table></div>';
        datasetsListContainer.innerHTML = html;

        // Add event listeners to view and delete buttons
        document.querySelectorAll('.view-examples-btn').forEach(btn => {
            btn.addEventListener('click', function() {
                const datasetId = this.getAttribute('data-dataset-id');
                currentDatasetId = datasetId;
                examplesPage = 1;
                document.getElementById('viewExamplesModalLabel').textContent = `Dataset Examples (ID: ${datasetId})`;
                fetchExamples(datasetId, examplesPage, examplesPageSize);
                
                const viewExamplesModal = new bootstrap.Modal(document.getElementById('viewExamplesModal'));
                viewExamplesModal.show();
            });
        });

        document.querySelectorAll('.delete-dataset-btn').forEach(btn => {
            btn.addEventListener('click', function() {
                const datasetId = this.getAttribute('data-dataset-id');
                if (confirm('Are you sure you want to delete this dataset? This cannot be undone.')) {
                    deleteDataset(datasetId);
                }
            });
        });

        // Update pagination
        updatePagination(page, Math.ceil(totalDatasets / limit), 'datasetPagination', fetchDatasets);
    } catch (error) {
        console.error('Error fetching datasets:', error);
        datasetsListContainer.innerHTML = '<div class="alert alert-danger">Error loading datasets</div>';
    }
}

async function fetchExamples(datasetId, page, limit) {
    const examplesListContainer = document.getElementById('examplesList');
    if (!examplesListContainer) return;

    try {
        const response = await fetch(`/api/examples?dataset_id=${datasetId}&skip=${(page - 1) * limit}&limit=${limit}`);
        const data = await response.json();

        if (data.examples.length === 0) {
            examplesListContainer.innerHTML = '<p>No examples found in this dataset.</p>';
            return;
        }

        let html = '';
        data.examples.forEach(example => {
            html += `
                <div class="card mb-3">
                    <div class="card-header d-flex justify-content-between align-items-center">
                        <span><strong>Target: ${example.target_agent}</strong></span>
                        <div>
                            <button class="btn btn-sm btn-primary edit-example-btn" data-example-id="${example.id}">
                                Edit
                            </button>
                            <button class="btn btn-sm btn-danger delete-example-btn" data-example-id="${example.id}">
                                Delete
                            </button>
                        </div>
                    </div>
                    <div class="card-body">
                        <div class="conversation-box">${example.conversation}</div>
                        <div class="example-meta">
                            <span class="me-3">Turns: ${example.turns}</span>
                            <span class="me-3">Temperature: ${example.temperature}</span>
                            <span>Special Case: ${example.special_case || 'None'}</span>
                        </div>
                    </div>
                </div>
            `;
        });
        
        examplesListContainer.innerHTML = html;

        // Add event listeners to example edit and delete buttons
        document.querySelectorAll('.edit-example-btn').forEach(btn => {
            btn.addEventListener('click', function() {
                const exampleId = this.getAttribute('data-example-id');
                prepareExampleForEditing(exampleId);
            });
        });

        document.querySelectorAll('.delete-example-btn').forEach(btn => {
            btn.addEventListener('click', function() {
                const exampleId = this.getAttribute('data-example-id');
                if (confirm('Are you sure you want to delete this example? This cannot be undone.')) {
                    deleteExample(exampleId);
                }
            });
        });

        // Update pagination
        updatePagination(page, Math.ceil(data.total / limit), 'examplesPagination', function(newPage, newLimit) {
            examplesPage = newPage;
            fetchExamples(currentDatasetId, newPage, newLimit);
        });
    } catch (error) {
        console.error('Error fetching examples:', error);
        examplesListContainer.innerHTML = '<div class="alert alert-danger">Error loading examples</div>';
    }
}

async function prepareExampleForEditing(exampleId) {
    try {
        const response = await fetch(`/api/examples/${exampleId}`);
        const example = await response.json();

        document.getElementById('editExampleId').value = example.id;
        document.getElementById('editConversation').value = example.conversation;
        document.getElementById('editTargetAgent').value = example.target_agent;
        document.getElementById('editTurns').value = example.turns;
        document.getElementById('editTemperature').value = example.temperature;
        document.getElementById('editSpecialCase').value = example.special_case || '';

        const editExampleModal = new bootstrap.Modal(document.getElementById('editExampleModal'));
        editExampleModal.show();
    } catch (error) {
        console.error('Error fetching example for editing:', error);
        alert('Error loading example data');
    }
}

async function updateExample() {
    const exampleId = document.getElementById('editExampleId').value;
    
    const payload = {
        conversation: document.getElementById('editConversation').value,
        target_agent: document.getElementById('editTargetAgent').value,
        turns: parseInt(document.getElementById('editTurns').value),
        temperature: parseFloat(document.getElementById('editTemperature').value),
        special_case: document.getElementById('editSpecialCase').value || null
    };

    try {
        const response = await fetch(`/api/examples/${exampleId}`, {
            method: 'PUT',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(payload)
        });

        if (response.ok) {
            const editExampleModal = bootstrap.Modal.getInstance(document.getElementById('editExampleModal'));
            editExampleModal.hide();
            
            // Refresh examples
            fetchExamples(currentDatasetId, examplesPage, examplesPageSize);
            alert('Example updated successfully');
        } else {
            const error = await response.json();
            alert(`Error: ${error.detail || 'Failed to update example'}`);
        }
    } catch (error) {
        console.error('Error updating example:', error);
        alert('An error occurred while updating the example');
    }
}

async function deleteExample(exampleId) {
    try {
        const response = await fetch(`/api/examples/${exampleId}`, {
            method: 'DELETE'
        });

        if (response.ok) {
            // Refresh examples
            fetchExamples(currentDatasetId, examplesPage, examplesPageSize);
            alert('Example deleted successfully');
        } else {
            const error = await response.json();
            alert(`Error: ${error.detail || 'Failed to delete example'}`);
        }
    } catch (error) {
        console.error('Error deleting example:', error);
        alert('An error occurred while deleting the example');
    }
}

async function deleteDataset(datasetId) {
    try {
        const response = await fetch(`/api/datasets/${datasetId}`, {
            method: 'DELETE'
        });

        if (response.ok) {
            // Refresh datasets
            fetchDatasets(currentPage, pageSize);
            alert('Dataset deleted successfully');
        } else {
            const error = await response.json();
            alert(`Error: ${error.detail || 'Failed to delete dataset'}`);
        }
    } catch (error) {
        console.error('Error deleting dataset:', error);
        alert('An error occurred while deleting the dataset');
    }
}

async function createDataset() {
    const nameInput = document.getElementById('name');
    const descriptionInput = document.getElementById('description');
    const totalExamplesInput = document.getElementById('totalExamples');
    const modelInput = document.getElementById('model');

    // Get selected turns
    const selectedTurns = [];
    if (document.getElementById('turn1').checked) selectedTurns.push(1);
    if (document.getElementById('turn3').checked) selectedTurns.push(3);
    if (document.getElementById('turn5').checked) selectedTurns.push(5);

    // Get selected temperatures
    const selectedTemps = [];
    if (document.getElementById('temp07').checked) selectedTemps.push(0.7);
    if (document.getElementById('temp08').checked) selectedTemps.push(0.8);
    if (document.getElementById('temp09').checked) selectedTemps.push(0.9);

    // Validate selections
    if (selectedTurns.length === 0) {
        alert('Please select at least one turn value');
        return;
    }

    if (selectedTemps.length === 0) {
        alert('Please select at least one temperature value');
        return;
    }

    const payload = {
        name: nameInput.value,
        description: descriptionInput.value || null,
        total_target: parseInt(totalExamplesInput.value),
        model: modelInput.value,
        turns: selectedTurns,
        temperatures: selectedTemps
    };

    try {
        const response = await fetch('/api/datasets', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(payload)
        });

        if (response.ok) {
            const result = await response.json();
            const createDatasetModal = bootstrap.Modal.getInstance(document.getElementById('createDatasetModal'));
            createDatasetModal.hide();
            
            // Refresh datasets
            fetchDatasets(currentPage, pageSize);
            alert(result.message);
        } else {
            const error = await response.json();
            alert(`Error: ${error.detail || 'Failed to create dataset'}`);
        }
    } catch (error) {
        console.error('Error creating dataset:', error);
        alert('An error occurred while creating the dataset');
    }
}

function updatePagination(currentPage, totalPages, paginationId, callback) {
    const paginationContainer = document.getElementById(paginationId);
    if (!paginationContainer) return;

    let html = '';
    
    // Previous button
    html += `
        <li class="page-item ${currentPage === 1 ? 'disabled' : ''}">
            <a class="page-link" href="#" data-page="${currentPage - 1}" aria-label="Previous">
                <span aria-hidden="true">&laquo;</span>
            </a>
        </li>
    `;
    
    // Page numbers
    const maxVisiblePages = 5;
    let startPage = Math.max(1, currentPage - Math.floor(maxVisiblePages / 2));
    let endPage = Math.min(totalPages, startPage + maxVisiblePages - 1);
    
    if (endPage - startPage + 1 < maxVisiblePages) {
        startPage = Math.max(1, endPage - maxVisiblePages + 1);
    }
    
    for (let i = startPage; i <= endPage; i++) {
        html += `
            <li class="page-item ${i === currentPage ? 'active' : ''}">
                <a class="page-link" href="#" data-page="${i}">${i}</a>
            </li>
        `;
    }
    
    // Next button
    html += `
        <li class="page-item ${currentPage === totalPages ? 'disabled' : ''}">
            <a class="page-link" href="#" data-page="${currentPage + 1}" aria-label="Next">
                <span aria-hidden="true">&raquo;</span>
            </a>
        </li>
    `;
    
    paginationContainer.innerHTML = html;
    
    // Add event listeners to pagination links
    paginationContainer.querySelectorAll('.page-link').forEach(link => {
        link.addEventListener('click', function(e) {
            e.preventDefault();
            const page = parseInt(this.getAttribute('data-page'));
            if (page > 0 && page <= totalPages) {
                callback(page, pageSize);
            }
        });
    });
}