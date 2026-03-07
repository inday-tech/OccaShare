(function () {
    const urlParams = new URLSearchParams(window.location.search);

    if (urlParams.get('verified') === 'true') {
        Swal.fire({ icon: 'success', title: 'Email successfully verified!', text: 'You can now log in to your account.', confirmButtonColor: '#99cc66' });
    }

    if (urlParams.get('success') === 'password_reset') {
        Swal.fire({ icon: 'success', title: 'Password Updated!', text: 'Your password has been reset successfully. Please log in with your new password.', confirmButtonColor: '#99cc66' });
    }

    let isLoggingIn = false;
    window.handleSocialLogin = function (provider) {
        if (isLoggingIn) return;
        isLoggingIn = true;

        const btn = document.querySelector(`.btn-${provider}`);
        if (btn) {
            btn.style.opacity = '0.7';
            btn.style.cursor = 'wait';
            const originalContent = btn.innerHTML;
            btn.innerHTML = `<i class="fas fa-spinner fa-spin"></i> Processing...`;
        }

        // Redirect immediately in the same tab
        window.location.href = `/auth/login/${provider}`;
    }
})();
