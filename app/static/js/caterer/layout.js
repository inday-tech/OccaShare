(function () {
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
