document.addEventListener('DOMContentLoaded', function () {
    const pricePerHead = Number(window.pricePerHead || 0);
    const catererId = Number(window.catererId || 0);

    window.updateCalculator = function () {
        const guestInput = document.getElementById('guest_count');
        const calcGuests = document.getElementById('calc-guests');
        const calcTotal = document.getElementById('calc-grand-total');
        const totalPriceInput = document.getElementById('total_price_input');
        const reservationFeeInput = document.getElementById('reservation_fee_input');

        if (!guestInput || !calcGuests || !calcTotal) return;

        const guests = parseInt(guestInput.value) || 0;
        calcGuests.innerText = guests;

        const total = guests * pricePerHead;
        calcTotal.innerText = '₱' + total.toLocaleString(undefined, { minimumFractionDigits: 2 });

        if (totalPriceInput) totalPriceInput.value = total;
        if (reservationFeeInput) reservationFeeInput.value = total * 0.3; // Default 30% for estimate
    };

    window.checkAvailability = async function () {
        const dateInput = document.getElementById('event_date');
        const chip = document.getElementById('availability-chip');
        const submitBtn = document.getElementById('submitBtn');

        if (!dateInput || !dateInput.value) return;

        const date = dateInput.value;
        chip.style.display = 'inline-flex';
        chip.style.background = '#f1f5f9';
        chip.style.color = '#64748b';
        chip.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Checking...';

        try {
            const response = await fetch(`/packages/api/check-availability?caterer_id=${catererId}&date_str=${date}`);
            const data = await response.json();

            if (data.available) {
                chip.style.background = '#dcfce7';
                chip.style.color = '#166534';
                chip.innerHTML = '<i class="fas fa-check-circle"></i> Date Available';
                if (submitBtn) {
                    submitBtn.disabled = false;
                    submitBtn.style.opacity = '1';
                }
            } else {
                chip.style.background = '#fee2e2';
                chip.style.color = '#991b1b';
                chip.innerHTML = '<i class="fas fa-times-circle"></i> Fully Booked';
                if (submitBtn) {
                    submitBtn.disabled = true;
                    submitBtn.style.opacity = '0.5';
                }
            }
        } catch (error) {
            chip.innerHTML = 'Error checking date';
        }
    };

    // Initial run
    updateCalculator();
});
