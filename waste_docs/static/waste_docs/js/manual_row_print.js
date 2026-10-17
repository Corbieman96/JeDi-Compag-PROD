(function (global) {
    "use strict";

    function csrfToken() {
        const input = document.querySelector('input[name="csrfmiddlewaretoken"]');
        return input ? input.value : "";
    }

    function markRowPrinted(rowKey) {
        const url = global.JEDIS_PRINT_MARK_URL;
        const driveDate = global.JEDIS_PRINT_DATE;
        if (!url || !driveDate || !rowKey) {
            return Promise.resolve();
        }
        return fetch(url, {
            method: "POST",
            credentials: "same-origin",
            headers: {
                "Content-Type": "application/json",
                "X-CSRFToken": csrfToken(),
            },
            body: JSON.stringify({ date: driveDate, row_key: rowKey }),
        }).catch(function () {
            return undefined;
        });
    }

    function applyPrintedRowUi(rowKey) {
        const tr = document.querySelector('tr[data-row-key="' + rowKey + '"]');
        if (!tr) {
            return;
        }
        tr.classList.add("print-row-printed");
        const statusCell = tr.querySelector(".print-status-cell");
        if (statusCell) {
            statusCell.innerHTML = '<span class="print-badge-done">Vytištěno</span>';
        }
    }

    function printRowByKey(rowKey, rows, onStatus) {
        const bulk = global.JedisClientBulkPrint;
        if (!bulk || !rowKey) {
            return Promise.resolve();
        }
        const row = (rows || []).find(function (item) {
            return item && item.row_key === rowKey;
        });
        if (!row || !bulk.isPrintableRow(row)) {
            if (onStatus) {
                onStatus("Soubor nelze vytisknout.", true);
            }
            return Promise.resolve();
        }
        const url = bulk.printTargetUrl(row);
        return bulk.printPdfUrl(url).then(function () {
            return markRowPrinted(rowKey).then(function () {
                applyPrintedRowUi(rowKey);
            });
        }).catch(function (err) {
            const msg = (err && err.message) ? err.message : "";
            if (onStatus) {
                onStatus("Tisk selhal — " + msg, true);
            }
        });
    }

    function initManualRowPrint(rows, onStatus) {
        document.querySelectorAll(".js-print-row").forEach(function (btn) {
            btn.addEventListener("click", function () {
                const rowKey = btn.getAttribute("data-row-key") || "";
                btn.disabled = true;
                printRowByKey(rowKey, rows, onStatus).finally(function () {
                    btn.disabled = false;
                });
            });
        });
    }

    global.JedisManualRowPrint = {
        initManualRowPrint: initManualRowPrint,
        markRowPrinted: markRowPrinted,
        applyPrintedRowUi: applyPrintedRowUi,
        printRowByKey: printRowByKey,
    };
}(window));
