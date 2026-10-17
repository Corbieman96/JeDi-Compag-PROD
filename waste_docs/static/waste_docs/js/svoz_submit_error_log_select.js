(function () {
    const form = document.getElementById("svoz-log-select-form");
    if (!form) return;

    function rowChecksForDay(day) {
        return form.querySelectorAll('.svoz-log-row-check[data-day="' + day + '"]');
    }

    function syncDayFromRows(day) {
        const dayCb = form.querySelector('.svoz-log-day-check[data-day="' + day + '"]');
        if (!dayCb) return;
        const rows = rowChecksForDay(day);
        let checked = 0;
        rows.forEach(function (cb) {
            if (cb.checked) checked += 1;
        });
        dayCb.checked = rows.length > 0 && checked === rows.length;
        dayCb.indeterminate = checked > 0 && checked < rows.length;
    }

    form.querySelectorAll(".svoz-log-day-check").forEach(function (dayCb) {
        dayCb.addEventListener("change", function () {
            const day = dayCb.getAttribute("data-day") || "";
            rowChecksForDay(day).forEach(function (rowCb) {
                rowCb.checked = dayCb.checked;
            });
            dayCb.indeterminate = false;
        });
    });

    form.querySelectorAll(".svoz-log-row-check").forEach(function (rowCb) {
        rowCb.addEventListener("change", function () {
            syncDayFromRows(rowCb.getAttribute("data-day") || "");
        });
    });

    form.addEventListener("submit", function (e) {
        const any = form.querySelector(".svoz-log-day-check:checked, .svoz-log-row-check:checked");
        if (!any) {
            e.preventDefault();
            window.alert("Vyberte dny nebo záznamy ke smazání.");
            return;
        }
        if (!window.confirm("Smazat vybrané dny a záznamy z logu?")) {
            e.preventDefault();
        }
    });
})();
