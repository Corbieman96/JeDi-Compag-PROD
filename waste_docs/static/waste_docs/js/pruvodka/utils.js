/** Malé čisté helpery pro formulář průvodky (bez závislosti na DOM uzlech). */

export function normalizeLabelSearch(value) {
    return (value || "").toLowerCase().replace(/\s+/g, " ").trim();
}

export function setSelectValue(selectEl, value) {
    if (!selectEl || value === null || value === undefined) return;
    const target = String(value);
    const options = selectEl.options ? Array.from(selectEl.options) : [];
    if (!options.length) {
        selectEl.value = target;
        return;
    }
    const option = options.find((o) => o.value === target);
    if (option) {
        selectEl.value = target;
    }
}

export function showFieldRow(key, mode) {
    document.querySelectorAll(`[data-field-key="${key}"]`).forEach((row) => {
        row.style.display = mode === "off" ? "none" : "";
    });
}
