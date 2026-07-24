/**
 * Events and Alerts Module
 * Small shared UI helpers actually used across the app: the profile page's
 * show/hide password toggle, and the mobile nav hamburger menu.
 */

// Toggle password visibility
function togglePasswordVisibility(passwordInputId, toggleButtonId) {
    const passwordInput = document.getElementById(passwordInputId);
    const toggleButton = document.getElementById(toggleButtonId);

    if (passwordInput && toggleButton) {
        toggleButton.addEventListener('click', function() {
            const type = passwordInput.getAttribute('type') === 'password' ? 'text' : 'password';
            passwordInput.setAttribute('type', type);
            this.textContent = type === 'password' ? 'Show' : 'Hide';
            this.setAttribute('aria-label', type === 'password' ? 'Show password' : 'Hide password');
        });
        return true;
    }
    return false;
}

document.addEventListener('DOMContentLoaded', function() {
    document.querySelectorAll('.nav-toggle').forEach(function(toggle) {
        const menuId = toggle.getAttribute('aria-controls');
        const menu = menuId ? document.getElementById(menuId) : null;
        if (!menu) {
            return;
        }

        toggle.addEventListener('click', function() {
            const isOpen = toggle.getAttribute('aria-expanded') === 'true';
            toggle.setAttribute('aria-expanded', String(!isOpen));
            menu.classList.toggle('is-open', !isOpen);
            document.body.classList.toggle('nav-open', !isOpen);
        });

        menu.querySelectorAll('a').forEach(function(link) {
            link.addEventListener('click', function() {
                toggle.setAttribute('aria-expanded', 'false');
                menu.classList.remove('is-open');
                document.body.classList.remove('nav-open');
            });
        });
    });
});
