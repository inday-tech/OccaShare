(function () {
    window.updateUI = function (role) {
        const welcomeText = document.getElementById('welcomeText');
        const roleLabel = document.getElementById('roleLabel');
        const roleToggleLink = document.getElementById('roleToggleLink');
        const roleInput = document.getElementById('roleInput');

        if (role === 'caterer') {
            welcomeText.innerText = 'Partner with OccaServe and grow your catering business';
            roleLabel.innerText = 'Regular customer?';
            roleToggleLink.innerText = 'Switch to Customer';
            roleInput.value = 'caterer';
        } else {
            welcomeText.innerText = 'Start your extraordinary event journey today';
            roleLabel.innerText = 'Business owner?';
            roleToggleLink.innerText = 'Switch to Caterer';
            roleInput.value = 'customer';
        }
    };

    window.switchRole = function () {
        const currentRole = document.getElementById('roleInput').value;
        if (currentRole === 'customer') {
            window.location.href = "/auth/register/caterer";
        } else {
            window.updateUI('customer');
        }
    };

    window.onload = function () {
        const urlParams = new URLSearchParams(window.location.search);
        const role = urlParams.get('role');
        if (role) window.updateUI(role);
    };

    const mobileInput = document.getElementById('mobile_number');
    if (mobileInput) {
        mobileInput.oninput = function () {
            const mobileRegex = /^(09|\+639)\d{9}$/;
            const val = this.value.replace(/\s/g, '');
            const error = document.getElementById('mobileError');
            if (val && !mobileRegex.test(val)) {
                this.classList.add('input-error');
                if (error) error.style.display = 'block';
            } else {
                this.classList.remove('input-error');
                if (error) error.style.display = 'none';
            }
        };
    }

    const validatePasswords = () => {
        const pass = document.getElementById('password');
        const confirm = document.getElementById('confirm_password');
        const passError = document.getElementById('passwordError');
        const confirmError = document.getElementById('confirmError');

        if (pass && pass.value && pass.value.length < 8) {
            pass.classList.add('input-error');
            if (passError) passError.style.display = 'block';
        } else if (pass) {
            pass.classList.remove('input-error');
            if (passError) passError.style.display = 'none';
        }

        if (confirm && pass && confirm.value && pass.value !== confirm.value) {
            confirm.classList.add('input-error');
            if (confirmError) confirmError.style.display = 'block';
        } else if (confirm) {
            confirm.classList.remove('input-error');
            if (confirmError) confirmError.style.display = 'none';
        }
    };

    const passInput = document.getElementById('password');
    const confirmInput = document.getElementById('confirm_password');
    if (passInput) passInput.oninput = validatePasswords;
    if (confirmInput) confirmInput.oninput = validatePasswords;

    const regForm = document.getElementById('regForm');
    if (regForm) {
        regForm.onsubmit = function (e) {
            const passEl = document.getElementById('password');
            const confirmEl = document.getElementById('confirm_password');
            const mobileEl = document.getElementById('mobile_number');

            const pass = passEl ? passEl.value : "social_login_auto";
            const confirm = confirmEl ? confirmEl.value : "social_login_auto";
            const mobile = mobileEl ? mobileEl.value.replace(/\s/g, '') : "";

            const mobileRegex = /^(09|\+639)\d{9}$/;
            let hasError = false;

            if (pass !== "social_login_auto" && pass.length < 8) {
                alert("Password must be at least 8 characters long.");
                hasError = true;
            } else if (pass !== "social_login_auto" && pass !== confirm) {
                alert("Credentials do not match. Please verify your security sequence.");
                hasError = true;
            } else if (mobile && !mobileRegex.test(mobile)) {
                alert("Please enter a valid Philippine mobile number.");
                hasError = true;
            }

            if (hasError) {
                e.preventDefault();
                return false;
            }
            return true;
        };
    }
})();
