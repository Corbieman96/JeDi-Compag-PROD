(function (global) {
    "use strict";

    function resolveEl(idOrEl) {
        if (!idOrEl) {
            return null;
        }
        if (typeof idOrEl === "string") {
            return document.getElementById(idOrEl);
        }
        return idOrEl;
    }

    function showOverlay(overlay, label) {
        if (!overlay) {
            return;
        }
        if (label) {
            const labelEl = overlay.querySelector(".jedis-busy-overlay__label");
            if (labelEl) {
                labelEl.textContent = label;
            }
        }
        overlay.classList.add("is-active");
    }

    function hideOverlay(overlay) {
        if (!overlay) {
            return;
        }
        overlay.classList.remove("is-active");
    }

    function showInlineProgress(progressEl, label) {
        if (!progressEl) {
            return;
        }
        if (label) {
            const labelEl = progressEl.querySelector(".bulk-print-progress-label");
            if (labelEl) {
                labelEl.textContent = label;
            }
        }
        progressEl.hidden = false;
        progressEl.scrollIntoView({ behavior: "smooth", block: "center" });
    }

    function hideInlineProgress(progressEl) {
        if (!progressEl) {
            return;
        }
        progressEl.hidden = true;
    }

    function resetSubmittingControls() {
        document.querySelectorAll('[data-generate-link][data-submitting="1"]').forEach(function (link) {
            delete link.dataset.submitting;
        });
        document.querySelectorAll('form[data-generate-progress-form][data-submitting="1"]').forEach(function (form) {
            delete form.dataset.submitting;
            const submitBtn = form.querySelector('button[type="submit"]');
            if (submitBtn) {
                submitBtn.disabled = false;
            }
        });
    }

    global.JedisHideFormGenerateProgress = function (options) {
        options = options || {};
        hideOverlay(resolveEl(options.overlayId || "jedis-global-busy"));
        hideInlineProgress(resolveEl(options.inlineProgressId));
        resetSubmittingControls();
        try {
            sessionStorage.removeItem("jedisGeneratePending");
        } catch (e) {
            /* ignore */
        }
    };

    global.JedisShowFormGenerateProgress = function (form, options) {
        options = options || {};
        if (!form || form.dataset.submitting === "1") {
            return true;
        }
        form.dataset.submitting = "1";
        const overlay = resolveEl(options.overlayId || "jedis-global-busy");
        const inlineProgress = resolveEl(options.inlineProgressId);
        const overlayLabel = options.overlayLabel || options.label || "Generuji…";
        const inlineLabel = options.inlineLabel || options.label || overlayLabel;
        showOverlay(overlay, overlayLabel);
        showInlineProgress(inlineProgress, inlineLabel);
        const submitBtn = form.querySelector('button[type="submit"]');
        if (submitBtn) {
            submitBtn.disabled = true;
        }
        window.setTimeout(function () {
            form.submit();
        }, 250);
        return false;
    };

    function scheduleHideForBlankTargetLink(link, options) {
        options = options || {};
        const overlayId = options.overlayId || link.getAttribute("data-overlay-id") || "jedis-global-busy";
        let cleaned = false;

        function cleanup() {
            if (cleaned) {
                return;
            }
            cleaned = true;
            window.removeEventListener("blur", onBlur);
            window.removeEventListener("focus", onFocus);
            global.JedisHideFormGenerateProgress({ overlayId: overlayId });
        }

        function onBlur() {
            window.setTimeout(cleanup, 300);
        }

        function onFocus() {
            window.setTimeout(cleanup, 100);
        }

        window.addEventListener("blur", onBlur);
        window.addEventListener("focus", onFocus);
        window.setTimeout(cleanup, 60000);
    }

    global.JedisShowLinkGenerateProgress = function (link, options) {
        options = options || {};
        if (!link || link.dataset.submitting === "1") {
            return true;
        }
        link.dataset.submitting = "1";
        const overlayId = options.overlayId || link.getAttribute("data-overlay-id") || "jedis-global-busy";
        const overlay = resolveEl(overlayId);
        showOverlay(overlay, options.label || "Generuji…");
        try {
            sessionStorage.setItem("jedisGeneratePending", options.label || "1");
        } catch (e) {
            /* ignore */
        }
        if ((link.target || "").toLowerCase() === "_blank") {
            scheduleHideForBlankTargetLink(link, { overlayId: overlayId });
        }
        return true;
    };

    global.JedisInitAutoPrepareForms = function () {
        document.querySelectorAll("form[data-print-prepare-form]").forEach(function (form) {
            const label = form.getAttribute("data-prepare-label") || "Připravuji soubory k tisku…";
            window.setTimeout(function () {
                global.JedisShowFormGenerateProgress(form, {
                    overlayId: form.getAttribute("data-overlay-id") || "jedis-global-busy",
                    inlineProgressId: form.getAttribute("data-inline-progress-id") || "print-prepare-progress",
                    overlayLabel: label,
                    inlineLabel: label.replace("…", ", čekejte prosím…"),
                });
            }, 50);
        });
    };

    document.addEventListener("DOMContentLoaded", function () {
        global.JedisInitAutoPrepareForms();
        document.querySelectorAll("form[data-generate-progress-form]").forEach(function (form) {
            form.addEventListener("submit", function (event) {
                const label = form.getAttribute("data-progress-label") || "Generuji…";
                if (!global.JedisShowFormGenerateProgress(form, {
                    overlayId: form.getAttribute("data-overlay-id") || "jedis-global-busy",
                    inlineProgressId: form.getAttribute("data-inline-progress-id") || "",
                    overlayLabel: label,
                    inlineLabel: label.replace("…", ", čekejte prosím…"),
                })) {
                    event.preventDefault();
                }
            });
        });
        document.querySelectorAll("[data-generate-link]").forEach(function (link) {
            link.addEventListener("click", function () {
                global.JedisShowLinkGenerateProgress(link, {
                    overlayId: link.getAttribute("data-overlay-id") || "jedis-global-busy",
                    label: link.getAttribute("data-generate-label") || "Generuji…",
                });
            });
        });
    });

    window.addEventListener("pageshow", function (event) {
        if (event.persisted) {
            global.JedisHideFormGenerateProgress();
        }
    });
})(window);
