(function () {
    "use strict";

    function normalizeQuery(value) {
        return (value || "").trim().casefold();
    }

    function rowMatches(row, query, year, type) {
        if (year && row.getAttribute("data-year") !== year) {
            return false;
        }
        if (type && row.getAttribute("data-type") !== type) {
            return false;
        }
        if (query) {
            var haystack = row.getAttribute("data-search-text") || "";
            if (!haystack.includes(query)) {
                return false;
            }
        }
        return true;
    }

    function filtersActive(query, year, type, defaultYear) {
        if (query) {
            return true;
        }
        if (type) {
            return true;
        }
        if (year && year !== String(defaultYear || "")) {
            return true;
        }
        return false;
    }

    function initPanel(panel) {
        var qInput = panel.querySelector("[data-driver-absence-q]");
        var yearSelect = panel.querySelector("[data-driver-absence-year]");
        var typeSelect = panel.querySelector("[data-driver-absence-type]");
        var resetBtn = panel.querySelector("[data-driver-absence-reset]");
        var visibleCountEl = panel.querySelector("[data-driver-absence-visible-count]");
        var tbody = panel.querySelector("[data-driver-absence-tbody]");
        var noMatchEl = panel.querySelector("[data-driver-absence-no-match]");
        if (!tbody) {
            return;
        }

        var rows = Array.prototype.slice.call(tbody.querySelectorAll(".driver-absence-row"));
        var defaultYear = yearSelect ? yearSelect.value : "";

        function applyFilters() {
            var query = normalizeQuery(qInput ? qInput.value : "");
            var year = yearSelect ? yearSelect.value : "";
            var type = typeSelect ? typeSelect.value : "";
            var visible = 0;

            rows.forEach(function (row) {
                var show = rowMatches(row, query, year, type);
                row.classList.toggle("is-hidden", !show);
                row.hidden = !show;
                if (show) {
                    visible += 1;
                }
            });

            if (visibleCountEl) {
                visibleCountEl.textContent = String(visible);
            }
            if (noMatchEl) {
                noMatchEl.hidden = visible > 0;
            }
            if (resetBtn) {
                resetBtn.hidden = !filtersActive(query, year, type, defaultYear);
            }
        }

        function resetFilters() {
            if (qInput) {
                qInput.value = "";
            }
            if (yearSelect) {
                yearSelect.value = defaultYear;
            }
            if (typeSelect) {
                typeSelect.value = "";
            }
            applyFilters();
        }

        if (qInput) {
            qInput.addEventListener("input", applyFilters);
        }
        if (yearSelect) {
            yearSelect.addEventListener("change", applyFilters);
        }
        if (typeSelect) {
            typeSelect.addEventListener("change", applyFilters);
        }
        if (resetBtn) {
            resetBtn.addEventListener("click", resetFilters);
        }

        applyFilters();
    }

    document.addEventListener("DOMContentLoaded", function () {
        document.querySelectorAll("[data-driver-absence-panel]").forEach(initPanel);
    });
})();
