(function () {
    "use strict";

    var openBtn = document.getElementById("cr-day-kind-counts-open");
    var modal = document.getElementById("cr-day-kind-counts-modal");
    if (!openBtn || !modal) return;

    var dateDisplay = document.getElementById("cr-day-kind-counts-date-display");
    var headRow = document.getElementById("cr-day-kind-counts-head-row");
    var body = document.getElementById("cr-day-kind-counts-body");
    var loadingEl = document.getElementById("cr-day-kind-counts-loading");
    var errorEl = document.getElementById("cr-day-kind-counts-error");
    var noteEl = document.getElementById("cr-day-kind-counts-note");
    var apiUrl = openBtn.getAttribute("data-api-url") || "";

    if (!apiUrl || !headRow || !body) return;

    var prevOverflow = "";
    var fetchToken = 0;

    function setHidden(el, hidden) {
        if (!el) return;
        el.hidden = hidden;
        if (hidden) {
            el.setAttribute("hidden", "");
        } else {
            el.removeAttribute("hidden");
        }
    }

    function isModalOpen() {
        return modal.classList.contains("is-open");
    }

    function openModal() {
        if (modal.parentElement !== document.body) {
            document.body.appendChild(modal);
        }
        modal.classList.add("is-open");
        modal.setAttribute("aria-hidden", "false");
        openBtn.setAttribute("aria-expanded", "true");
        prevOverflow = document.body.style.overflow;
        document.body.style.overflow = "hidden";
        void loadCounts();
        openBtn.focus();
    }

    function closeModal() {
        modal.classList.remove("is-open");
        modal.setAttribute("aria-hidden", "true");
        openBtn.setAttribute("aria-expanded", "false");
        document.body.style.overflow = prevOverflow;
        openBtn.focus();
    }

    function renderTable(data) {
        headRow.innerHTML = "";
        body.innerHTML = "";

        var thLabel = document.createElement("th");
        thLabel.scope = "col";
        thLabel.textContent = "";
        headRow.appendChild(thLabel);

        (data.bucket_labels || []).forEach(function (label) {
            var th = document.createElement("th");
            th.scope = "col";
            th.textContent = label;
            headRow.appendChild(th);
        });

        var thTotal = document.createElement("th");
        thTotal.scope = "col";
        thTotal.textContent = "Celkem";
        headRow.appendChild(thTotal);

        (data.sections || []).forEach(function (section) {
            var tr = document.createElement("tr");

            var tdLabel = document.createElement("td");
            tdLabel.textContent = section.label || "";
            tr.appendChild(tdLabel);

            (section.counts || []).forEach(function (count) {
                var td = document.createElement("td");
                td.textContent = String(count);
                tr.appendChild(td);
            });

            var tdTotal = document.createElement("td");
            tdTotal.textContent = String(section.total || 0);
            tdTotal.style.fontWeight = "700";
            tr.appendChild(tdTotal);

            body.appendChild(tr);
        });

        if (dateDisplay) {
            dateDisplay.textContent = "Datum požadavku: " + (data.date_display || "");
        }

        var unclassifiedTotal = (data.sections || []).reduce(function (sum, section) {
            return sum + (section.unclassified || 0);
        }, 0);
        if (noteEl) {
            if (unclassifiedTotal > 0) {
                noteEl.textContent =
                    "Poznámka: " +
                    unclassifiedTotal +
                    " záznamů nemá přiřazený druh vozidla nebo nepatří do Řetěz / Atego / Hák.";
                setHidden(noteEl, false);
            } else {
                noteEl.textContent = "";
                setHidden(noteEl, true);
            }
        }
    }

    async function loadCounts() {
        var token = ++fetchToken;
        setHidden(loadingEl, false);
        setHidden(errorEl, true);
        if (errorEl) errorEl.textContent = "";

        try {
            var resp = await fetch(apiUrl, {
                headers: { Accept: "application/json" },
                credentials: "same-origin",
            });
            var payload = await resp.json();
            if (token !== fetchToken) return;
            if (!resp.ok || !payload.ok) {
                throw new Error((payload && payload.error) || "Nepodařilo se načíst počty.");
            }
            renderTable(payload.data || {});
        } catch (error) {
            if (token !== fetchToken) return;
            if (errorEl) {
                errorEl.textContent = error && error.message ? error.message : "Nepodařilo se načíst počty.";
                setHidden(errorEl, false);
            }
            headRow.innerHTML = "";
            body.innerHTML = "";
            if (dateDisplay) dateDisplay.textContent = "";
            if (noteEl) setHidden(noteEl, true);
        } finally {
            if (token === fetchToken) {
                setHidden(loadingEl, true);
            }
        }
    }

    openBtn.addEventListener("click", function (event) {
        event.preventDefault();
        openModal();
    });

    modal.querySelectorAll("[data-cr-day-kind-counts-close]").forEach(function (el) {
        el.addEventListener("click", function (event) {
            event.preventDefault();
            closeModal();
        });
    });

    modal.addEventListener("click", function (event) {
        if (event.target === modal) {
            closeModal();
        }
    });

    document.addEventListener("keydown", function (event) {
        if (event.key === "Escape" && isModalOpen()) {
            closeModal();
        }
    });
})();
