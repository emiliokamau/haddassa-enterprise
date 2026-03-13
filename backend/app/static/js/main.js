document.addEventListener("DOMContentLoaded", () => {
    const yearElement = document.getElementById("year");
    if (yearElement) {
        yearElement.textContent = new Date().getFullYear();
    }

    const themeToggles = [
        document.getElementById("theme-toggle"),
        document.getElementById("theme-toggle-mobile"),
    ].filter(Boolean);

    const mobileNavToggle = document.getElementById("mobile-nav-toggle");
    const mobileNavClose = document.getElementById("mobile-nav-close");
    const mobileDrawer = document.getElementById("mobile-drawer");
    const mobileOverlay = document.getElementById("mobile-nav-overlay");

    const storageKey = "hadassah-theme";

    const applyTheme = (theme) => {
        document.body.setAttribute("data-theme", theme);
        const nextLabel = theme === "dark" ? "Light" : "Dark";
        themeToggles.forEach((toggle) => {
            const label = toggle.querySelector(".theme-toggle-label");
            if (label) {
                label.textContent = nextLabel;
            }
        });
    };

    const setMobileDrawerState = (open) => {
        if (!mobileDrawer || !mobileOverlay || !mobileNavToggle) {
            return;
        }
        mobileDrawer.dataset.open = open ? "true" : "false";
        mobileDrawer.setAttribute("aria-hidden", open ? "false" : "true");
        mobileOverlay.hidden = !open;
        mobileNavToggle.setAttribute("aria-expanded", open ? "true" : "false");
        document.body.classList.toggle("no-scroll", open);
    };

    const savedTheme = window.localStorage.getItem(storageKey);
    const prefersDark = window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches;
    const initialTheme = savedTheme || (prefersDark ? "dark" : "light");
    applyTheme(initialTheme);

    themeToggles.forEach((toggle) => {
        toggle.addEventListener("click", () => {
            const current = document.body.getAttribute("data-theme") || "light";
            const next = current === "dark" ? "light" : "dark";
            applyTheme(next);
            window.localStorage.setItem(storageKey, next);
        });
    });

    if (mobileNavToggle && mobileDrawer && mobileOverlay) {
        mobileNavToggle.addEventListener("click", () => setMobileDrawerState(true));
        if (mobileNavClose) {
            mobileNavClose.addEventListener("click", () => setMobileDrawerState(false));
        }
        mobileOverlay.addEventListener("click", () => setMobileDrawerState(false));
        document.addEventListener("keydown", (event) => {
            if (event.key === "Escape") {
                setMobileDrawerState(false);
            }
        });

        const drawerLinks = mobileDrawer.querySelectorAll("a");
        drawerLinks.forEach((link) => {
            link.addEventListener("click", () => setMobileDrawerState(false));
        });
    }
});
