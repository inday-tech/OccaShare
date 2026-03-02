function selectPaymentMethod(method, element) {
    // Update hidden input
    document.getElementById('selected-method').value = method;

    // Update UI
    document.querySelectorAll('.method-card').forEach(card => {
        card.classList.remove('active');
    });
    element.classList.add('active');

    // Update button text and icon
    const btn = document.querySelector('.btn-complete');
    if (btn) {
        const span = btn.querySelector('span') || btn;
        const icon = btn.querySelector('i');

        if (method === 'Cash') {
            if (span.tagName === 'SPAN') span.innerText = 'Complete Booking (Cash)';
            else btn.innerHTML = 'Complete Booking (Cash) <i class="fas fa-check"></i>';
            if (icon) icon.className = 'fas fa-check';
        } else {
            if (span.tagName === 'SPAN') span.innerText = 'Proceed to Secure Checkout';
            else btn.innerHTML = 'Proceed to Secure Checkout <i class="fas fa-lock"></i>';
            if (icon) icon.className = 'fas fa-lock';
        }
    }
}

document.addEventListener('DOMContentLoaded', function () {
    const form = document.querySelector('form');
    const actions = document.getElementById('wizard-actions');
    const processing = document.getElementById('payment-processing');

    if (form && actions && processing) {
        form.onsubmit = function () {
            actions.style.display = 'none';
            processing.style.display = 'block';
            return true;
        };
    }
});
