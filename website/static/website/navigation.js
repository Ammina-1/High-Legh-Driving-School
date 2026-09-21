(() => {
    const menu = document.getElementById('mobile-menu');
    if (!menu) return;
    const toggle = menu.querySelector('summary');
    const panel = menu.querySelector('nav');
    const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)');
    const desktop = window.matchMedia('(min-width: 64rem)');
    let animation;
    let expanded = menu.open;

    function setOpen(open, restoreFocus = false, immediate = false) {
        expanded = open;
        animation?.cancel();
        toggle.setAttribute('aria-expanded', String(open));
        toggle.setAttribute('aria-label', open ? 'Close navigation' : 'Open navigation');
        if (restoreFocus) toggle.focus();
        panel.inert = !open;
        if (open) menu.open = true;
        if (immediate || reducedMotion.matches || !panel.animate) {
            menu.open = open;
            return;
        }
        animation = panel.animate([
            { opacity: open ? 0 : 1, transform: open ? 'translateY(-8px)' : 'translateY(0)' },
            { opacity: open ? 1 : 0, transform: open ? 'translateY(0)' : 'translateY(-8px)' }
        ], { duration: 180, easing: 'ease-out' });
        animation.onfinish = () => { menu.open = open; };
    }
    toggle.addEventListener('click', event => {
        event.preventDefault();
        setOpen(!expanded);
    });
    panel.querySelectorAll('a').forEach(link => {
        link.addEventListener('click', () => {
            setOpen(false, true);
            if (link.pathname === location.pathname && link.hash) {
                const target = document.getElementById(link.hash.slice(1));
                if (target) {
                    target.setAttribute('tabindex', '-1');
                    target.focus({ preventScroll: true });
                }
            }
        });
    });
    document.addEventListener('keydown', event => {
        if (event.key === 'Escape' && expanded) {
            event.preventDefault();
            setOpen(false, true);
        }
    });
    document.addEventListener('click', event => {
        if (expanded && !menu.contains(event.target)) setOpen(false);
    });
    document.addEventListener('focusin', event => {
        if (expanded && !menu.contains(event.target)) setOpen(false);
    });
    desktop.addEventListener('change', () => {
        if (desktop.matches) setOpen(false, false, true);
    });
    setOpen(false, false, true);

    // Contact is a section of Home; highlight it when its anchor is active.
    const navLinks = [...document.querySelectorAll('header nav a')];
    const pageLinks = navLinks.filter(link => link.getAttribute('aria-current') === 'page');
    function updateActiveLink() {
        navLinks.forEach(link => link.removeAttribute('aria-current'));
        const contact = document.getElementById('contact') && location.hash === '#contact';
        (contact ? navLinks.filter(link => link.hash === '#contact') : pageLinks)
            .forEach(link => link.setAttribute('aria-current', contact ? 'location' : 'page'));
    }
    window.addEventListener('hashchange', updateActiveLink);
    updateActiveLink();
})();
