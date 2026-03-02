(function () {
    /* ============================================================
       NAV ACTIVE-LINK HIGHLIGHTING
       Strategy:
         - On the home page (data-nav-page="home"): use IntersectionObserver
           to watch sections and highlight matching nav links.
         - On every other page: match body[data-nav-page] to nav links
           with matching [data-nav] attribute.
         - On login page ("login"): highlight #navLoginBtn with active-page class.
         - On register page ("register"): highlight #navSignupBtn with active-page class.
    ============================================================ */

    const NAV_PAGE = document.body.dataset.navPage || '';
    const navLinks = document.querySelectorAll('.nav-links a');
    const loginBtn = document.getElementById('navLoginBtn');
    const signupBtn = document.getElementById('navSignupBtn');

    function clearActive() {
        navLinks.forEach(a => a.classList.remove('active'));
        if (loginBtn) loginBtn.classList.remove('active-page');
        if (signupBtn) signupBtn.classList.remove('active-page');
    }

    function setActive(navValue) {
        clearActive();
        navLinks.forEach(a => {
            if (a.dataset.nav === navValue) a.classList.add('active');
        });
    }

    /* ---- HOME PAGE: IntersectionObserver ---- */
    if (NAV_PAGE === 'home' || NAV_PAGE === '') {
        const sections = document.querySelectorAll('section[id], header[id]');
        if (sections.length > 0) {
            const observer = new IntersectionObserver((entries) => {
                entries.forEach(entry => {
                    if (entry.isIntersecting) {
                        const id = entry.target.id;
                        // Map section IDs to data-nav values
                        const map = {
                            'home': 'home',
                            'caterers': 'caterers',
                            'how-it-works': 'how-it-works',
                            'categories': 'categories',
                            'testimonials': 'home',
                        };
                        const navVal = map[id] || 'home';
                        setActive(navVal);
                    }
                });
            }, { threshold: 0.35 });

            sections.forEach(sec => observer.observe(sec));
        }
        // Default: highlight Home
        setActive('home');
    }

    /* ---- AUTH BUTTON HIGHLIGHT: Login page ---- */
    else if (NAV_PAGE === 'login') {
        clearActive();
        if (loginBtn) loginBtn.classList.add('active-page');
    }

    /* ---- AUTH BUTTON HIGHLIGHT: Register page ---- */
    else if (NAV_PAGE === 'register') {
        clearActive();
        if (signupBtn) signupBtn.classList.add('active-page');
    }

    /* ---- ALL OTHER PAGES: match data-nav attribute ---- */
    else {
        setActive(NAV_PAGE);
    }

    /* ---- MOBILE HAMBURGER ---- */
    const hamburger = document.querySelector('.hamburger');
    const navMenu = document.querySelector('.nav-menu');
    if (hamburger && navMenu) {
        hamburger.addEventListener('click', () => {
            hamburger.classList.toggle('active');
            navMenu.classList.toggle('active');
        });
        document.querySelectorAll('.nav-links a').forEach(link => {
            link.addEventListener('click', () => {
                hamburger.classList.remove('active');
                navMenu.classList.remove('active');
            });
        });
    }

    /* ---- NAVBAR SCROLL SHRINK ---- */
    const navbar = document.getElementById('mainNavbar');
    if (navbar) {
        window.addEventListener('scroll', () => {
            navbar.style.boxShadow = window.scrollY > 40
                ? '0 2px 20px rgba(0,0,0,0.12)'
                : '';
        }, { passive: true });
    }
})();
