/**
 * Profile Edit Functionality
 * Handles gallery items and other profile-specific client-side logic
 */

async function deleteGalleryItem(itemId) {
    if (!confirm('Are you sure you want to delete this image from your gallery?')) {
        return;
    }

    try {
        const response = await fetch(`/caterer/gallery/${itemId}/delete`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            }
        });

        if (response.ok) {
            // Remove the item from DOM or reload
            location.reload();
        } else {
            const data = await response.json();
            alert('Error: ' + (data.detail || 'Could not delete item'));
        }
    } catch (error) {
        console.error('Error deleting gallery item:', error);
        alert('An unexpected error occurred.');
    }
}

// Update hex code labels when color pickers change
document.addEventListener('DOMContentLoaded', function () {
    const colorPickers = document.querySelectorAll('input[type="color"]');
    colorPickers.forEach(picker => {
        picker.addEventListener('input', function () {
            const codeLabel = this.nextElementSibling;
            if (codeLabel && codeLabel.tagName === 'CODE') {
                codeLabel.textContent = this.value.toUpperCase();
            }
        });
    });
});
