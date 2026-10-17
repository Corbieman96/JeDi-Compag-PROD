/**
 * Náhled ZPO u formuláře zákaznického požadavku — refresh po změně subjektu/odpadu/koncovky.
 */

export function bootCustomerRequestZpoPairing(cfg, hooks) {
    if (!cfg || !cfg.zpoPairing) return;

    const prev = hooks.onWasteOrSubjectChanged;
    hooks.onWasteOrSubjectChanged = function () {
        if (typeof prev === "function") {
            prev();
        }
        if (typeof window.jedisRefreshZpoPairingDock === "function") {
            window.jedisRefreshZpoPairingDock();
        }
    };

    ["id_suffix", "id_activity", "id_target_date", "id_address_value"].forEach(function (id) {
        const el = document.getElementById(id);
        if (!el) return;
        el.addEventListener("change", hooks.onWasteOrSubjectChanged);
        if (el.tagName === "INPUT" || el.tagName === "TEXTAREA") {
            el.addEventListener("blur", hooks.onWasteOrSubjectChanged);
        }
    });

    const nameLookup = document.getElementById("id_name_lookup");
    if (nameLookup) {
        nameLookup.addEventListener("change", hooks.onWasteOrSubjectChanged);
    }

    hooks.onWasteOrSubjectChanged();
}
