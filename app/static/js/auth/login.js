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

        // Redirect immediately
        // Open a centered popup window
        const width = 600;
        const height = 700;
        const left = (window.screen.width / 2) - (width / 2);
        const top = (window.screen.height / 2) - (height / 2);

        window.open(
            `/auth/login/${provider}`,
            'SocialLoginPopup',
            `width=${width},height=${height},top=${top},left=${left},scrollbars=yes,resizable=yes`
        );

        // Optional: show a small message while the popup is open
        Swal.fire({
            title: 'Connecting...',
            text: 'Please complete the login in the popup window.',
            allowOutsideClick: false,
            showConfirmButton: false,
            willOpen: () => {
                Swal.showLoading();
            }
        });

        // The popup will either close itself and redirect the parent (handled in social_auth.py)
        // Or the user will close it manually (handled by an interval check if needed)
        const checkPopup = setInterval(() => {
            if (!window.SocialLoginPopup || window.SocialLoginPopup.closed) {
                clearInterval(checkPopup);
                isLoggingIn = false;
                if (btn) {
                    const originalBtn = document.querySelector(`.btn-${provider}`);
                    if (originalBtn) {
                        originalBtn.innerHTML = `Continue with ${provider.charAt(0).toUpperCase() + provider.slice(1)}`; // Simplified restore
                        originalBtn.style.opacity = '1';
                        originalBtn.style.cursor = 'pointer';
                    }
                }
            }
        }, 1000);
    }
})();
