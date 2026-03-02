document.addEventListener('DOMContentLoaded', function () {
    const calendarEl = document.getElementById('calendar');
    if (calendarEl) {
        const calendar = new FullCalendar.Calendar(calendarEl, {
            initialView: 'dayGridMonth',
            headerToolbar: {
                left: 'prev,next today',
                center: 'title',
                right: 'dayGridMonth,timeGridWeek'
            },
            events: '/caterer/api/events',
            eventClick: function (info) {
                showEventDetails(info.event);
            },
            height: 'auto',
            dayMaxEvents: true
        });
        calendar.render();
    }
});

function showEventDetails(event) {
    const props = event.extendedProps;
    const modalTitle = document.getElementById('modalTitle');
    if (modalTitle) modalTitle.textContent = event.title || 'Event Details';

    document.getElementById('currentBookingId').value = event.id;
    document.getElementById('detCustomer').textContent = props.customer || '---';
    document.getElementById('detType').textContent = props.type || '---';
    document.getElementById('detDateTime').textContent = event.start.toLocaleDateString('en-US', {
        weekday: 'long',
        year: 'numeric',
        month: 'long',
        day: 'numeric'
    }) + ' at ' + (props.time || 'TBD');
    document.getElementById('detVenue').textContent = props.venue || '---';
    document.getElementById('detPackage').textContent = (props.guests || '0') + ' Guests - ' + (props.package || '---');

    document.getElementById('eventModal').style.display = 'flex';
}

async function setReminder() {
    const bookingId = document.getElementById('currentBookingId').value;
    const btn = document.querySelector('#eventModal .btn-primary');
    if (!btn) return;

    const originalText = btn.textContent;

    btn.disabled = true;
    btn.textContent = 'Setting...';

    try {
        const response = await fetch(`/caterer/api/bookings/${bookingId}/reminders`, {
            method: 'POST'
        });
        const data = await response.json();

        if (data.status === 'success') {
            alert('Reminder set! You will see it in your notifications.');
            closeModal();
            location.reload(); // To update notification count
        } else {
            alert(data.message || 'Failed to set reminder.');
        }
    } catch (error) {
        console.error('Error:', error);
        alert('Failed to set reminder.');
    } finally {
        btn.disabled = false;
        btn.textContent = originalText;
    }
}

function closeModal() {
    const modal = document.getElementById('eventModal');
    if (modal) modal.style.display = 'none';
}

async function toggleDateAvailability(isAvailable) {
    const dateInput = document.getElementById('blockDate');
    const reasonInput = document.getElementById('blockReason');

    if (!dateInput) return;

    const date = dateInput.value;
    const reason = reasonInput ? reasonInput.value : '';

    if (!date) {
        alert('Please select a date first.');
        return;
    }

    try {
        const response = await fetch('/caterer/api/availability/toggle', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ date, is_available: isAvailable, reason })
        });

        if (response.ok) {
            location.reload();
        } else {
            alert('Failed to update availability.');
        }
    } catch (error) {
        console.error('Error:', error);
        alert('An error occurred.');
    }
}

// Close on escape
document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') closeModal();
});

// Global exposure
window.showEventDetails = showEventDetails;
window.setReminder = setReminder;
window.closeModal = closeModal;
window.toggleDateAvailability = toggleDateAvailability;
