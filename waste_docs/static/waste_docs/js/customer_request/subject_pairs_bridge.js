/**
 * Modal úpravy párů odpad–koncovka pro formulář zákaznického požadavku.
 */

import { bootSubjectPairsModal } from "../pruvodka/subject_pairs_modal.js";

export function bootCustomerRequestSubjectPairs(cfg, hooks) {
    bootSubjectPairsModal(cfg, {
        getProfileId: function () {
            if (typeof hooks.getProfileId === "function") {
                return hooks.getProfileId();
            }
            return null;
        },
        applySnapshot: function (snapshot) {
            if (!snapshot) return;
            if (typeof hooks.applySubjectSnapshot === "function") {
                hooks.applySubjectSnapshot(snapshot);
            }
        },
    });

    const secondaryBtn = document.querySelector(
        "#customer-request-pairs-btn-wrap-waste .customer-request-edit-subject-pairs-btn"
    );
    const primaryBtn = document.getElementById("customer-request-edit-subject-pairs-btn");
    if (secondaryBtn && primaryBtn) {
        secondaryBtn.addEventListener("click", function (e) {
            e.preventDefault();
            e.stopPropagation();
            primaryBtn.click();
        });
    }
}
