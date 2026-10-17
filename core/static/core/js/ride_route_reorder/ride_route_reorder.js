(function () {
    var dom = window.jedisRideRouteReorderDom;
    if (!dom) return;

    var REORDER_JS_VERSION = "7";

    function getCookie(name) {
        var parts = ("; " + document.cookie).split("; " + name + "=");
        if (parts.length === 2) {
            return parts.pop().split(";").shift();
        }
        return "";
    }

    function csrfToken() {
        var input = document.querySelector("[name=csrfmiddlewaretoken]");
        return (input && input.value) || getCookie("csrftoken") || "";
    }

    function showFeedback(root, text, isError) {
        if (!root) return;
        var fb = root.querySelector(".dash-ride-reorder-feedback");
        if (!fb) return;
        fb.hidden = !text;
        fb.textContent = text || "";
        fb.classList.toggle("is-error", !!isError);
    }

    function blockModalCloseWhileEditing(modal, isEditMode) {
        if (!modal || modal.getAttribute("data-reorder-close-guard") === "1") return;
        modal.setAttribute("data-reorder-close-guard", "1");
        modal.querySelectorAll("[data-dash-ride-detail-modal-close]").forEach(function (el) {
            el.addEventListener(
                "click",
                function (e) {
                    if (isEditMode()) {
                        e.preventDefault();
                        e.stopPropagation();
                        showFeedback(
                            modal.querySelector(".dash-ride-reorder-root"),
                            "Nejdřív uložte nebo zrušte úpravu pořadí.",
                            true
                        );
                    }
                },
                true
            );
        });
    }

    function initRoot(root) {
        if (root.getAttribute("data-reorder-bound") === "1") return;
        root.setAttribute("data-reorder-bound", "1");

        var tbody = root.querySelector(".dash-ride-reorder-tbody");
        if (!tbody) return;

        var reorderUrl = root.getAttribute("data-reorder-url");
        var promptUrl = root.getAttribute("data-prompt-url");
        var optimizeUrl = root.getAttribute("data-optimize-url");
        var optimizeApplyUrl = root.getAttribute("data-optimize-apply-url");
        var driveDate = root.getAttribute("data-drive-date");
        var vehicleRzId = root.getAttribute("data-vehicle-rz-id");
        var driverId = root.getAttribute("data-driver-id");
        var rideGroup = root.getAttribute("data-ride-group");
        var toolbar = root.querySelector(".dash-ride-reorder-toolbar");
        var statusEl = root.querySelector(".dash-ride-reorder-status");
        var saveBtn = root.querySelector(".dash-ride-reorder-save");
        var cancelBtn = root.querySelector(".dash-ride-reorder-cancel");
        var resetBtn = root.querySelector(".dash-ride-reorder-reset");
        var modal = root.closest(".dash-ride-detail-modal");
        var toggleBtn = modal && modal.querySelector(".dash-ride-reorder-toggle");
        var optimizeBtn = modal && modal.querySelector(".dash-ride-reorder-optimize-btn");
        var aiBtn = modal && modal.querySelector(".dash-ride-reorder-ai-btn");

        var initialOrder = dom.rowPks(tbody);
        var editMode = false;

        dom.setupPointerReorder(tbody, function () {
            return editMode;
        });
        dom.setupArrowButtons(tbody, function () {
            return editMode;
        });
        blockModalCloseWhileEditing(modal, function () {
            return editMode;
        });

        function setEditMode(on) {
            editMode = !!on;
            root.classList.toggle("is-reorder-mode", editMode);
            if (modal) modal.classList.toggle("dash-ride-detail-modal--reorder-editing", editMode);
            if (toolbar) toolbar.hidden = !editMode;
            if (toggleBtn) {
                toggleBtn.textContent = editMode ? "Ukončit úpravu" : "Uspořádat zastávky";
                toggleBtn.classList.toggle("is-active", editMode);
            }
            if (statusEl) {
                statusEl.textContent = editMode
                    ? "Přetáhněte řádky (⠿) nebo použijte ↑↓. Poté uložte pořadí."
                    : "";
            }
            if (!editMode) {
                showFeedback(root, "", false);
            } else {
                dom.updateSeqLabels(tbody);
            }
        }

        function apiParams() {
            return (
                "date=" +
                encodeURIComponent(driveDate) +
                "&ride_group=" +
                encodeURIComponent(rideGroup) +
                "&vehicle_rz_id=" +
                encodeURIComponent(vehicleRzId) +
                "&driver_id=" +
                encodeURIComponent(driverId)
            );
        }

        if (toggleBtn) {
            toggleBtn.addEventListener("click", function () {
                if (root.classList.contains("dash-ride-reorder-root--disabled")) return;
                if (editMode) {
                    dom.restoreOrder(tbody, initialOrder);
                    setEditMode(false);
                } else {
                    initialOrder = dom.rowPks(tbody);
                    setEditMode(true);
                }
            });
        }

        if (saveBtn) {
            saveBtn.addEventListener("click", function () {
                var order = dom.rowPks(tbody);
                saveBtn.disabled = true;
                fetch(reorderUrl + "?" + apiParams(), {
                    method: "POST",
                    credentials: "same-origin",
                    headers: {
                        "Content-Type": "application/json",
                        "X-CSRFToken": csrfToken(),
                        "X-Requested-With": "XMLHttpRequest",
                    },
                    body: JSON.stringify({ order: order }),
                })
                    .then(function (res) {
                        return res.json().then(function (data) {
                            return { ok: res.ok, data: data };
                        });
                    })
                    .then(function (result) {
                        saveBtn.disabled = false;
                        if (!result.ok || !result.data.ok) {
                            showFeedback(
                                root,
                                (result.data && result.data.error) || "Uložení pořadí se nepodařilo.",
                                true
                            );
                            return;
                        }
                        window.location.reload();
                    })
                    .catch(function () {
                        saveBtn.disabled = false;
                        showFeedback(root, "Uložení pořadí se nepodařilo — zkuste to znovu.", true);
                    });
            });
        }

        if (cancelBtn) {
            cancelBtn.addEventListener("click", function () {
                dom.restoreOrder(tbody, initialOrder);
                setEditMode(false);
            });
        }

        if (resetBtn) {
            resetBtn.addEventListener("click", function () {
                if (!window.confirm("Vrátit výchozí pořadí (podle SND)? Ruční pořadí trasy se zruší.")) {
                    return;
                }
                resetBtn.disabled = true;
                fetch(reorderUrl + "?" + apiParams(), {
                    method: "POST",
                    credentials: "same-origin",
                    headers: {
                        "Content-Type": "application/json",
                        "X-CSRFToken": csrfToken(),
                        "X-Requested-With": "XMLHttpRequest",
                    },
                    body: JSON.stringify({ reset: true }),
                })
                    .then(function (res) {
                        return res.json();
                    })
                    .then(function (data) {
                        resetBtn.disabled = false;
                        if (data.ok) window.location.reload();
                        else showFeedback(root, data.error || "Operace se nepodařila.", true);
                    })
                    .catch(function () {
                        resetBtn.disabled = false;
                        showFeedback(root, "Operace se nepodařila.", true);
                    });
            });
        }

        if (aiBtn) {
            aiBtn.addEventListener("click", function () {
                fetch(promptUrl + "?" + apiParams(), {
                    credentials: "same-origin",
                    headers: { "X-Requested-With": "XMLHttpRequest" },
                })
                    .then(function (res) {
                        return res.json();
                    })
                    .then(function (data) {
                        if (!data.ok || !data.prompt) {
                            showFeedback(root, data.error || "Prompt se nepodařilo načíst.", true);
                            return;
                        }
                        if (navigator.clipboard && navigator.clipboard.writeText) {
                            navigator.clipboard.writeText(data.prompt).then(function () {
                                showFeedback(
                                    root,
                                    "Prompt zkopírován — vložte do AI; odpověď (pk po řádcích) pak seřaďte a uložte.",
                                    false
                                );
                            });
                        } else {
                            window.prompt("Zkopírujte prompt pro AI:", data.prompt);
                        }
                    })
                    .catch(function () {
                        showFeedback(root, "Prompt se nepodařilo načíst.", true);
                    });
            });
        }

        if (optimizeBtn) {
            optimizeBtn.addEventListener("click", function () {
                if (root.classList.contains("dash-ride-reorder-root--disabled")) return;
                optimizeBtn.disabled = true;
                fetch(optimizeUrl + "?" + apiParams(), {
                    credentials: "same-origin",
                    headers: { "X-Requested-With": "XMLHttpRequest" },
                })
                    .then(function (res) {
                        return res.json().then(function (data) {
                            return { ok: res.ok, data: data };
                        });
                    })
                    .then(function (result) {
                        optimizeBtn.disabled = false;
                        if (!result.ok || !result.data.ok || !result.data.order) {
                            showFeedback(
                                root,
                                (result.data && result.data.error) || "Optimalizace se nepodařila.",
                                true
                            );
                            return;
                        }
                        var applyNow = window.confirm(
                            "Navržené pořadí:\n" +
                                result.data.order.join(" → ") +
                                "\n\nUložit toto pořadí trasy?"
                        );
                        if (!applyNow) {
                            if (!editMode) {
                                initialOrder = dom.rowPks(tbody);
                                setEditMode(true);
                            }
                            dom.restoreOrder(tbody, result.data.order);
                            showFeedback(
                                root,
                                "Pořadí v tabulce upraveno — zkontrolujte a uložte.",
                                false
                            );
                            return;
                        }
                        optimizeBtn.disabled = true;
                        fetch(optimizeApplyUrl + "?" + apiParams(), {
                            method: "POST",
                            credentials: "same-origin",
                            headers: {
                                "Content-Type": "application/json",
                                "X-CSRFToken": csrfToken(),
                                "X-Requested-With": "XMLHttpRequest",
                            },
                            body: "{}",
                        })
                            .then(function (res) {
                                return res.json();
                            })
                            .then(function (data) {
                                optimizeBtn.disabled = false;
                                if (data.ok) window.location.reload();
                                else showFeedback(root, data.error || "Uložení se nepodařilo.", true);
                            })
                            .catch(function () {
                                optimizeBtn.disabled = false;
                                showFeedback(root, "Uložení se nepodařilo.", true);
                            });
                    })
                    .catch(function () {
                        optimizeBtn.disabled = false;
                        showFeedback(root, "Optimalizace se nepodařila.", true);
                    });
            });
        }
    }

    function initAll() {
        document.querySelectorAll(".dash-ride-reorder-root").forEach(initRoot);
    }

    window.jedisInitRideRouteReorder = initAll;
    window.jedisRideRouteReorderVersion = REORDER_JS_VERSION;

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", initAll);
    } else {
        initAll();
    }
})();
