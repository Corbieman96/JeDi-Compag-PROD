(function () {
    const form = document.querySelector(".yard-ride-form");
    if (!form) return;
    const validateUrl = form.getAttribute("data-validate-url");
    if (!validateUrl) return;
    const submitBtn = document.getElementById("yard-ride-submit-btn");
    const fields = Array.from(form.querySelectorAll(".yard-ride-container"));
    const state = new Map();
    const debounceTimers = new Map();

    function rzForPair(pk) {
        const sel = document.querySelector('.svoz-rz-select[data-pair-pk="' + pk + '"]');
        return sel ? (sel.value || "").trim() : "";
    }

    function setFieldState(input, status, messages) {
        const pk = input.getAttribute("data-pair-pk");
        const fb = document.getElementById("yard-container-feedback-" + pk);
        if (!fb) return;
        input.classList.remove("is-invalid", "is-valid");
        fb.classList.remove("is-error", "is-ok", "is-pending");
        if (status === "pending") {
            fb.classList.add("is-pending");
            fb.textContent = "Kontroluji pasport…";
            return;
        }
        if (status === "error") {
            input.classList.add("is-invalid");
            fb.classList.add("is-error");
            fb.innerHTML = messages
                .map(function (m) {
                    return '<p style="margin:0 0 4px;">' + String(m).replace(/</g, "&lt;") + "</p>";
                })
                .join("");
            return;
        }
        if ((input.value || "").trim()) {
            input.classList.add("is-valid");
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

    function validateField(input) {
        const pk = input.getAttribute("data-pair-pk");
        const raw = (input.value || "").trim();
        if (!raw) {
            state.set(pk, "ok");
            setFieldState(input, "ok", []);
            updateSubmit();
            return;
        }
        const rzId = rzForPair(pk);
        if (!rzId) {
            state.set(pk, "error");
            setFieldState(input, "error", ["Nejdříve vyberte RZ vozidla."]);
            updateSubmit();
            return;
        }
        state.set(pk, "pending");
        setFieldState(input, "pending", []);
        updateSubmit();
        const params = new URLSearchParams({
            pair_pk: pk,
            container: input.value || "",
            vehicle_rz_id: rzId,
        });
        fetch(validateUrl + "?" + params.toString(), {
            headers: { "X-Requested-With": "XMLHttpRequest" },
            credentials: "same-origin",
        })
            .then(function (res) {
                return res.json();
            })
            .then(function (data) {
                if (data.ok) {
                    state.set(pk, "ok");
                    setFieldState(input, "ok", []);
                } else {
                    state.set(pk, "error");
                    const errs =
                        data.errors && data.errors.length
                            ? data.errors
                            : [data.error || "Kontrola pasportu selhala."];
                    setFieldState(input, "error", errs);
                }
                updateSubmit();
            })
            .catch(function () {
                state.set(pk, "error");
                setFieldState(input, "error", ["Kontrola pasportu se nepodařila — zkuste to znovu."]);
                updateSubmit();
            });
    }

    fields.forEach(function (input) {
        const pk = input.getAttribute("data-pair-pk");
        state.set(pk, "ok");
        function schedule() {
            clearTimeout(debounceTimers.get(pk));
            debounceTimers.set(
                pk,
                setTimeout(function () {
                    validateField(input);
                }, 350)
            );
        }
        input.addEventListener("input", schedule);
        input.addEventListener("blur", function () {
            clearTimeout(debounceTimers.get(pk));
            validateField(input);
        });
    });

    document.querySelectorAll(".svoz-rz-select").forEach(function (sel) {
        const pairPk = sel.dataset.pairPk;
        sel.addEventListener("change", function () {
            const input = document.querySelector('.yard-ride-container[data-pair-pk="' + pairPk + '"]');
            if (input && (input.value || "").trim()) {
                clearTimeout(debounceTimers.get(pairPk));
                validateField(input);
            }
        });
    });

    form.addEventListener("submit", function (e) {
        let blocked = false;
        state.forEach(function (v) {
            if (v === "error" || v === "pending") blocked = true;
        });
        if (blocked) {
            e.preventDefault();
            return;
        }
        fields.forEach(function (input) {
            if ((input.value || "").trim() && state.get(input.getAttribute("data-pair-pk")) !== "ok") {
                e.preventDefault();
                validateField(input);
            }
        });
    });
})();
