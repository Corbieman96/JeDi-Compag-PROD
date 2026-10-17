/**
 * Modal úpravy párů odpad–koncovka z formuláře jízdy (bez opuštění stránky).
 */
export function bootSubjectPairsModal(cfg, hooks) {
    const buttonId = (cfg && cfg.subjectPairsButtonId) || "jedis-edit-subject-pairs-btn";
    const btn = document.getElementById(buttonId);
    const modal = document.getElementById("jedis-subject-pairs-modal");
    const bodyEl = document.getElementById("jedis-subject-pairs-modal-body");
    const saveBtn = document.getElementById("jedis-subject-pairs-modal-save");
    if (!btn || !modal || !bodyEl || !saveBtn) {
        console.warn("Subject pairs modal: chybí elementy v DOM.");
        return;
    }

    const urlTemplate = cfg.urls && cfg.urls.nameSubjectPairsModal;
    const profileByNameUrl = cfg.urls && cfg.urls.subjectProfileByName;
    if (!urlTemplate) {
        console.warn("Subject pairs modal: chybí URL nameSubjectPairsModal.");
        return;
    }

    const getProfileId = hooks && hooks.getProfileId;
    const ensureSubject = hooks && hooks.ensureSubject;
    const applySnapshot = hooks && hooks.applySnapshot;

    let loading = false;

    function pairsModalUrl(profileId) {
        return urlTemplate.replace("__PROFILE_PK__", String(profileId));
    }

    function setOpen(open) {
        modal.classList.toggle("is-open", open);
        modal.setAttribute("aria-hidden", open ? "false" : "true");
        if (!open) {
            bodyEl.innerHTML = "";
        }
    }

    async function resolveProfileId() {
        let profileId = typeof getProfileId === "function" ? getProfileId() : null;
        if (profileId) return profileId;

        if (typeof ensureSubject === "function") {
            const icoLookup = document.getElementById("id_ico_lookup");
            const hit = await ensureSubject(icoLookup ? icoLookup.value : "");
            if (hit && hit.subject_profile_id) {
                return hit.subject_profile_id;
            }
            if (hit && hit.name_id && profileByNameUrl) {
                const r = await fetch(
                    `${profileByNameUrl}?name_id=${encodeURIComponent(hit.name_id)}`,
                    { credentials: "same-origin" }
                );
                const payload = await r.json().catch(() => ({}));
                if (payload.ok && payload.subject_profile_id) {
                    return payload.subject_profile_id;
                }
            }
        }

        const nameSelect = document.getElementById("id_name");
        if (nameSelect && nameSelect.value && profileByNameUrl) {
            const r = await fetch(
                `${profileByNameUrl}?name_id=${encodeURIComponent(nameSelect.value)}`,
                { credentials: "same-origin" }
            );
            const payload = await r.json().catch(() => ({}));
            if (payload.ok && payload.subject_profile_id) {
                return payload.subject_profile_id;
            }
        }

        const nameExisting = document.getElementById("id_name_existing");
        if (nameExisting && nameExisting.value && profileByNameUrl) {
            const r = await fetch(
                `${profileByNameUrl}?name_id=${encodeURIComponent(nameExisting.value)}`,
                { credentials: "same-origin" }
            );
            const payload = await r.json().catch(() => ({}));
            if (payload.ok && payload.subject_profile_id) {
                return payload.subject_profile_id;
            }
        }
        return null;
    }

    function mergeZpoUrlMapFromModal(root) {
        const src = root.querySelector("#name-subject-zpo-urls-modal");
        const tgt = document.getElementById("name-subject-zpo-urls");
        if (src && tgt) {
            tgt.textContent = src.textContent;
        }
    }

    function initModalBody(root) {
        mergeZpoUrlMapFromModal(root);
        const form = root.querySelector("#jedis-name-subject-pairs-modal-form");
        if (!form) return;
        if (window.jedisInitWasteCombosIn) {
            const list = form.querySelector(".name-subject-pairs__list");
            if (list) window.jedisInitWasteCombosIn(list);
        }
        if (window.jedisInitNameSubjectPairsFormset) {
            window.jedisInitNameSubjectPairsFormset(form);
        }
        if (window.jedisInitPairFulfillmentSafe) {
            window.jedisInitPairFulfillmentSafe(form);
        }
        if (window.jedisRefreshZpoPairCardsIn) {
            window.jedisRefreshZpoPairCardsIn(form);
        }
    }

    async function openModal() {
        if (loading) return;
        const profileId = await resolveProfileId();
        if (!profileId) {
            alert(
                "Subjekt zatím není vybrán.\n\nVyberte firmu z našeptávače (klik na položku v seznamu) " +
                    "nebo dokončete výběr klávesou Enter po vyplnění názvu."
            );
            return;
        }
        loading = true;
        btn.setAttribute("aria-busy", "true");
        try {
            const response = await fetch(pairsModalUrl(profileId), {
                headers: { Accept: "text/html" },
                credentials: "same-origin",
            });
            if (!response.ok) {
                alert("Nepodařilo se načíst formulář párů (kód " + response.status + ").");
                return;
            }
            const html = await response.text();
            bodyEl.innerHTML = html;
            initModalBody(bodyEl);
            setOpen(true);
        } finally {
            loading = false;
            btn.removeAttribute("aria-busy");
        }
    }

    async function saveModal() {
        const form = bodyEl.querySelector("#jedis-name-subject-pairs-modal-form");
        if (!form || loading) return;
        if (window.jedisFlushWasteCombosInForm) {
            window.jedisFlushWasteCombosInForm(form);
        }
        const errBox = bodyEl.querySelector("#jedis-pairs-modal-errors");
        if (errBox) {
            errBox.hidden = true;
            errBox.textContent = "";
        }
        loading = true;
        saveBtn.disabled = true;
        try {
            const response = await fetch(form.action, {
                method: "POST",
                body: new FormData(form),
                credentials: "same-origin",
                headers: {
                    Accept: "application/json",
                    "X-Requested-With": "XMLHttpRequest",
                },
            });
            const payload = await response.json().catch(() => ({}));
            if (!response.ok || !payload.ok) {
                if (payload.html) {
                    bodyEl.innerHTML = payload.html;
                    initModalBody(bodyEl);
                }
                const msg = payload.error || "Formulář nelze uložit.";
                if (errBox) {
                    errBox.textContent = msg;
                    errBox.hidden = false;
                } else {
                    alert(msg);
                }
                return;
            }
            if (payload.subject && typeof applySnapshot === "function") {
                applySnapshot(payload.subject);
            }
            setOpen(false);
        } finally {
            loading = false;
            saveBtn.disabled = false;
        }
    }

    btn.addEventListener("click", function (e) {
        e.preventDefault();
        e.stopPropagation();
        void openModal();
    });
    saveBtn.addEventListener("click", function () {
        void saveModal();
    });
    modal.querySelectorAll("[data-subject-pairs-modal-close]").forEach(function (el) {
        el.addEventListener("click", function () {
            setOpen(false);
        });
    });
    modal.addEventListener("click", function (e) {
        if (e.target === modal) setOpen(false);
    });

    window.jedisSyncSubjectPairsEditButton = function () {
        /* Tlačítko je vždy aktivní; profil se řeší až při kliknutí. */
    };
}
