// Professional Package Management Logic

function openAddPackageModal() {
    const form = document.getElementById('packageForm');
    document.getElementById('modalTitle').innerText = 'Create New Package';
    form.action = '/caterer/packages/add';
    form.reset();

    // Explicitly uncheck inclusions
    form.querySelectorAll('input[name="inclusions"]').forEach(input => {
        input.checked = false;
    });

    showModal();
}

function showModal() {
    document.getElementById('packageModal').style.display = 'flex';
}

function hideModal() {
    document.getElementById('packageModal').style.display = 'none';
}

function switchPackageTab(event, tabName) {
    const modalBody = event.currentTarget.closest('.modal-body-pro');
    modalBody.querySelectorAll('.tab-pane-pro').forEach(p => p.classList.remove('active'));
    event.currentTarget.parentElement.querySelectorAll('.mtab-btn').forEach(b => b.classList.remove('active'));

    document.getElementById('tab-' + tabName).classList.add('active');
    event.currentTarget.classList.add('active');
}

async function editPackage(pkgId) {
    try {
        const response = await fetch(`/caterer/packages/${pkgId}/details`);
        if (!response.ok) throw new Error('Failed to fetch');

        const pkg = await response.json();

        document.getElementById('modalTitle').innerText = 'Edit Package';
        const form = document.getElementById('packageForm');
        form.action = `/caterer/packages/${pkgId}/update`;

        // Populate fields
        form.name.value = pkg.name || '';
        form.description.value = pkg.description || '';
        form.service_type.value = pkg.service_type || 'General';
        form.price_per_head.value = pkg.price_per_head || '';
        form.min_contract_amount.value = pkg.min_contract_amount || '';
        form.min_guests.value = pkg.min_guests || 10;
        form.max_guests.value = pkg.max_guests || '';
        form.service_duration.value = pkg.service_duration || 4;

        // Handle inclusions
        const inclusions = pkg.inclusions || {};
        form.querySelectorAll('input[name="inclusions"]').forEach(input => {
            input.checked = !!inclusions[input.value];
        });

        showModal();
    } catch (error) {
        console.error('Edit fetch failed:', error);
        alert('Could not load package details.');
    }
}

async function togglePackageStatus(pkgId, element) {
    try {
        const response = await fetch(`/caterer/packages/${pkgId}/toggle`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' }
        });

        const data = await response.json();
        if (data.status === 'success') {
            const label = element.querySelector('.label');
            if (data.is_active) {
                element.classList.add('active');
                label.innerText = 'Available';
            } else {
                element.classList.remove('active');
                label.innerText = 'Hidden';
            }
        }
    } catch (error) {
        console.error('Toggle failed:', error);
    }
}

function showMenuModal(packageId, packageName) {
    document.getElementById('modalMenuPackageId').value = packageId;
    document.getElementById('targetPkgDisplay').innerText = `Package: ${packageName}`;
    document.getElementById('menuForm').action = `/caterer/packages/${packageId}/menu/add`;

    const container = document.getElementById('menuItemsContainer');
    container.innerHTML = '<div class="text-center p-4"><i class="fas fa-spinner fa-spin fa-2x text-primary"></i></div>';

    fetch(`/caterer/packages/${packageId}/menu`)
        .then(response => response.json())
        .then(data => {
            container.innerHTML = '';
            if (data && data.length > 0) {
                data.forEach(item => {
                    const row = document.createElement('div');
                    row.className = 'menu-item-pro-row';
                    row.innerHTML = `
                        <img src="${item.image_url || '/static/images/default_dish.jpg'}" class="dish-thumb">
                        <div class="dish-info-pro">
                            <h6>${item.name}</h6>
                            <span>${item.category} • ${item.is_addon ? 'Premium Add-on' : 'Included'}</span>
                        </div>
                        <button type="button" class="btn btn-link text-danger p-0" onclick="deleteMenuItem(${item.id})">
                            <i class="fas fa-times-circle"></i>
                        </button>
                    `;
                    container.appendChild(row);
                });
            } else {
                container.innerHTML = '<p class="text-center text-muted p-3">No items curated for this package yet.</p>';
            }
        });

    document.getElementById('menuModal').style.display = 'flex';
}

function hideMenuModal() {
    document.getElementById('menuModal').style.display = 'none';
}

async function deletePackage(pkgId) {
    if (!confirm('Are you sure you want to retire this package? This action cannot be undone.')) return;

    try {
        const response = await fetch(`/caterer/packages/${pkgId}`, { method: 'DELETE' });
        if (response.ok) {
            const card = document.getElementById(`package-${pkgId}`);
            if (card) {
                card.style.transform = 'scale(0.9)';
                card.style.opacity = '0';
                setTimeout(() => location.reload(), 400);
            } else {
                location.reload();
            }
        }
    } catch (error) {
        alert('Could not delete package. Please try again.');
    }
}

async function deleteMenuItem(itemId) {
    if (!confirm('Remove this dish from the menu?')) return;
    try {
        const response = await fetch(`/caterer/packages/menu/${itemId}/delete`, { method: 'POST' });
        if (response.ok) {
            const pkgId = document.getElementById('modalMenuPackageId').value;
            const pkgName = document.getElementById('targetPkgDisplay').innerText.replace('Package: ', '');
            showMenuModal(pkgId, pkgName);
        }
    } catch (error) {
        console.error('Error:', error);
    }
}

// Global Event Listeners
document.addEventListener('DOMContentLoaded', function () {
    // Add-on Price Toggle
    const isAddonCheck = document.getElementById('is_addon');
    if (isAddonCheck) {
        isAddonCheck.addEventListener('change', function () {
            const priceGroup = document.getElementById('addonPriceGroup');
            priceGroup.style.display = this.checked ? 'block' : 'none';
            if (this.checked) priceGroup.querySelector('input').focus();
        });
    }

    // AJAX Form Submission for Packages
    const pkgForm = document.getElementById('packageForm');
    if (pkgForm) {
        pkgForm.addEventListener('submit', async function (e) {
            e.preventDefault();
            const submitBtn = this.querySelector('button[type="submit"]');
            const originalText = submitBtn.innerText;
            submitBtn.disabled = true;
            submitBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Saving...';

            const formData = new FormData(this);
            try {
                const response = await fetch(this.action, {
                    method: 'POST',
                    body: formData
                });

                if (response.ok) {
                    hideModal();
                    location.reload();
                } else {
                    alert('Error saving package details.');
                    submitBtn.disabled = false;
                    submitBtn.innerText = originalText;
                }
            } catch (error) {
                console.error('Submission error:', error);
                submitBtn.disabled = false;
                submitBtn.innerText = originalText;
            }
        });
    }

    // AJAX Form Submission for Menu Items
    const menuForm = document.getElementById('menuForm');
    if (menuForm) {
        menuForm.addEventListener('submit', async function (e) {
            e.preventDefault();
            const submitBtn = this.querySelector('button[type="submit"]');
            const originalText = submitBtn.innerText;
            submitBtn.disabled = true;
            submitBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Curating...';

            const formData = new FormData(this);
            try {
                const response = await fetch(this.action, {
                    method: 'POST',
                    body: formData
                });
                if (response.ok) {
                    this.reset();
                    // Explicitly reset the addon group
                    document.getElementById('addonPriceGroup').style.display = 'none';

                    const pkgId = document.getElementById('modalMenuPackageId').value;
                    const pkgName = document.getElementById('targetPkgDisplay').innerText.replace('Package: ', '');
                    showMenuModal(pkgId, pkgName);

                    submitBtn.disabled = false;
                    submitBtn.innerText = originalText;
                } else {
                    alert('Failed to add dish.');
                    submitBtn.disabled = false;
                    submitBtn.innerText = originalText;
                }
            } catch (error) {
                console.error('Menu save error:', error);
                submitBtn.disabled = false;
                submitBtn.innerText = originalText;
            }
        });
    }
});

window.onclick = function (event) {
    if (event.target.classList.contains('modal-pro')) {
        hideModal();
        hideMenuModal();
    }
}

// Expose functions globally
window.openAddPackageModal = openAddPackageModal;
window.hideModal = hideModal;
window.switchPackageTab = switchPackageTab;
window.editPackage = editPackage;
window.togglePackageStatus = togglePackageStatus;
window.showMenuModal = showMenuModal;
window.hideMenuModal = hideMenuModal;
window.deletePackage = deletePackage;
window.deleteMenuItem = deleteMenuItem;
