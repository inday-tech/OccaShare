/**
 * Admin Layout Functionality
 * Handles sidebar interactions and inactivity auto-logout
 */
(function () {
    // Inactivity Auto-Logout Logic
    let timeoutLength = 30 * 60 * 1000; // 30 minutes for Admin
    let warningLength = 29 * 60 * 1000; // 29 minutes
    let inactivityTimeout;
    let warningTimeout;

    const modal = document.getElementById('inactivityModal');
    const stayBtn = document.getElementById('stayLoggedInBtn');

    function resetTimer() {
        // If modal is open, don't reset timer from background clicks
        if (modal && modal.style.display === 'flex') return;

        clearTimeout(inactivityTimeout);
        clearTimeout(warningTimeout);

        warningTimeout = setTimeout(function () {
            if (modal) modal.style.display = 'flex';
        }, warningLength);

        inactivityTimeout = setTimeout(function () {
            window.location.href = "/auth/logout?reason=inactivity";
        }, timeoutLength);
    }

    // Close modal and reset
    if (stayBtn) {
        stayBtn.addEventListener('click', function () {
            if (modal) modal.style.display = 'none';
            resetTimer();
        });
    }

    // Listen for activities
    window.addEventListener('load', resetTimer);
    document.addEventListener('mousemove', resetTimer);
    document.addEventListener('keypress', resetTimer);
    document.addEventListener('touchstart', resetTimer);
    document.addEventListener('click', resetTimer);
    document.addEventListener('scroll', resetTimer);

    // Sidebar Toggle (if needed for mobile)
    const sidebar = document.querySelector('.sidebar');
    // Add mobile toggle logic here if required
})();
