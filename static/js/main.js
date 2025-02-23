// Change semester tabs
function showSemester(semester) {
    // Hide all semester contents
    document.querySelectorAll('.semester-content').forEach(content => {
        content.style.display = 'none';
    });

    // Show selected semester
    document.getElementById(semester).style.display = 'block';

    // Update active tab style
    document.querySelectorAll('.tab-btn').forEach(btn => {
        btn.classList.remove('active');
        if (btn.textContent.includes(semester)) {
            btn.classList.add('active');
        }
    });
}

// Image upload preview
document.addEventListener('DOMContentLoaded', function() {
    const imageInput = document.getElementById('image');
    if (imageInput) {
        imageInput.addEventListener('change', function() {
            const file = this.files[0];
            if (file) {
                const reader = new FileReader();
                reader.onload = function(e) {
                    const preview = document.createElement('img');
                    preview.src = e.target.result;
                    preview.className = 'image-preview';

                    const existingPreview = document.querySelector('.image-preview');
                    if (existingPreview) {
                        existingPreview.remove();
                    }

                    imageInput.parentNode.appendChild(preview);
                }
                reader.readAsDataURL(file);
            }
        });
    }
});

// Image preview style
document.head.insertAdjacentHTML('beforeend', `
    <style>
        .image-preview {
            max-width: 200px;
            max-height: 200px;
            margin-top: 10px;
            border-radius: 4px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
    </style>
`);

// Edit note function
function editNote(noteId, button) {
    const noteCard = button.closest('.note-card');
    const noteContent = noteCard.querySelector('.note-text');
    const currentText = noteContent.textContent;

    // Create edit area
    const editArea = document.createElement('div');
    editArea.className = 'edit-area';
    editArea.innerHTML = `
        <textarea class="note-textarea editing">${currentText}</textarea>
        <div class="edit-actions">
            <button class="save-btn" onclick="saveNote(${noteId}, this)">
                <i class="fas fa-save"></i> Save
            </button>
            <button class="cancel-btn" onclick="cancelEdit(this)">
                <i class="fas fa-times"></i> Cancel
            </button>
        </div>
    `;

    // Hide original content and insert edit area
    noteContent.style.display = 'none';
    noteContent.parentNode.insertBefore(editArea, noteContent.nextSibling);
}

// Save edited note
function saveNote(noteId, button) {
    const editArea = button.closest('.edit-area');
    const noteCard = editArea.closest('.note-card');
    const textarea = editArea.querySelector('textarea');
    const noteContent = noteCard.querySelector('.note-text');
    const newText = textarea.value;

    // AJAX request to update the note
    fetch(`/update_note/${noteId}`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({ note: newText })
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            noteContent.textContent = newText;
            noteContent.style.display = 'block';
            editArea.remove();
        } else {
            alert('An error occurred while updating the note!');
        }
    })
    .catch(error => {
        console.error('Error:', error);
        alert('An error occurred while updating the note!');
    });
}

// Cancel editing
function cancelEdit(button) {
    const editArea = button.closest('.edit-area');
    const noteContent = editArea.previousElementSibling;
    noteContent.style.display = 'block';
    editArea.remove();
}
