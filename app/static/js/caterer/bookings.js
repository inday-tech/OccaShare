document.addEventListener('DOMContentLoaded', function () {
    // Add click listeners to all detail buttons
    document.querySelectorAll('.view-details').forEach(btn => {
        btn.addEventListener('click', function () {
            showBookingDetails(this);
        });
    });
});

function showBookingDetails(btn) {
    const data = btn.dataset;
    const modal = document.getElementById('bookingDetailModal');
    if (!modal) return;

    document.getElementById('modalBookingId').innerText = `Booking #${data.id}`;
    document.getElementById('modalCustomer').innerText = data.customer;
    document.getElementById('modalEmail').innerText = data.email;
    document.getElementById('modalEventName').innerText = data.eventName;
    document.getElementById('modalEventType').innerText = data.eventType;
    document.getElementById('modalVenue').innerText = data.venue;
    document.getElementById('modalRequests').innerText = data.requests;

    // Status styling
    const statusEl = document.getElementById('modalStatus');
    statusEl.innerText = data.status;
    const statusColors = {
        'pending': { color: '#92400e', bg: '#fef3c7' },
        'confirmed': { color: '#166534', bg: '#dcfce7' },
        'completed': { color: '#1e40af', bg: '#dbeafe' },
        'cancelled': { color: '#991b1b', bg: '#fee2e2' }
    };
    const style = statusColors[data.status] || { color: '#374151', bg: '#f1f5f9' };
    statusEl.style.color = style.color;
    statusEl.style.backgroundColor = style.bg;

    // Menu items
    const menuSource = document.getElementById(`booking-items-${data.id}`);
    const menuTarget = document.getElementById('modalMenuItems');
    const menuSection = document.getElementById('modalMenuSection');

    if (menuSource) {
        menuTarget.innerHTML = menuSource.innerHTML;
        if (menuSection) menuSection.style.display = 'block';
    } else {
        menuTarget.innerHTML = '<p style="color: #64748b; font-size: 0.9rem;">No menu items selected.</p>';
    }

    // Actions
    const actionsEl = document.getElementById('modalActions');
    actionsEl.innerHTML = '';

    // Always show View Contract if it exists
    if (data.hasContract === 'true') {
        const viewLink = document.createElement('a');
        viewLink.href = `/caterer/bookings/${data.id}/contract`;
        viewLink.className = 'btn-action-modal btn-status-confirm';
        viewLink.style.textDecoration = 'none';
        viewLink.style.textAlign = 'center';
        viewLink.style.lineHeight = '1.2';
        viewLink.style.display = 'flex';
        viewLink.style.alignItems = 'center';
        viewLink.style.justifyContent = 'center';
        viewLink.style.background = '#1e293b';
        viewLink.innerText = 'View Contract';
        actionsEl.appendChild(viewLink);
    }

    if (data.status === 'pending') {
        actionsEl.innerHTML += `
            <form action="/caterer/bookings/${data.id}/accept" method="POST" style="flex: 1; display: flex;">
                <button type="submit" class="btn-action-modal btn-status-confirm">Accept</button>
            </form>
            <button onclick="promptCancel('${data.id}')" class="btn-action-modal btn-status-reject">Reject</button>
        `;
    } else if (data.status === 'confirmed') {
        actionsEl.innerHTML += `
            <form action="/caterer/bookings/${data.id}/complete" method="POST" style="flex: 1; display: flex;">
                <button type="submit" class="btn-action-modal btn-status-complete">Mark as Completed</button>
            </form>
            <button onclick="promptCancel('${data.id}')" class="btn-action-modal btn-status-cancel">Cancel Booking</button>
        `;
    }

    // Payment info
    document.getElementById('modalBookedOn').innerText = data.bookedOn;
    document.getElementById('modalPaymentMethod').innerText = `Method: ${data.paymentMethod}`;
    document.getElementById('modalTotalAmount').innerText = data.amount;
    document.getElementById('modalGuestCount').innerText = `${data.guestCount} Guests`;

    const pStatusEl = document.getElementById('modalPaymentStatus');
    pStatusEl.innerText = data.paymentStatus;
    pStatusEl.style.color = data.paymentStatus === 'paid' ? '#166534' : '#92400e';

    // History
    const historySource = document.getElementById(`booking-history-${data.id}`);
    const historyTarget = document.getElementById('modalHistory');
    if (historySource && historySource.innerHTML.trim() !== '') {
        historyTarget.innerHTML = historySource.innerHTML;
    } else {
        historyTarget.innerHTML = '<p style="color: #64748b; font-size: 0.85rem;">No history available yet.</p>';
    }

    modal.style.display = 'flex';
}

function promptCancel(bookingId) {
    const reason = prompt("Enter reason for cancellation:");
    if (reason) {
        const form = document.createElement('form');
        form.method = 'POST';
        form.action = `/caterer/bookings/${bookingId}/cancel`;

        const reasonInput = document.createElement('input');
        reasonInput.type = 'hidden';
        reasonInput.name = 'reason';
        reasonInput.value = reason;

        form.appendChild(reasonInput);
        document.body.appendChild(form);
        form.submit();
    }
}

function showMenuDetails(bookingId) {
    const btn = document.querySelector(`.view-details[data-id="${bookingId}"]`);
    if (btn) showBookingDetails(btn);
}

function closeModal() {
    const modal = document.getElementById('bookingDetailModal');
    if (modal) modal.style.display = 'none';
}

// Global exposure
window.promptCancel = promptCancel;
window.showMenuDetails = showMenuDetails;
window.closeModal = closeModal;

// Close when clicking outside
window.onclick = function (event) {
    const modal = document.getElementById('bookingDetailModal');
    if (event.target == modal) {
        closeModal();
    }
}
