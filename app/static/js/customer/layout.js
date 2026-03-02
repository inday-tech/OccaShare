(function () {
    // Real-time WebSocket Client
    const clientId = "client_" + Math.random().toString(36).substr(2, 9);
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const ws = new WebSocket(`${protocol}//${window.location.host}/ws/${clientId}`);

    ws.onmessage = function (event) {
        const data = JSON.parse(event.data);
        if (data.type === 'new_package') {
            showToast(data);
        }
    };

    function showToast(data) {
        const container = document.getElementById('toast-container');
        const toast = document.createElement('div');
        toast.className = 'toast-notification';
        toast.innerHTML = `
            <div class="toast-icon">
                <i class="fas fa-utensils"></i>
            </div>
            <div style="flex: 1;">
                <div style="font-weight: 700; margin-bottom: 0.25rem;">New Package Added!</div>
                <div style="font-size: 0.85rem; color: #64748b; margin-bottom: 0.5rem;">
                    <strong>${data.caterer_name}</strong> just added <em>"${data.package_name}"</em>
                </div>
                <a href="/caterers/${data.caterer_id}" style="color: var(--primary-color); font-weight: 600; font-size: 0.8rem; text-decoration: none;">
                    View Package <i class="fas fa-arrow-right" style="font-size: 0.7rem; margin-left: 0.25rem;"></i>
                </a>
            </div>
            <button onclick="this.parentElement.remove()" style="background: none; border: none; color: #cbd5e1; cursor: pointer;">
                <i class="fas fa-times"></i>
            </button>
        `;
        container.appendChild(toast);

        // Auto-dismiss after 8 seconds
        setTimeout(() => {
            toast.classList.add('fade-out');
            setTimeout(() => toast.remove(), 500);
        }, 8000);
    }

    let timeoutLength = 15 * 60 * 1000; // 15 minutes
    let warningLength = 14 * 60 * 1000; // 14 minutes
    let inactivityTimeout;
    let warningTimeout;
    const modal = document.getElementById('inactivityModal');
    const stayBtn = document.getElementById('stayLoggedInBtn');

    function resetTimer() {
        // If modal is open, don't reset timer from background clicks
        if (modal.style.display === 'flex') return;

        clearTimeout(inactivityTimeout);
        clearTimeout(warningTimeout);

        warningTimeout = setTimeout(function () {
            modal.style.display = 'flex';
        }, warningLength);

        inactivityTimeout = setTimeout(function () {
            window.location.href = "/auth/logout?reason=inactivity";
        }, timeoutLength);
    }

    // Close modal and reset
    if (stayBtn) {
        stayBtn.addEventListener('click', function () {
            modal.style.display = 'none';
            resetTimer();
        });
    }

    // Listen for activities
    window.onload = resetTimer;
    document.onmousemove = resetTimer;
    document.onkeypress = resetTimer;
    document.ontouchstart = resetTimer; // for mobile
    document.onclick = resetTimer;
    document.onscroll = resetTimer;
})();
