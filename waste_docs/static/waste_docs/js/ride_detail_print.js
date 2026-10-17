(function () {
    "use strict";

    const modal = document.getElementById("detail-print-modal");
    const openBtn = document.getElementById("detail-print-open");
    const cancelBtn = document.getElementById("detail-print-cancel");
    const runLink = document.getElementById("detail-print-run");
    const statusEl = document.getElementById("detail-print-status");
    const optionsWrap = document.getElementById("detail-print-options");

    if (!modal || !openBtn) {
        return;
    }

    function showStatus(message, isError) {
        if (!statusEl) {
            return;
        }
        statusEl.textContent = message || "";
        statusEl.classList.toggle("is-visible", Boolean(message));
        statusEl.classList.toggle("is-error", Boolean(isError));
    }

    function closeModal() {
        showStatus("");
        modal.style.display = "none";
    }

    function selectedOption() {
        if (!optionsWrap) {
            return null;
        }
        const checked = optionsWrap.querySelector(
            'input[name="detail_print_kind"]:checked:not([disabled])'
        );
        return checked || optionsWrap.querySelector('input[name="detail_print_kind"]:not([disabled])');
    }

    function syncRunLink() {
        if (!runLink) {
            return;
        }
        const input = selectedOption();
        const url = input ? (input.getAttribute("data-print-url") || "") : "";
        runLink.href = url || "#";
    }

    function openModal() {
        showStatus("");
        modal.style.display = "flex";
        if (optionsWrap) {
            const pendingUrl = window.__JEDIS_DETAIL_PRINT_PENDING_URL__ || "";
            let matched = false;
            if (pendingUrl) {
                optionsWrap.querySelectorAll('input[name="detail_print_kind"]').forEach(function (input) {
                    if ((input.getAttribute("data-print-url") || "") === pendingUrl) {
                        input.checked = true;
                        matched = true;
                    }
                });
                window.__JEDIS_DETAIL_PRINT_PENDING_URL__ = "";
            }
            if (!matched) {
                const enabled = optionsWrap.querySelector(
                    'input[name="detail_print_kind"]:not([disabled])'
                );
                if (enabled) {
                    enabled.checked = true;
                }
            }
        }
        syncRunLink();
    }

    function openPdfInNewTab(url) {
        if (!url) {
            showStatus("PDF není k dispozici.", true);
            return false;
        }
        const popup = window.open(url, "_blank", "noopener,noreferrer");
        if (!popup) {
            showStatus(
                "Prohlížeč zablokoval novou záložku. Klikněte znovu na „Otevřít PDF“ nebo povolte vyskakovací okna.",
                true
            );
            return false;
        }
        closeModal();
        return true;
    }

    openBtn.addEventListener("click", openModal);

    if (cancelBtn) {
        cancelBtn.addEventListener("click", closeModal);
    }

    if (optionsWrap) {
        optionsWrap.addEventListener("change", syncRunLink);
    }

    modal.addEventListener("click", function (event) {
        if (event.target === modal) {
            closeModal();
        }
    });

    if (runLink) {
        runLink.addEventListener("click", function (event) {
            syncRunLink();
            const url = runLink.getAttribute("href") || "";
            if (!url || url === "#") {
                event.preventDefault();
                showStatus("Vyberte položku k tisku.", true);
                return;
            }
            window.setTimeout(closeModal, 0);
        });
    }

    if (window.__JEDIS_OPEN_DETAIL_PRINT__) {
        openModal();
        window.__JEDIS_OPEN_DETAIL_PRINT__ = false;
    } else if (window.__JEDIS_AUTO_OPEN_PDF_URL__) {
        const autoUrl = window.__JEDIS_AUTO_OPEN_PDF_URL__;
        window.__JEDIS_AUTO_OPEN_PDF_URL__ = "";
        if (!openPdfInNewTab(autoUrl)) {
            window.__JEDIS_DETAIL_PRINT_PENDING_URL__ = autoUrl;
            openModal();
        }
    }
})();
