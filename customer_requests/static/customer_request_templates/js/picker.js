/**
 * Výběr a aplikace šablony zákaznického požadavku na /waste-docs/customer-requests/new/.
 */
(function () {
    function readConfig() {
        const el = document.getElementById("customer-request-form-config");
        if (!el) return null;
        try {
            return JSON.parse(el.textContent || "{}");
        } catch (e) {
            return null;
        }
    }

    function waitForHooks() {
        return new Promise(function (resolve) {
            if (window.customerRequestFormHooks) {
                resolve(window.customerRequestFormHooks);
                return;
            }
            document.addEventListener(
                "customer-request-form-ready",
                function () {
                    resolve(window.customerRequestFormHooks || null);
                },
                { once: true }
            );
        });
    }

    function getCsrfToken() {
        const inp = document.querySelector('input[name="csrfmiddlewaretoken"]');
        return inp ? inp.value : "";
    }

    function setSelectValue(selectEl, value) {
        if (!selectEl || value === null || value === undefined || value === "") return;
        const v = String(value);
        const ok = Array.from(selectEl.options).some(function (o) {
            return String(o.value) === v;
        });
        if (ok) selectEl.value = v;
    }

    function setCoords(latRaw, lngRaw) {
        const latInput = document.getElementById("id_fulfillment_latitude");
        const lngInput = document.getElementById("id_fulfillment_longitude");
        const lat = parseFloat(String(latRaw || "").replace(",", "."));
        const lng = parseFloat(String(lngRaw || "").replace(",", "."));
        if (window.FulfillmentAddressField && window.FulfillmentAddressField.clearCoordInputs) {
            if (Number.isFinite(lat) && Number.isFinite(lng)) {
                if (latInput) latInput.value = lat.toFixed(7);
                if (lngInput) lngInput.value = lng.toFixed(7);
            } else {
                window.FulfillmentAddressField.clearCoordInputs(latInput, lngInput);
            }
        }
    }

    function clearRequestDates() {
        const targetDate = document.getElementById("id_target_date");
        const recurrenceUntil = document.getElementById("id_recurrence_until");
        if (targetDate) targetDate.value = "";
        if (recurrenceUntil) recurrenceUntil.value = "";
    }

    function collectRecurrenceWeekdays() {
        const checks = document.querySelectorAll('input[name="recurrence_weekdays_pick"]');
        const days = [];
        checks.forEach(function (cb) {
            if (cb.checked) days.push(String(cb.value));
        });
        return days.join(",");
    }

    function applyRecurrenceFromTemplate(row) {
        const recurringCheck = document.getElementById("id_is_recurring");
        const weekdayChecks = document.querySelectorAll('input[name="recurrence_weekdays_pick"]');
        const wantRecurring = Boolean(row && row.is_recurring);
        const wanted = new Set(
            String((row && row.recurrence_weekdays) || "")
                .split(",")
                .map(function (x) {
                    return x.trim();
                })
                .filter(Boolean)
        );
        if (recurringCheck) {
            recurringCheck.checked = wantRecurring && wanted.size > 0;
            recurringCheck.dispatchEvent(new Event("change", { bubbles: true }));
        }
        weekdayChecks.forEach(function (cb) {
            cb.checked = wantRecurring && wanted.has(String(cb.value));
        });
        if (recurringCheck) {
            recurringCheck.dispatchEvent(new Event("change", { bubbles: true }));
        }
    }

    async function fetchSubjectSnapshot(nameValue, urls) {
        const q = (nameValue || "").trim();
        if (!q || q.length < 2 || !urls || !urls.subjectSearch) return null;
        const res = await fetch(
            urls.subjectSearch + "?q=" + encodeURIComponent(q),
            { headers: { "X-Requested-With": "XMLHttpRequest" }, credentials: "same-origin" }
        );
        if (!res.ok) return null;
        const payload = await res.json();
        const rows = payload.data || [];
        return rows.length ? rows[0] : null;
    }

    async function applyTemplateRow(row, hooks, urls) {
        if (!row) return;
        const snapshot =
            (await fetchSubjectSnapshot(row.name_value, urls)) ||
            {
                name_id: row.name_id,
                name_value: row.name_value,
                label: row.name_value,
            };
        if (hooks && typeof hooks.applySubjectSnapshot === "function") {
            hooks.applySubjectSnapshot(snapshot, { preserveSideFields: true, preserveExistingWaste: true });
        } else {
            const nameLookup = document.getElementById("id_name_lookup");
            const nameHidden = document.getElementById("id_name_existing");
            if (nameLookup) nameLookup.value = row.name_value || "";
            if (nameHidden) nameHidden.value = row.name_id ? String(row.name_id) : "";
        }

        const wasteSelect = document.getElementById("id_waste_type");
        const wasteComboApi = hooks && hooks.getWasteComboApi ? hooks.getWasteComboApi() : null;
        if (row.waste_type_id) {
            if (wasteComboApi && wasteComboApi.applyPk) {
                wasteComboApi.applyPk(String(row.waste_type_id));
            } else if (wasteSelect) {
                wasteSelect.value = String(row.waste_type_id);
                wasteSelect.dispatchEvent(new Event("change", { bubbles: true }));
            }
        }

        await new Promise(function (r) {
            setTimeout(r, 80);
        });

        const suffixSelect = document.getElementById("id_suffix");
        if (suffixSelect && row.suffix_id) {
            setSelectValue(suffixSelect, row.suffix_id);
            suffixSelect.dispatchEvent(new Event("change", { bubbles: true }));
        }

        const facilityInput = document.getElementById("id_facility_address_value");
        if (facilityInput && row.facility_address_value) {
            facilityInput.value = row.facility_address_value;
        }
        const addrInput = document.getElementById("id_address_value");
        if (addrInput) {
            addrInput.value = row.address_value || "";
            addrInput.dispatchEvent(new Event("change", { bubbles: true }));
        }
        setCoords(row.fulfillment_latitude, row.fulfillment_longitude);

        const activitySelect = document.getElementById("id_activity");
        if (activitySelect && row.activity_id) {
            setSelectValue(activitySelect, row.activity_id);
            activitySelect.dispatchEvent(new Event("change", { bubbles: true }));
        }
        const vehicleKindSelect = document.getElementById("id_vehicle_kind");
        if (vehicleKindSelect && row.vehicle_kind_id) {
            setSelectValue(vehicleKindSelect, row.vehicle_kind_id);
        }
        const phoneInput = document.getElementById("id_contact_phone");
        if (phoneInput && row.contact_phone) {
            phoneInput.value = row.contact_phone;
        }
        const noteInput = document.getElementById("id_contact_note");
        if (noteInput && row.contact_note) {
            noteInput.value = row.contact_note;
        }
        const contractInput = document.getElementById("id_contract_number");
        if (contractInput && row.contract_number) {
            contractInput.value = row.contract_number;
            const contractRow = document.getElementById("customer-request-contract-row");
            if (contractRow) contractRow.style.display = "";
        }
        const requestNote = document.getElementById("id_note");
        if (requestNote && row.note) {
            requestNote.value = row.note;
        }

        if (hooks && typeof hooks.syncContractFromPair === "function") {
            hooks.syncContractFromPair();
        }
        if (hooks && typeof hooks.syncFulfillmentFromPair === "function" && !row.address_value) {
            hooks.syncFulfillmentFromPair();
        }
        applyRecurrenceFromTemplate(row);
        clearRequestDates();
        if (window.jedisRefreshZpoPairingDock) {
            window.jedisRefreshZpoPairingDock();
        }
    }

    function collectSavePayload() {
        const nameHidden = document.getElementById("id_name_existing");
        const wasteSelect = document.getElementById("id_waste_type");
        const suffixSelect = document.getElementById("id_suffix");
        const addrInput = document.getElementById("id_address_value");
        const latInput = document.getElementById("id_fulfillment_latitude");
        const lngInput = document.getElementById("id_fulfillment_longitude");
        const recurringCheck = document.getElementById("id_is_recurring");
        return {
            name_id: nameHidden ? nameHidden.value : "",
            waste_type_id: wasteSelect ? wasteSelect.value : "",
            suffix_id: suffixSelect ? suffixSelect.value : "",
            address_value: addrInput ? (addrInput.value || "").trim() : "",
            fulfillment_latitude: latInput ? latInput.value : "",
            fulfillment_longitude: lngInput ? lngInput.value : "",
            activity_id: (document.getElementById("id_activity") || {}).value || "",
            vehicle_kind_id: (document.getElementById("id_vehicle_kind") || {}).value || "",
            facility_address_value: (document.getElementById("id_facility_address_value") || {}).value || "",
            contact_phone: (document.getElementById("id_contact_phone") || {}).value || "",
            contact_note: (document.getElementById("id_contact_note") || {}).value || "",
            contract_number: (document.getElementById("id_contract_number") || {}).value || "",
            note: (document.getElementById("id_note") || {}).value || "",
            is_recurring: Boolean(recurringCheck && recurringCheck.checked),
            recurrence_weekdays: collectRecurrenceWeekdays(),
        };
    }

    async function boot() {
        const cfg = readConfig();
        const tplCfg = cfg && cfg.customerRequestTemplates;
        if (!tplCfg || !tplCfg.enabled) return;

        const picker = document.getElementById("customer-request-template-picker");
        const selectEl = document.getElementById("customer-request-template-select");
        const applyBtn = document.getElementById("customer-request-template-apply-btn");
        const saveBtn = document.getElementById("customer-request-template-save-btn");
        if (!picker || !selectEl || !applyBtn || !saveBtn) return;

        picker.hidden = false;
        let rows = [];

        async function reloadTemplates() {
            const res = await fetch(tplCfg.listUrl, {
                credentials: "same-origin",
                headers: { "X-Requested-With": "XMLHttpRequest" },
            });
            if (!res.ok) {
                rows = [];
                return;
            }
            const payload = await res.json();
            rows = payload.ok ? payload.data || [] : [];
            selectEl.innerHTML = "";
            const empty = document.createElement("option");
            empty.value = "";
            empty.textContent = "--- vyberte šablonu ---";
            selectEl.appendChild(empty);
            rows.forEach(function (row) {
                const opt = document.createElement("option");
                opt.value = String(row.id);
                opt.textContent = row.title;
                opt.title = [row.name_value, row.address_value].filter(Boolean).join(" · ");
                selectEl.appendChild(opt);
            });
        }

        applyBtn.addEventListener("click", async function () {
            const id = String(selectEl.value || "");
            if (!id) return;
            const row = rows.find(function (item) {
                return String(item.id) === id;
            });
            if (!row) return;
            const hooks = await waitForHooks();
            await applyTemplateRow(row, hooks, cfg.urls || {});
        });

        saveBtn.addEventListener("click", async function () {
            const payload = collectSavePayload();
            if (!payload.name_id || !payload.waste_type_id) {
                alert("Vyplňte subjekt a druh odpadu před uložením šablony.");
                return;
            }
            if (!payload.address_value) {
                alert("Vyplňte adresu plnění před uložením šablony.");
                return;
            }
            const title = window.prompt("Název šablony:", payload.address_value.slice(0, 80));
            if (title === null) return;
            const trimmed = (title || "").trim();
            if (!trimmed) {
                alert("Zadejte název šablony.");
                return;
            }
            payload.title = trimmed;
            const res = await fetch(tplCfg.saveUrl, {
                method: "POST",
                credentials: "same-origin",
                headers: {
                    "Content-Type": "application/json",
                    "X-CSRFToken": getCsrfToken(),
                    "X-Requested-With": "XMLHttpRequest",
                },
                body: JSON.stringify(payload),
            });
            const body = await res.json();
            if (!res.ok || !body.ok) {
                alert((body && body.error) || "Šablonu se nepodařilo uložit.");
                return;
            }
            await reloadTemplates();
            if (body.data && body.data.id) {
                selectEl.value = String(body.data.id);
            }
        });

        await reloadTemplates();
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", function () {
            void boot();
        });
    } else {
        void boot();
    }
})();
