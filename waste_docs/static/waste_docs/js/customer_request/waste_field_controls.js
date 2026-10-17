/**
 * Tlačítka „x“ a sync kódu/kategorie odpadu u formuláře zákaznického požadavku.
 */

export function bootWasteFieldControls(hooks) {
    const wasteClearBtn = document.getElementById("customer-request-waste-clear");
    const vehicleKindClearBtn = document.getElementById("customer-request-vehicle-kind-clear");
    const suffixClearBtn = document.getElementById("customer-request-suffix-clear");
    const codeEl = document.getElementById("customer-request-waste-code");
    const categoryEl = document.getElementById("customer-request-waste-category");

    function syncWasteMeta() {
        const wasteSelect = document.getElementById("id_waste_type");
        const api = hooks.getWasteComboApi ? hooks.getWasteComboApi() : null;
        const metaMap = api && api.wasteTypeMeta ? api.wasteTypeMeta : {};
        const pk = wasteSelect ? String(wasteSelect.value || "") : "";
        const meta = pk ? metaMap[pk] || {} : {};
        if (codeEl) codeEl.value = meta.code || "";
        if (categoryEl) categoryEl.value = meta.category || "";
        if (typeof hooks.onWasteOrSubjectChanged === "function") {
            hooks.onWasteOrSubjectChanged();
        }
    }

    hooks.syncWasteMeta = syncWasteMeta;

    if (wasteClearBtn) {
        wasteClearBtn.addEventListener("click", function () {
            const wasteSelect = document.getElementById("id_waste_type");
            const lookupHidden = document.getElementById("id_waste_type_lookup");
            const api = hooks.getWasteComboApi ? hooks.getWasteComboApi() : null;
            if (api && api.input) {
                api.input.value = "";
            }
            if (wasteSelect) wasteSelect.value = "";
            if (lookupHidden) lookupHidden.value = "";
            if (api && api.refresh) api.refresh();
            syncWasteMeta();
            if (typeof hooks.clearWasteFollowUp === "function") {
                hooks.clearWasteFollowUp();
            }
            if (api && api.input) api.input.focus();
        });
    }

    if (suffixClearBtn) {
        suffixClearBtn.addEventListener("click", function () {
            const suffixSelect = document.getElementById("id_suffix");
            if (suffixSelect) suffixSelect.value = "";
            if (typeof hooks.onWasteOrSubjectChanged === "function") {
                hooks.onWasteOrSubjectChanged();
            }
        });
    }

    if (vehicleKindClearBtn) {
        vehicleKindClearBtn.addEventListener("click", function () {
            const vehicleKindSelect = document.getElementById("id_vehicle_kind");
            if (vehicleKindSelect) vehicleKindSelect.value = "";
            if (typeof hooks.onWasteOrSubjectChanged === "function") {
                hooks.onWasteOrSubjectChanged();
            }
        });
    }

    syncWasteMeta();
}
