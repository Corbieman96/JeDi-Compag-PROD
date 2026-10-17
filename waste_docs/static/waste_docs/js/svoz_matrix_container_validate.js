(function () {
    const form = document.querySelector(".svoz-matrix-form");
    if (!form) return;
    const validateUrl = form.getAttribute("data-validate-url");
    if (!validateUrl) return;
    const submitBtn = document.getElementById("svoz-matrix-submit-btn");
    const fields = Array.from(form.querySelectorAll(".svoz-matrix-containers"));
    const confirmedInput = document.getElementById("unknown-passport-confirmed");
    const banner = document.getElementById("svoz-unknown-fix-banner");
    const bannerNum = document.getElementById("svoz-unknown-fix-num");
    const modalBackdrop = document.getElementById("svoz-unknown-modal-backdrop");
    const modalNumEl = document.getElementById("svoz-unknown-modal-num");
    const modalConfirmText = document.getElementById("svoz-unknown-modal-confirm-text");
    const modalYes = document.getElementById("svoz-unknown-modal-yes");
    const modalNo = document.getElementById("svoz-unknown-modal-no");
    const state = new Map();
    const debounceTimers = new Map();
    let submitGateOpen = false;
    let modalResolve = null;

    function setFieldState(ta, status, messages) {
        const pk = ta.getAttribute("data-pair-pk");
        const fb = document.getElementById("svoz-container-feedback-" + pk);
        if (!fb) return;
        ta.classList.remove("is-invalid", "is-valid");
        if (status !== "needs-fix") {
            ta.classList.remove("is-needs-fix");
            fb.classList.remove("is-needs-fix");
        }
        fb.classList.remove("is-error", "is-ok", "is-pending");
        if (status === "pending") {
            fb.classList.add("is-pending");
            fb.textContent = "Kontroluji pasport…";
            return;
        }
        if (status === "error") {
            ta.classList.add("is-invalid");
            fb.classList.add("is-error");
            fb.innerHTML = messages
                .map(function (m) {
                    return '<p style="margin:0 0 4px;">' + String(m).replace(/</g, "&lt;") + "</p>";
                })
                .join("");
            return;
        }
        if (status === "needs-fix") {
            ta.classList.add("is-needs-fix");
            fb.classList.add("is-needs-fix");
            fb.textContent =
                messages && messages[0]
                    ? messages[0]
                    : "Opravte toto číslo kontejneru a odešlete znovu.";
            return;
        }
        if ((ta.value || "").trim()) {
            ta.classList.add("is-valid");
            fb.classList.add("is-ok");
            fb.textContent = "Pasport v pořádku.";
        } else {
            fb.textContent = "";
        }
    }

    function updateSubmit() {
        if (!submitBtn) return;
        let blocked = false;
        state.forEach(function (v) {
            if (v === "error" || v === "pending") blocked = true;
        });
        submitBtn.disabled = blocked;
        submitBtn.title = blocked
            ? "Opravte kontejnery s chybou pasportu (nebo počkejte na dokončení kontroly)."
            : "";
    }

    function clearNeedsFix(ta) {
        ta.classList.remove("is-needs-fix");
        const pk = ta.getAttribute("data-pair-pk");
        const fb = document.getElementById("svoz-container-feedback-" + pk);
        if (fb) fb.classList.remove("is-needs-fix");
        if (banner) banner.classList.remove("is-visible");
    }

    function markNeedsFix(ta, num) {
        setFieldState(ta, "needs-fix", [
            "Opravte číslo " + num + " — není v číselníku pasportů (nebo potvrďte při odeslání).",
        ]);
        if (banner && bannerNum) {
            bannerNum.textContent = num;
            banner.classList.add("is-visible");
        }
        try {
            ta.focus();
            ta.scrollIntoView({ behavior: "smooth", block: "center" });
        } catch (e) {}
    }

    function goLoginSessionExpired() {
        const next = window.location.pathname + window.location.search + window.location.hash;
        window.location.href =
            "/accounts/login/?next=" +
            encodeURIComponent(next || "/") +
            "&reason=idle";
    }

    function fetchValidate(ta, extraParams) {
        const pk = ta.getAttribute("data-pair-pk");
        const params = new URLSearchParams({
            pair_pk: pk,
            containers: ta.value || "",
        });
        if (extraParams) {
            Object.keys(extraParams).forEach(function (k) {
                params.set(k, extraParams[k]);
            });
        }
        return fetch(validateUrl + "?" + params.toString(), {
            headers: { "X-Requested-With": "XMLHttpRequest" },
            credentials: "same-origin",
        }).then(function (res) {
            if (res.status === 401) {
                goLoginSessionExpired();
                return Promise.reject(new Error("session"));
            }
            return res.json();
        });
    }

    function getConfirmedSet() {
        const raw = confirmedInput ? String(confirmedInput.value || "") : "";
        const set = {};
        raw.split(",").forEach(function (part) {
            const n = String(part || "").trim();
            if (n) set[n] = true;
        });
        return set;
    }

    function addConfirmedNumbers(nums) {
        if (!confirmedInput) return;
        const set = getConfirmedSet();
        (nums || []).forEach(function (n) {
            const key = String(n || "").trim();
            if (key) set[key] = true;
        });
        confirmedInput.value = Object.keys(set).join(",");
    }

    function removeConfirmedNumber(num) {
        if (!confirmedInput) return;
        const key = String(num || "").trim();
        const set = getConfirmedSet();
        delete set[key];
        confirmedInput.value = Object.keys(set).join(",");
    }

    function validateField(ta) {
        const pk = ta.getAttribute("data-pair-pk");
        const raw = (ta.value || "").trim();
        if (!raw) {
            state.set(pk, "ok");
            setFieldState(ta, "ok", []);
            updateSubmit();
            return;
        }
        state.set(pk, "pending");
        setFieldState(ta, "pending", []);
        updateSubmit();
        fetchValidate(ta)
            .then(function (data) {
                if (data.ok) {
                    // Neznámá čísla: při psaní skrytá (jen admin log na serveru).
                    state.set(pk, "ok");
                    setFieldState(ta, "ok", []);
                } else {
                    state.set(pk, "error");
                    const errs =
                        data.errors && data.errors.length
                            ? data.errors
                            : [data.error || "Kontrola pasportu selhala."];
                    setFieldState(ta, "error", errs);
                }
                updateSubmit();
            })
            .catch(function (err) {
                if (err && err.message === "session") return;
                state.set(pk, "error");
                setFieldState(ta, "error", [
                    "Kontrola pasportu se nepodařila (síť nebo server) — zkuste to znovu.",
                ]);
                updateSubmit();
            });
    }

    async function confirmUnknownNumbersForField(ta, unknowns) {
        const already = getConfirmedSet();
        const pending = (unknowns || []).filter(function (n) {
            return !already[String(n)];
        });
        if (!pending.length) return true;
        for (let i = 0; i < pending.length; i++) {
            const num = String(pending[i]);
            const ok = await showUnknownModal(num);
            if (!ok) {
                await logReject(ta, num);
                removeConfirmedNumber(num);
                markNeedsFix(ta, num);
                return false;
            }
            await logAccept(ta, num);
            addConfirmedNumbers([num]);
        }
        state.set(ta.getAttribute("data-pair-pk"), "ok");
        setFieldState(ta, "ok", []);
        updateSubmit();
        return true;
    }

    async function validateFieldOnBlur(ta) {
        const pk = ta.getAttribute("data-pair-pk");
        const raw = (ta.value || "").trim();
        if (!raw) {
            state.set(pk, "ok");
            setFieldState(ta, "ok", []);
            updateSubmit();
            return;
        }
        // Modal otevřený / právě potvrzujeme — nevolat znovu (focus z modalu).
        if (modalResolve || (modalBackdrop && !modalBackdrop.hidden)) {
            return;
        }
        state.set(pk, "pending");
        setFieldState(ta, "pending", []);
        updateSubmit();
        let data;
        try {
            data = await fetchValidate(ta);
        } catch (e) {
            if (e && e.message === "session") return;
            state.set(pk, "error");
            setFieldState(ta, "error", [
                "Kontrola pasportu se nepodařila (síť nebo server) — zkuste to znovu.",
            ]);
            updateSubmit();
            return;
        }
        if (!data.ok) {
            state.set(pk, "error");
            const errs =
                data.errors && data.errors.length
                    ? data.errors
                    : [data.error || "Kontrola pasportu selhala."];
            setFieldState(ta, "error", errs);
            updateSubmit();
            return;
        }
        state.set(pk, "ok");
        setFieldState(ta, "ok", []);
        updateSubmit();
        const unknowns = Array.isArray(data.unknown_numbers) ? data.unknown_numbers : [];
        if (unknowns.length) {
            await confirmUnknownNumbersForField(ta, unknowns);
        }
    }

    function showUnknownModal(num) {
        return new Promise(function (resolve) {
            modalResolve = resolve;
            if (modalNumEl) modalNumEl.textContent = num;
            if (modalConfirmText) {
                modalConfirmText.textContent = "Potvrďte, že zadáváte opravdu toto číslo.";
            }
            if (modalBackdrop) {
                modalBackdrop.hidden = false;
                modalBackdrop.removeAttribute("hidden");
            }
        });
    }

    function hideUnknownModal() {
        if (modalBackdrop) {
            modalBackdrop.hidden = true;
            modalBackdrop.setAttribute("hidden", "");
        }
        modalResolve = null;
    }

    if (modalYes) {
        modalYes.addEventListener("click", function () {
            const r = modalResolve;
            hideUnknownModal();
            if (r) r(true);
        });
    }
    if (modalNo) {
        modalNo.addEventListener("click", function () {
            const r = modalResolve;
            hideUnknownModal();
            if (r) r(false);
        });
    }

    function logReject(ta, num) {
        return fetchValidate(ta, {
            confirm_rejected: "1",
            rejected_number: num,
        }).catch(function () {});
    }

    function logAccept(ta, num) {
        return fetchValidate(ta, {
            confirm_accepted: "1",
            accepted_number: num,
        }).catch(function () {});
    }

    async function collectUnknownItems() {
        const items = [];
        const seen = {};
        const already = getConfirmedSet();
        for (let i = 0; i < fields.length; i++) {
            const ta = fields[i];
            if (!(ta.value || "").trim()) continue;
            let data;
            try {
                data = await fetchValidate(ta);
            } catch (e) {
                if (e && e.message === "session") {
                    return { hardError: true, message: "session" };
                }
                return {
                    hardError: true,
                    message: "Kontrola pasportu se nepodařila (síť nebo server) — zkuste to znovu.",
                };
            }
            if (!data.ok) {
                state.set(ta.getAttribute("data-pair-pk"), "error");
                const errs =
                    data.errors && data.errors.length
                        ? data.errors
                        : [data.error || "Kontrola pasportu selhala."];
                setFieldState(ta, "error", errs);
                updateSubmit();
                return { hardError: true };
            }
            const unknowns = Array.isArray(data.unknown_numbers) ? data.unknown_numbers : [];
            unknowns.forEach(function (num) {
                const key = String(num);
                if (seen[key] || already[key]) return;
                seen[key] = true;
                items.push({ ta: ta, number: key });
            });
        }
        return { hardError: false, items: items };
    }

    async function runSubmitConfirmFlow() {
        const result = await collectUnknownItems();
        if (result.hardError) return false;
        const items = result.items || [];
        if (!items.length) {
            return true;
        }
        for (let i = 0; i < items.length; i++) {
            const item = items[i];
            const ok = await showUnknownModal(item.number);
            if (!ok) {
                await logReject(item.ta, item.number);
                removeConfirmedNumber(item.number);
                markNeedsFix(item.ta, item.number);
                return false;
            }
            await logAccept(item.ta, item.number);
            addConfirmedNumbers([item.number]);
        }
        return true;
    }

    fields.forEach(function (ta) {
        const pk = ta.getAttribute("data-pair-pk");
        state.set(pk, "ok");
        function schedule() {
            clearTimeout(debounceTimers.get(pk));
            clearNeedsFix(ta);
            debounceTimers.set(
                pk,
                setTimeout(function () {
                    validateField(ta);
                }, 3350)
            );
        }
        ta.addEventListener("input", schedule);
        ta.addEventListener("blur", function () {
            clearTimeout(debounceTimers.get(pk));
            validateFieldOnBlur(ta);
        });
    });

    form.addEventListener("submit", function (e) {
        if (submitGateOpen) {
            submitGateOpen = false;
            return;
        }
        e.preventDefault();
        let blocked = false;
        state.forEach(function (v) {
            if (v === "error" || v === "pending") blocked = true;
        });
        if (blocked) return;

        runSubmitConfirmFlow().then(function (ok) {
            if (!ok) return;
            submitGateOpen = true;
            if (submitBtn) {
                submitBtn.disabled = true;
                submitBtn.setAttribute("aria-busy", "true");
                if (!submitBtn.getAttribute("data-label-orig")) {
                    submitBtn.setAttribute("data-label-orig", submitBtn.textContent || "Odeslat");
                }
                submitBtn.textContent = "Odesílám…";
            }
            if (typeof form.requestSubmit === "function") {
                form.requestSubmit(submitBtn || undefined);
            } else {
                HTMLFormElement.prototype.submit.call(form);
            }
        });
    });
})();
