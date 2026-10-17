(function () {
    function parseData() {
        var el = document.getElementById("ride-reassign-driver-data");
        if (!el) return null;
        try {
            return JSON.parse(el.textContent || "{}");
        } catch (e) {
            return null;
        }
    }

    function fillRzSelect(select, options, currentRzId) {
        if (!select) return;
        var keepLabel = "Stávající RZ";
        var cur = String(currentRzId || "");
        var found = null;
        options.forEach(function (o) {
            if (String(o.id) === cur) found = o;
        });
        if (found) keepLabel = "Stávající RZ (" + found.label + ")";

        select.innerHTML = "";
        var keep = document.createElement("option");
        keep.value = cur;
        keep.textContent = keepLabel;
        keep.title = keepLabel;
        select.appendChild(keep);

        options.forEach(function (o) {
            if (String(o.id) === cur) return;
            var opt = document.createElement("option");
            opt.value = String(o.id);
            opt.textContent = o.label;
            opt.title = o.label;
            select.appendChild(opt);
        });
        select.value = cur;
    }

    function init() {
        var data = parseData();
        var openBtn = document.getElementById("ride-reassign-driver-open");
        var backdrop = document.getElementById("ride-reassign-driver-modal");
        if (!data || !openBtn || !backdrop) return;

        var form = document.getElementById("ride-reassign-driver-form");
        var driverSelect = document.getElementById("ride-reassign-driver-select");
        var rzSelect = document.getElementById("ride-reassign-rz-select");
        var selectAll = document.getElementById("ride-reassign-select-all");
        var cancelBtn = document.getElementById("ride-reassign-cancel");
        var submitBtn = document.getElementById("ride-reassign-submit");

        function rideChecks() {
            return Array.prototype.slice.call(
                backdrop.querySelectorAll('input[name="ride_pks"]')
            );
        }

        function openPanel() {
            backdrop.hidden = false;
            backdrop.classList.add("is-open");
            backdrop.setAttribute("aria-hidden", "false");
            if (driverSelect) driverSelect.focus();
        }

        function closePanel() {
            backdrop.classList.remove("is-open");
            backdrop.hidden = true;
            backdrop.setAttribute("aria-hidden", "true");
        }

        function syncRzForDriver() {
            var driverId = driverSelect ? String(driverSelect.value || "") : "";
            var map = data.rz_by_driver || {};
            var options = driverId && map[driverId] ? map[driverId] : data.rz_options || [];
            fillRzSelect(rzSelect, options, data.current_rz_id);
        }

        function syncSubmit() {
            var any = rideChecks().some(function (c) { return c.checked; });
            var hasDriver = driverSelect && String(driverSelect.value || "") !== "";
            if (submitBtn) submitBtn.disabled = !(any && hasDriver);
        }

        openBtn.addEventListener("click", function (e) {
            e.preventDefault();
            e.stopPropagation();
            openPanel();
            syncRzForDriver();
            syncSubmit();
        });

        if (cancelBtn) {
            cancelBtn.addEventListener("click", function (e) {
                e.preventDefault();
                closePanel();
            });
        }

        if (selectAll) {
            selectAll.addEventListener("change", function () {
                var on = selectAll.checked;
                rideChecks().forEach(function (c) { c.checked = on; });
                syncSubmit();
            });
        }

        rideChecks().forEach(function (c) {
            c.addEventListener("change", function () {
                var all = rideChecks();
                if (selectAll) {
                    selectAll.checked = all.length > 0 && all.every(function (x) { return x.checked; });
                }
                syncSubmit();
            });
        });

        if (driverSelect) {
            driverSelect.addEventListener("change", function () {
                syncRzForDriver();
                syncSubmit();
            });
        }

        if (form) {
            form.addEventListener("submit", function (e) {
                var any = rideChecks().some(function (c) { return c.checked; });
                var hasDriver = driverSelect && String(driverSelect.value || "") !== "";
                if (!any || !hasDriver) {
                    e.preventDefault();
                    syncSubmit();
                }
            });
        }

        document.addEventListener(
            "keydown",
            function (e) {
                if (e.key === "Escape" && backdrop.classList.contains("is-open")) {
                    e.preventDefault();
                    e.stopPropagation();
                }
            },
            true
        );

        syncRzForDriver();
        syncSubmit();
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", init);
    } else {
        init();
    }
})();
