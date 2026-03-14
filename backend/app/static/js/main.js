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
    const uploadArea = document.getElementById("upload-area");
    const fileInput = document.getElementById("document-input");

    if (uploadArea && fileInput) {
        const setSelectedFilename = (name) => {
            let nameNode = uploadArea.querySelector(".upload-filename");
            if (!nameNode) {
                nameNode = document.createElement("p");
                nameNode.className = "upload-filename";
                uploadArea.appendChild(nameNode);
            }
            nameNode.textContent = name;
        };

        uploadArea.addEventListener("click", (event) => {
            if (event.target !== fileInput) {
                fileInput.click();
            }
        });

        fileInput.addEventListener("change", () => {
            if (fileInput.files && fileInput.files.length > 0) {
                setSelectedFilename(fileInput.files[0].name);
            }
        });

        ["dragenter", "dragover"].forEach((eventName) => {
            uploadArea.addEventListener(eventName, (event) => {
                event.preventDefault();
                event.stopPropagation();
                uploadArea.classList.add("drag-over");
            });
        });

        ["dragleave", "dragend"].forEach((eventName) => {
            uploadArea.addEventListener(eventName, (event) => {
                event.preventDefault();
                event.stopPropagation();
                uploadArea.classList.remove("drag-over");
            });
        });

        uploadArea.addEventListener("drop", (event) => {
            event.preventDefault();
            event.stopPropagation();
            uploadArea.classList.remove("drag-over");

            const files = event.dataTransfer && event.dataTransfer.files;
            if (!files || files.length === 0) {
                return;
            }

            // Keep one-file upload behavior aligned with backend validation.
            try {
                const transfer = new DataTransfer();
                transfer.items.add(files[0]);
                fileInput.files = transfer.files;
                fileInput.dispatchEvent(new Event("change"));
            } catch (_error) {
                setSelectedFilename(`${files[0].name} (selected)`);
            }
        });
    }
});

