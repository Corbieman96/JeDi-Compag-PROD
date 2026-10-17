import { bootWasteFieldControls } from "./waste_field_controls.js";
import { bootCustomerRequestSubjectPairs } from "./subject_pairs_bridge.js";
import { bootCustomerRequestZpoPairing } from "./zpo_pairing_bridge.js";

function readConfig() {
    const el = document.getElementById("customer-request-form-config");
    if (!el) return null;
    try {
        return JSON.parse(el.textContent || "{}");
    } catch (e) {
        return null;
    }
}

export function bootCustomerRequestFormExtras() {
    const cfg = readConfig();
    const hooks = window.customerRequestFormHooks;
    if (!hooks) return;

    bootWasteFieldControls(hooks);
    if (cfg) {
        bootCustomerRequestZpoPairing(cfg, hooks);
        if (cfg.canEditNameSubjectPairs) {
            bootCustomerRequestSubjectPairs(cfg, hooks);
        }
    }
}

window.bootCustomerRequestFormExtras = bootCustomerRequestFormExtras;

if (window.customerRequestFormHooks) {
    bootCustomerRequestFormExtras();
} else {
    document.addEventListener("customer-request-form-ready", bootCustomerRequestFormExtras, { once: true });
}
