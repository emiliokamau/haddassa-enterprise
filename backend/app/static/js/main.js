document.addEventListener("DOMContentLoaded", () => {
    const yearElement = document.getElementById("year");
    if (yearElement) {
        yearElement.textContent = new Date().getFullYear();
    }

    const themeToggle = document.getElementById("theme-toggle");
    const themeLabel = themeToggle ? themeToggle.querySelector(".theme-toggle-label") : null;
    const storageKey = "hadassah-theme";

    const applyTheme = (theme) => {
        document.body.setAttribute("data-theme", theme);
        if (themeLabel) {
            themeLabel.textContent = theme === "dark" ? "Light" : "Dark";
        }
    };

    const savedTheme = window.localStorage.getItem(storageKey);
    const prefersDark = window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches;
    const initialTheme = savedTheme || (prefersDark ? "dark" : "light");
    applyTheme(initialTheme);

    if (themeToggle) {
        themeToggle.addEventListener("click", () => {
            const current = document.body.getAttribute("data-theme") || "light";
            const next = current === "dark" ? "light" : "dark";
            applyTheme(next);
            window.localStorage.setItem(storageKey, next);
        });
    }
});
