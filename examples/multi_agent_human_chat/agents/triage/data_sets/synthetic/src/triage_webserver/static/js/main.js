document.addEventListener('DOMContentLoaded', function() {
    // Load recent datasets
    fetchRecentDatasets();

    // Handle dataset creation form submission
    const createDatasetForm = document.getElementById('createDatasetForm');
    if (createDatasetForm) {
        createDatasetForm.addEventListener('submit', function(e) {
            e.preventDefault();
            createDataset();
        });
    }
});

async function fetchRecentDatasets() {
    const recentDatasetsContainer = document.getElementById('recentDatasets');
    if (!recentDatasetsContainer) return;

    try {
        const response = await fetch('/api/datasets?limit=5');
        const data = await response.json();

        if (data.datasets.length === 0) {
            recentDatasetsContainer.innerHTML = '<p>No datasets found. Create your first one!</p>';
            return;
        }

        let html = '<div class="list-group">';
        data.datasets.forEach(dataset => {
            html += `
                <a href="/datasets?id=${dataset.id}" class="list-group-item list-group-item-action">
                    <div class="d-flex w-100 justify-content-between">
                        <h5 class="mb-1">${dataset.name}</h5>
                        <small>${new Date(dataset.created_at).toLocaleDateString()}</small>
                    </div>
                    <p class="mb-1">${dataset.description || 'No description'}</p>
                    <small>${dataset.total_examples} examples</small>
                </a>
            `;
        });
        html += '</div>';
        
        recentDatasetsContainer.innerHTML = html;
    } catch (error) {
        console.error('Error fetching recent datasets:', error);
        recentDatasetsContainer.innerHTML = '<div class="alert alert-danger">Error loading datasets</div>';
    }
}

async function createDataset() {
    const nameInput = document.getElementById('name');
    const descriptionInput = document.getElementById('description');
    const totalExamplesInput = document.getElementById('totalExamples');
    const modelInput = document.getElementById('model');

    const payload = {
        name: nameInput.value,
        description: descriptionInput.value || null,
        total_target: parseInt(totalExamplesInput.value),
        model: modelInput.value
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
            alert(result.message);
            nameInput.value = '';
            descriptionInput.value = '';
            totalExamplesInput.value = '100';
            modelInput.value = 'openai/gpt-4o-mini';
            
            // Refresh recent datasets
            fetchRecentDatasets();
        } else {
            const error = await response.json();
            alert(`Error: ${error.detail || 'Failed to create dataset'}`);
        }
    } catch (error) {
        console.error('Error creating dataset:', error);
        alert('An error occurred while creating the dataset');
    }
}