(function (global) {
    function rowPks(tbody) {
        return Array.from(tbody.querySelectorAll("tr[data-ride-pk]")).map(function (tr) {
            return parseInt(tr.getAttribute("data-ride-pk"), 10);
        });
    }

    function updateSeqLabels(tbody) {
        var rows = tbody.querySelectorAll("tr[data-ride-pk]");
        Array.from(rows).forEach(function (tr, idx) {
            var cell = tr.querySelector(".dash-ride-reorder-col-seq");
            if (!cell) return;
            cell.innerHTML = '<span class="dash-ride-route-order">' + (idx + 1) + "</span>";
        });
        updateArrowButtons(tbody);
    }

    function updateArrowButtons(tbody) {
        var rows = Array.from(tbody.querySelectorAll("tr[data-ride-pk]"));
        rows.forEach(function (tr, idx) {
            var up = tr.querySelector(".dash-ride-reorder-up");
            var down = tr.querySelector(".dash-ride-reorder-down");
            if (up) up.disabled = idx === 0;
            if (down) down.disabled = idx === rows.length - 1;
        });
    }

    function restoreOrder(tbody, order) {
        order.forEach(function (pk) {
            var tr = tbody.querySelector('tr[data-ride-pk="' + pk + '"]');
            if (tr) tbody.appendChild(tr);
        });
        updateSeqLabels(tbody);
    }

    function moveRow(tbody, tr, delta) {
        if (!tr || !delta) return false;
        if (delta < 0 && tr.previousElementSibling) {
            tbody.insertBefore(tr, tr.previousElementSibling);
            updateSeqLabels(tbody);
            return true;
        }
        if (delta > 0 && tr.nextElementSibling) {
            tbody.insertBefore(tr.nextElementSibling, tr);
            updateSeqLabels(tbody);
            return true;
        }
        return false;
    }

    function targetIndexFromY(tbody, clientY, dragRow) {
        var rows = Array.from(tbody.querySelectorAll("tr[data-ride-pk]"));
        for (var i = 0; i < rows.length; i += 1) {
            if (rows[i] === dragRow) continue;
            var rect = rows[i].getBoundingClientRect();
            if (clientY < rect.top + rect.height / 2) {
                return i;
            }
        }
        return rows.length - 1;
    }

    function moveRowToIndex(tbody, dragRow, targetIdx) {
        var rows = Array.from(tbody.querySelectorAll("tr[data-ride-pk]"));
        var currentIdx = rows.indexOf(dragRow);
        if (currentIdx < 0 || targetIdx < 0 || currentIdx === targetIdx) return;
        var ref = rows[targetIdx];
        if (!ref) return;
        if (currentIdx < targetIdx) {
            tbody.insertBefore(dragRow, ref.nextElementSibling);
        } else {
            tbody.insertBefore(dragRow, ref);
        }
    }

    function setupPointerReorder(tbody, isEditMode) {
        var dragRow = null;
        var lastTargetIdx = -1;

        tbody.addEventListener("mousedown", function (e) {
            if (!isEditMode()) return;
            if (e.button !== 0) return;
            var handle = e.target.closest(".dash-ride-reorder-handle");
            if (!handle || !tbody.contains(handle)) return;
            e.preventDefault();
            e.stopPropagation();
            dragRow = handle.closest("tr[data-ride-pk]");
            if (!dragRow) return;
            lastTargetIdx = Array.from(tbody.querySelectorAll("tr[data-ride-pk]")).indexOf(dragRow);
            dragRow.classList.add("dash-ride-reorder-row--dragging");
            document.body.classList.add("dash-ride-reorder-dragging");

            function onMove(ev) {
                if (!dragRow) return;
                ev.preventDefault();
                var targetIdx = targetIndexFromY(tbody, ev.clientY, dragRow);
                if (targetIdx === lastTargetIdx) return;
                moveRowToIndex(tbody, dragRow, targetIdx);
                lastTargetIdx = Array.from(tbody.querySelectorAll("tr[data-ride-pk]")).indexOf(dragRow);
            }

            function onUp() {
                document.removeEventListener("mousemove", onMove);
                document.removeEventListener("mouseup", onUp);
                document.body.classList.remove("dash-ride-reorder-dragging");
                if (dragRow) {
                    dragRow.classList.remove("dash-ride-reorder-row--dragging");
                    dragRow = null;
                    if (isEditMode()) updateSeqLabels(tbody);
                }
            }

            document.addEventListener("mousemove", onMove);
            document.addEventListener("mouseup", onUp);
        });
    }

    function setupArrowButtons(tbody, isEditMode) {
        tbody.addEventListener("click", function (e) {
            if (!isEditMode()) return;
            var up = e.target.closest(".dash-ride-reorder-up");
            var down = e.target.closest(".dash-ride-reorder-down");
            if (!up && !down) return;
            e.preventDefault();
            e.stopPropagation();
            var tr = (up || down).closest("tr[data-ride-pk]");
            if (!tr) return;
            moveRow(tbody, tr, up ? -1 : 1);
        });
    }

    global.jedisRideRouteReorderDom = {
        rowPks: rowPks,
        updateSeqLabels: updateSeqLabels,
        restoreOrder: restoreOrder,
        moveRow: moveRow,
        setupPointerReorder: setupPointerReorder,
        setupArrowButtons: setupArrowButtons,
    };
})(window);
