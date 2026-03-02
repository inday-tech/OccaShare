document.addEventListener('DOMContentLoaded', function () {
    const UNIT_PRICE = parseFloat(window.unitPrice || 0);
    const BOOKING_ID = window.bookingId;
    const ADDON_TOTAL = parseFloat(window.addonTotal || 0);
    let isCalculating = false;

    function formatMoney(num) {
        return '₱' + num.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });
    }

    window.adjustPax = function (delta) {
        const input = document.getElementById('pax-input');
        if (!input) return;
        const min = parseInt(input.min) || 10;
        const max = parseInt(input.max) || 99999;
        let val = (parseInt(input.value) || min) + delta;
        input.value = Math.min(max, Math.max(min, val));
        recalculate();
    };

    window.setDPTier = function (val) {
        const dpInput = document.getElementById('dp-percent-input');
        if (dpInput) dpInput.value = val;
        document.querySelectorAll('.dp-tier-btn').forEach(btn => {
            const isActive = btn.querySelector('.dpt-percent').innerText === val + '%';
            btn.classList.toggle('active', isActive);
        });
        recalculate();
    };

    window.recalculate = function () {
        if (isCalculating) return;
        const input = document.getElementById('pax-input');
        const dpInput = document.getElementById('dp-percent-input');
        if (!input || !dpInput) return;

        const pax = parseInt(input.value) || 0;
        const dpPercent = parseInt(dpInput.value);
        if (pax < 1) return;

        isCalculating = true;

        try {
            const baseAmount = UNIT_PRICE * pax;
            const totalAmount = baseAmount + ADDON_TOTAL;
            const depositAmount = totalAmount * (dpPercent / 100);

            // Invoice row
            const baseDisplay = document.getElementById('base-total-display');
            if (baseDisplay) baseDisplay.innerText = formatMoney(baseAmount);

            const baseSubtotal = document.getElementById('base-subtotal-val');
            if (baseSubtotal) baseSubtotal.innerText = formatMoney(baseAmount);

            // Grand Total
            const totalVal = document.getElementById('total-val');
            if (totalVal) totalVal.innerText = formatMoney(totalAmount);

            // Banner
            const bannerPax = document.getElementById('banner-pax-display');
            if (bannerPax) bannerPax.innerText = pax + ' pax';
            const bannerTotal = document.getElementById('banner-total-display');
            if (bannerTotal) bannerTotal.innerText = formatMoney(baseAmount);

            // Deposit card
            const depositVal = document.getElementById('deposit-val');
            if (depositVal) depositVal.innerText = formatMoney(depositAmount);
            const calcLabel = document.getElementById('dc-calc-label');
            if (calcLabel) calcLabel.innerText = formatMoney(totalAmount) + ' × ' + dpPercent + '%';

            // Contract text
            document.querySelectorAll('.contract-total-text').forEach(el => el.innerText = formatMoney(totalAmount));
            document.querySelectorAll('.contract-deposit-text').forEach(el => el.innerText = formatMoney(depositAmount));
            document.querySelectorAll('.contract-dp-percent').forEach(el => el.innerText = dpPercent);

            // Pop animation
            const card = document.getElementById('deposit-card');
            if (card) {
                card.classList.remove('updated');
                void card.offsetWidth;
                card.classList.add('updated');
                setTimeout(() => card.classList.remove('updated'), 400);
            }
        } catch (err) {
            console.error('Calculation error:', err);
        } finally {
            isCalculating = false;
        }
    };

    window.toggleSignButton = function () {
        const nameInput = document.getElementById('signature_name');
        const agreeInput = document.getElementById('agree_terms');
        const btnSign = document.getElementById('btn-sign');
        if (!nameInput || !agreeInput || !btnSign) return;

        const name = nameInput.value.trim();
        const agree = agreeInput.checked;
        btnSign.disabled = !(name.length >= 5 && agree);
    };

    window.submitSignature = async function () {
        const signature = document.getElementById('signature_name').value.trim();
        const paxCount = document.getElementById('pax-input').value;
        const dpPercent = document.getElementById('dp-percent-input').value;

        const formData = new FormData();
        formData.append('signature_data', signature);
        formData.append('guest_count', paxCount);
        formData.append('downpayment_percent', dpPercent);

        const btn = document.getElementById('btn-sign');
        btn.disabled = true;
        btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> <span>Processing…</span>';

        try {
            const res = await fetch(`/api/bookings/${BOOKING_ID}/contract/sign`, {
                method: 'POST',
                body: formData,
                credentials: 'same-origin'
            });
            const data = await res.json();
            if (data.success) {
                window.location.href = `/bookings/step/payment/${BOOKING_ID}`;
            } else {
                alert('Error: ' + (data.detail || 'Could not sign contract.'));
                btn.disabled = false;
                btn.innerHTML = '<i class="fas fa-check-circle"></i> <span>Confirm &amp; Proceed to Payment</span>';
            }
        } catch (err) {
            alert('Network error: ' + err);
            btn.disabled = false;
            btn.innerHTML = '<i class="fas fa-check-circle"></i> <span>Confirm &amp; Proceed to Payment</span>';
        }
    };

    // Initial sync
    recalculate();
});
