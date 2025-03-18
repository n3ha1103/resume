document.addEventListener('DOMContentLoaded', function() {
    // DOM Elements
    const uploadArea = document.getElementById('upload-area');
    const fileInput = document.getElementById('file-input');
    const fileInfo = document.getElementById('file-info');
    const sectionList = document.getElementById('section-list');
    const searchInput = document.getElementById('search-input');
    const searchButton = document.getElementById('search-button');
    const contentTitle = document.getElementById('content-title');
    const viewContent = document.getElementById('view-content');
    const editContent = document.getElementById('edit-content');
    const editTextarea = document.getElementById('edit-textarea');
    const editButton = document.getElementById('edit-button');
    const saveButton = document.getElementById('save-button');
    const cancelButton = document.getElementById('cancel-button');
    const statusBar = document.getElementById('status-bar');
    
    // Current state
    let currentSection = 'all';
    let isEditing = false;
    
    // Event Listeners
    uploadArea.addEventListener('click', () => fileInput.click());
    
    uploadArea.addEventListener('dragover', (e) => {
        e.preventDefault();
        uploadArea.style.borderColor = '#4CAF50';
        uploadArea.style.backgroundColor = '#f9f9f9';
    });
    
    uploadArea.addEventListener('dragleave', () => {
        uploadArea.style.borderColor = '#ccc';
        uploadArea.style.backgroundColor = '';
    });
    
    uploadArea.addEventListener('drop', (e) => {
        e.preventDefault();
        uploadArea.style.borderColor = '#ccc';
        uploadArea.style.backgroundColor = '';
        
        if(e.dataTransfer.files.length) {
            handleFileUpload(e.dataTransfer.files[0]);
        }
    });
    
    fileInput.addEventListener('change', () => {
        if(fileInput.files.length) {
            handleFileUpload(fileInput.files[0]);
        }
    });
    
    sectionList.addEventListener('click', (e) => {
        if(e.target.tagName === 'LI') {
            const section = e.target.getAttribute('data-section');
            loadSection(section);
            
            // Update active class
            document.querySelectorAll('#section-list li').forEach(li => {
                li.classList.remove('active');
            });
            e.target.classList.add('active');
        }
    });
    
    searchButton.addEventListener('click', performSearch);
    searchInput.addEventListener('keypress', (e) => {
        if(e.key === 'Enter') {
            performSearch();
        }
    });
    
    editButton.addEventListener('click', () => {
        startEditing();
    });
    
    saveButton.addEventListener('click', () => {
        saveChanges();
    });
    
    cancelButton.addEventListener('click', () => {
        cancelEditing();
    });
    
    // Functions
    async function handleFileUpload(file) {
        updateStatus(`Processing file: ${file.name}...`);
        
        const formData = new FormData();
        formData.append('file', file);
        
        try {
            const response = await fetch('/upload', {
                method: 'POST',
                body: formData
            });
            
            const data = await response.json();
            
            if(data.status === 'success') {
                fileInfo.textContent = `File: ${file.name}`;
                updateStatus(data.message);
                enableEditButton();
                loadSection('all');
                
                // Set all sections as active
                document.querySelector('#section-list li[data-section="all"]').classList.add('active');
                document.querySelectorAll('#section-list li:not([data-section="all"])').forEach(li => {
                    li.classList.remove('active');
                });
            } else {
                updateStatus(`Error: ${data.message}`);
            }
        } catch(error) {
            updateStatus(`Error uploading file: ${error.message}`);
        }
    }
    
    async function loadSection(section) {
        currentSection = section;
        
        try {
            const response = await fetch(`/get_section/${section}`);
            const data = await response.json();
            
            if(data.status === 'success') {
                contentTitle.textContent = data.title;
                viewContent.textContent = data.content || 'No content available for this section.';
                
                if(isEditing) {
                    editTextarea.value = data.content || '';
                }
                
                updateStatus(`Section ${data.title} loaded.`);
            } else {
                updateStatus(`Error: ${data.message}`);
            }
        } catch(error) {
            updateStatus(`Error loading section: ${error.message}`);
        }
    }
    
    async function performSearch() {
        const query = searchInput.value.trim();
        
        if(!query) {
            updateStatus('Please enter a search term.');
            return;
        }
        
        try {
            const response = await fetch('/search', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ query })
            });
            
            const data = await response.json();
            
            if(data.status === 'success') {
                contentTitle.textContent = `Search Results for "${query}"`;
                
                const resultsHTML = data.results.join('<br><br>').replace(
                    new RegExp(`(${query})`, 'gi'),
                    '<span class="highlight">$1</span>'
                );
                
                viewContent.innerHTML = resultsHTML || 'No results found.';
                updateStatus(`Search completed for "${query}".`);
            } else {
                updateStatus(`Error: ${data.message}`);
            }
        } catch(error) {
            updateStatus(`Error during search: ${error.message}`);
        }
    }
    
    function startEditing() {
        isEditing = true;
        
        // Show edit content and hide view content
        viewContent.style.display = 'none';
        editContent.style.display = 'block';
        
        // Load current content into textarea
        editTextarea.value = viewContent.textContent;
        
        // Update button states
        editButton.disabled = true;
        saveButton.disabled = false;
        cancelButton.disabled = false;
        
        updateStatus('Editing mode. Make changes and click Save when done.');
    }
    
    async function saveChanges() {
        const content = editTextarea.value;
        const section = currentSection === 'all' ? 'full_resume' : currentSection;
        
        try {
            const response = await fetch('/update_section', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    section,
                    content
                })
            });
            
            const data = await response.json();
            
            if(data.status === 'success') {
                // Exit edit mode
                exitEditMode();
                
                // Reload the section to show updated content
                loadSection(currentSection);
                
                updateStatus(`${section === 'full_resume' ? 'Full resume' : section} updated successfully.`);
            } else {
                updateStatus(`Error: ${data.message}`);
            }
        } catch(error) {
            updateStatus(`Error saving changes: ${error.message}`);
        }
    }
    
    function cancelEditing() {
        exitEditMode();
        loadSection(currentSection);
        updateStatus('Editing cancelled.');
    }
    
    function exitEditMode() {
        isEditing = false;
        
        // Show view content and hide edit content
        viewContent.style.display = 'block';
        editContent.style.display = 'none';
        
        // Update button states
        editButton.disabled = false;
        saveButton.disabled = true;
        cancelButton.disabled = true;
    }
    
    function enableEditButton() {
        editButton.disabled = false;
    }
    
    function updateStatus(message) {
        statusBar.textContent = message;
    }
});
   

