/**
 * Logika formuláře průvodky — #jedis-pruvodka-form-config (json_script).
 */
import { normalizeLabelSearch, setSelectValue, showFieldRow } from "./utils.js";
import { bootSubjectPairsModal } from "./subject_pairs_modal.js";

export function bootPruvodkaCreateForm() {
    const cfgEl = document.getElementById("jedis-pruvodka-form-config");
    if (!cfgEl) return;
    let cfg;
    try {
        cfg = JSON.parse(cfgEl.textContent);
    } catch (e) {
        return;
    }
    const U = cfg.urls;
    const wasteTypeMeta = cfg.wasteTypeMeta || {};
    const defaultCity = cfg.defaultCity || "Česko";
    const cfgInitialFollowUpPk =
        cfg.initialFollowUpParentPk != null && cfg.initialFollowUpParentPk !== ""
            ? String(cfg.initialFollowUpParentPk)
            : "";

    function restoreInitialFollowUpParentIfNeeded() {
        if (!followUpHidden || !cfgInitialFollowUpPk) return;
        followUpHidden.value = cfgInitialFollowUpPk;
    }

    function ensureVehicleRzOptionVisible(rzId) {
        if (!vehicleRzSelect || rzId == null || rzId === "") return;
        const opt = Array.from(vehicleRzSelect.options).find(
            (o) => o.value && String(o.value) === String(rzId)
        );
        if (opt) opt.hidden = false;
    }

    /** Poslední stav z /activity-field-rules/ — zda aktuální činnost umožňuje dokončit návaznost. */
    let canCompleteFollowUpActive = false;
    let subjectOpenFollowUpsHintTimer = null;

    const activitySelect = document.getElementById("id_activity");
    const driveDateInput = document.getElementById("id_drive_date");
    const vehicleRzSelect = document.getElementById("id_vehicle_rz");
    const vehicleRzCombobox = document.getElementById("vehicle-rz-combobox");
    const vehicleRzDatalist = document.getElementById("vehicle-rz-datalist");
    const driverSelect = document.getElementById("id_driver");
    const driverCombobox = document.getElementById("driver-combobox");
    const driverDatalist = document.getElementById("driver-datalist");
    const driverHint = document.getElementById("driver-hint");
    const icoLookupInput = document.getElementById("id_ico_lookup");
    const icoLookupPlaceholderDefault = "Název firmy/F osoby (našeptávač z číselníku)";
    const icoLookupPlaceholderNitro = "Název — jen vnitropodnikové subjekty";
    const icoSelect = document.getElementById("id_ico");
    const nameSelect = document.getElementById("id_name");
    const fulfillmentAddressInput = document.getElementById("id_fulfillment_address_value");
    const pairAddressSelect = document.getElementById("pruvodka-pair-address-select");
    const pairAddressSelectWrap = document.getElementById("pruvodka-pair-address-select-wrap");
    const facilityAddressDisplay = document.getElementById("id_facility_address_display");
    const contactPhoneInput = document.getElementById("id_contact_phone");
    const contractNumberInput = document.getElementById("id_contract_number");
    const contactNoteInput = document.getElementById("id_contact_note");
    let lastSubjectPairHints = [];
    let lastCentralFulfillmentAddress = "";
    let fulfillmentAddressMode = "auto";
    let fulfillmentAddressProgrammatic = false;
    let pairAddressSelectProgrammatic = false;
    let pairAddressPinnedByUser = false;
    let pairAddressPinWasteId = "";
    /** Options z CR/edit prefillu — merge se syncem, ať late updateSuffixOptions neschová combo. */
    let lastPrefillAddressOptions = [];
    // Při submitu vypnout preferenční sync adresy (RZ change / applySubjectHit by jinak přepsal výběr).
    let fulfillmentSyncSuspended = false;
    let contactNoteManual = Boolean(cfg.isEdit);
    let contactNoteTypedByUser = false;
    let editWasteContextChanged = false;
    const editInitialWaste = cfg.isEdit
        ? {
              wasteTypeId: "",
              suffixId: "",
          }
        : null;
    let activeSubjectProfileId =
        cfg.initialSubjectProfileId != null && cfg.initialSubjectProfileId !== ""
            ? parseInt(String(cfg.initialSubjectProfileId), 10)
            : null;
    if (Number.isNaN(activeSubjectProfileId)) {
        activeSubjectProfileId = null;
    }

    function syncFulfillmentMapLink() {
        const link = document.getElementById("jedis-fulfillment-map-link");
        const input = document.getElementById("id_fulfillment_address_value");
        if (!link || !input) return;
        const q = (input.value || "").trim();
        if (!q) {
            link.hidden = true;
            link.removeAttribute("href");
            return;
        }
        link.href = `https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(q)}`;
        link.hidden = false;
    }

    function normalizePairHint(h) {
        if (!h) return null;
        const yardKindId = h.yard_vehicle_kind_id || h.vehicle_kind_id || null;
        let kindIds = Array.isArray(h.yard_vehicle_kind_ids) ? h.yard_vehicle_kind_ids.map(String) : [];
        if (!kindIds.length && yardKindId) {
            kindIds = [String(yardKindId)];
        }
        return {
            waste_type_id: h.waste_type_id,
            suffix_id: h.suffix_id,
            contract_number: h.contract_number || "",
            ride_note: h.ride_note || "",
            fulfillment_address_value: h.fulfillment_address_value || "",
            own_fulfillment_address_value: h.own_fulfillment_address_value || "",
            yard_vehicle_kind_id: yardKindId,
            yard_vehicle_kind_ids: kindIds,
            covering_kind_ids: Array.isArray(h.covering_kind_ids) ? h.covering_kind_ids.map(String) : kindIds.slice(),
            vehicle_kind_constraint_hint: h.vehicle_kind_constraint_hint || "",
            yard_vehicle_kind_display: h.yard_vehicle_kind_display || "",
            activity_id: h.activity_id,
            vehicle_kind_id: h.vehicle_kind_id || yardKindId,
        };
    }

    function normalizePairHints(rows) {
        return (Array.isArray(rows) ? rows : [])
            .map((h) => normalizePairHint(h))
            .filter(Boolean);
    }

    function setFulfillmentAddressValue(value) {
        if (!fulfillmentAddressInput) return;
        fulfillmentAddressProgrammatic = true;
        fulfillmentAddressInput.value = value || "";
        fulfillmentAddressProgrammatic = false;
        syncFulfillmentMapLink();
    }

    function pickSubjectPairHintsForContext() {
        if (!wasteTypeSelect || !suffixSelect) return [];
        const w = (wasteTypeSelect.value || "").trim();
        const s = (suffixSelect.value || "").trim();
        if (!w || !s) return [];
        let rows = lastSubjectPairHints.filter(
            (p) => String(p.waste_type_id) === String(w) && String(p.suffix_id) === String(s)
        );
        const rzId = vehicleRzSelect ? (vehicleRzSelect.value || "").trim() : "";
        if (rzId && vehicleRzMeta[String(rzId)]) {
            const kindIds = (vehicleRzMeta[String(rzId)].kind_ids || []).map(String);
            if (kindIds.length) {
                const filtered = rows.filter((p) => {
                    const pairKinds = (p.yard_vehicle_kind_ids || []).map(String);
                    if (!pairKinds.length && p.yard_vehicle_kind_id) {
                        pairKinds.push(String(p.yard_vehicle_kind_id));
                    }
                    return pairKinds.some((k) => kindIds.includes(k));
                });
                if (filtered.length) {
                    rows = filtered;
                }
            }
        }
        return rows;
    }

    function pairHintCandidatesForFulfillment() {
        // Nabídka adres = jako u požadavku: odpad (+ koncovka). VK jen v preferenci defaultu.
        if (!wasteTypeSelect) return [];
        const w = (wasteTypeSelect.value || "").trim();
        if (!w) return [];
        let rows = lastSubjectPairHints.filter(
            (p) => String(p.waste_type_id) === String(w)
        );
        const s = suffixSelect ? (suffixSelect.value || "").trim() : "";
        if (s) {
            const byBoth = rows.filter((p) => String(p.suffix_id) === String(s));
            if (byBoth.length) rows = byBoth;
        }
        return rows;
    }

    function pairHintOwnAddress(hint) {
        return hint && hint.own_fulfillment_address_value
            ? String(hint.own_fulfillment_address_value).trim()
            : "";
    }

    function pairHintKindIds(hint) {
        const ids = Array.isArray(hint && hint.yard_vehicle_kind_ids)
            ? hint.yard_vehicle_kind_ids.map(String)
            : [];
        if (!ids.length && hint && hint.yard_vehicle_kind_id) {
            ids.push(String(hint.yard_vehicle_kind_id));
        }
        return ids;
    }

    function pickLastPairHintForFulfillment(matches) {
        if (!matches.length) return null;
        let rows = matches;
        const vk = getRequiredPairVehicleKindId();
        if (vk) {
            const byVk = rows.filter((p) => pairHintKindIds(p).includes(vk));
            if (byVk.length) rows = byVk;
        }
        const withOwn = rows.filter((p) => pairHintOwnAddress(p));
        if (withOwn.length) return withOwn[withOwn.length - 1];
        return rows[rows.length - 1];
    }

    function pairHintResolvedAddress(hint) {
        const own = pairHintOwnAddress(hint);
        if (own) return own;
        if (hint && hint.fulfillment_address_value) {
            const resolved = String(hint.fulfillment_address_value).trim();
            if (resolved) return resolved;
        }
        return lastCentralFulfillmentAddress || "";
    }

    function hidePairAddressSelect() {
        if (pairAddressSelectWrap) pairAddressSelectWrap.style.display = "none";
        if (pairAddressSelect) {
            pairAddressSelectProgrammatic = true;
            pairAddressSelect.innerHTML = "";
            pairAddressSelectProgrammatic = false;
        }
    }

    function buildPairAddressOptions(candidates) {
        const seen = {};
        const options = [];
        (candidates || []).forEach((p) => {
            const addr = pairHintResolvedAddress(p);
            if (!addr || seen[addr]) return;
            seen[addr] = true;
            const kinds = String((p && p.yard_vehicle_kind_display) || "").trim();
            const label = kinds ? kinds + " — " + addr : addr;
            options.push({
                value: addr,
                label: label,
                title: addr,
            });
        });
        return options;
    }

    function fillPairAddressSelect(options, selectedValue) {
        if (!pairAddressSelect) return;
        pairAddressSelectProgrammatic = true;
        try {
            pairAddressSelect.innerHTML = "";
            const empty = document.createElement("option");
            empty.value = "";
            empty.textContent = "— vyberte adresu plnění —";
            empty.title = "Vyberte příslušnou adresu plnění";
            pairAddressSelect.appendChild(empty);
            (options || []).forEach((row) => {
                const opt = document.createElement("option");
                opt.value = row.value;
                opt.textContent = row.label;
                opt.title = row.title || row.value;
                pairAddressSelect.appendChild(opt);
            });
            const chosen = (selectedValue || "").trim();
            if (chosen && options.some((o) => o.value === chosen)) {
                pairAddressSelect.value = chosen;
            } else {
                pairAddressSelect.value = "";
            }
        } finally {
            pairAddressSelectProgrammatic = false;
        }
    }

    function applyPrefillAddressOptions(rawOptions, preferredValue) {
        const options = (Array.isArray(rawOptions) ? rawOptions : [])
            .map((row) => ({
                value: String((row && row.value) || "").trim(),
                label: String((row && (row.label || row.value)) || "").trim(),
                title: String((row && (row.title || row.value)) || "").trim(),
            }))
            .filter((row) => row.value);
        if (options.length < 2) {
            lastPrefillAddressOptions = [];
            hidePairAddressSelect();
            return false;
        }
        lastPrefillAddressOptions = options.slice();
        const preferred = (preferredValue || "").trim();
        if (pairAddressSelectWrap) pairAddressSelectWrap.style.display = "";
        fillPairAddressSelect(options, preferred);
        const wasteId = wasteTypeSelect ? String(wasteTypeSelect.value || "") : "";
        pairAddressPinnedByUser = Boolean(preferred);
        pairAddressPinWasteId = wasteId;
        if (preferred) {
            fulfillmentAddressMode = "manual";
            setFulfillmentAddressValue(preferred);
        } else {
            fulfillmentAddressMode = "auto";
            setFulfillmentAddressValue("");
        }
        return true;
    }

    function mergeFulfillmentAddressOptions(pairOptions) {
        const seen = {};
        const out = [];
        function add(row) {
            const value = String((row && row.value) || "").trim();
            if (!value || seen[value]) return;
            seen[value] = true;
            out.push({
                value: value,
                label: String((row && (row.label || row.value)) || value).trim() || value,
                title: String((row && (row.title || row.value)) || value).trim() || value,
            });
        }
        (pairOptions || []).forEach(add);
        (lastPrefillAddressOptions || []).forEach(add);
        const currentAddr = fulfillmentAddressInput
            ? String(fulfillmentAddressInput.value || "").trim()
            : "";
        const facilityAddr = facilityAddressDisplay
            ? String(facilityAddressDisplay.value || "").trim()
            : "";
        const currentIsFacility =
            Boolean(currentAddr) && Boolean(facilityAddr) && currentAddr === facilityAddr;
        if (currentAddr && !currentIsFacility) {
            add({ value: currentAddr, label: currentAddr, title: currentAddr });
        }
        return out;
    }

    function syncFulfillmentFromSubjectPair() {
        if (fulfillmentSyncSuspended) return;
        if (!fulfillmentAddressInput || !wasteTypeSelect || !suffixSelect) return;
        const addrRow = document.querySelector('[data-field-key="fulfillment_address"]');
        if (addrRow && addrRow.style.display === "none") {
            hidePairAddressSelect();
            return;
        }
        const w = (wasteTypeSelect.value || "").trim();
        if (!w) {
            lastPrefillAddressOptions = [];
            hidePairAddressSelect();
            pairAddressPinnedByUser = false;
            pairAddressPinWasteId = "";
            if (fulfillmentAddressMode !== "manual" && lastCentralFulfillmentAddress) {
                setFulfillmentAddressValue(lastCentralFulfillmentAddress);
            }
            return;
        }
        const candidates = pairHintCandidatesForFulfillment();
        const options = mergeFulfillmentAddressOptions(buildPairAddressOptions(candidates));
        if (options.length < 2) {
            hidePairAddressSelect();
            pairAddressPinnedByUser = false;
            pairAddressPinWasteId = "";
            if (fulfillmentAddressMode === "manual") return;
            const match = pickLastPairHintForFulfillment(candidates);
            const addr =
                pairHintResolvedAddress(match) || lastCentralFulfillmentAddress || "";
            if (addr) {
                setFulfillmentAddressValue(addr);
            }
            return;
        }
        if (pairAddressSelectWrap) pairAddressSelectWrap.style.display = "";
        const currentAddr = String(fulfillmentAddressInput.value || "").trim();
        const facilityAddr = facilityAddressDisplay
            ? String(facilityAddressDisplay.value || "").trim()
            : "";
        const currentIsFacility =
            Boolean(currentAddr) && Boolean(facilityAddr) && currentAddr === facilityAddr;
        const inOptions = Boolean(currentAddr && options.some((o) => o.value === currentAddr));
        // Provozovna mimo párové options ≠ „uživatel chtěl tuto adresu“ (edit prefill fallback).
        const userKept =
            Boolean(currentAddr) &&
            !currentIsFacility &&
            (fulfillmentAddressMode === "manual" || pairAddressPinnedByUser);
        let chosen = "";
        if (inOptions) {
            // Shoda s párovou adresou — ponechat.
            chosen = currentAddr;
            pairAddressPinnedByUser = true;
            pairAddressPinWasteId = w;
            fulfillmentAddressMode = "manual";
        } else if (userKept && currentAddr) {
            // Ruční / pin mimo seznam options — nenašilovat.
            fillPairAddressSelect(options, "");
            return;
        } else {
            // Prázdné NEBO auto/facility mimo options → preferovaná z páru.
            const preferred = pickLastPairHintForFulfillment(candidates);
            chosen =
                pairHintResolvedAddress(preferred) ||
                (options[0] && options[0].value) ||
                "";
            if (chosen) {
                pairAddressPinnedByUser = true;
                pairAddressPinWasteId = w;
                fulfillmentAddressMode = "manual";
            } else {
                pairAddressPinnedByUser = false;
                pairAddressPinWasteId = "";
            }
        }
        fillPairAddressSelect(options, chosen);
        if (chosen) {
            setFulfillmentAddressValue(chosen);
        }
    }

    function syncContractFromSubjectPair() {
        if (!contractNumberInput || !wasteTypeSelect || !suffixSelect) return;
        const cnRow = contractNumberInput.closest('[data-field-key="contract_number"]');
        if (cnRow && cnRow.style.display === "none") {
            return;
        }
        const w = (wasteTypeSelect.value || "").trim();
        const s = (suffixSelect.value || "").trim();
        if (!w || !s || !lastSubjectPairHints.length) {
            contractNumberInput.value = "";
            return;
        }
        const row = lastSubjectPairHints.find(
            (p) => String(p.waste_type_id) === String(w) && String(p.suffix_id) === String(s)
        );
        contractNumberInput.value = row && row.contract_number ? row.contract_number : "";
    }

    function syncRideNoteFromSubjectPair() {
        if (!contactNoteInput || contactNoteTypedByUser) return;
        const noteRow = contactNoteInput.closest('[data-field-key="contact_note"]');
        if (noteRow && noteRow.style.display === "none") {
            return;
        }
        if (cfg.isEdit && !editWasteContextChanged) {
            return;
        }
        const w = wasteTypeSelect ? (wasteTypeSelect.value || "").trim() : "";
        const s = suffixSelect ? (suffixSelect.value || "").trim() : "";
        if (!w || !s || !lastSubjectPairHints.length) {
            return;
        }
        const row = lastSubjectPairHints.find(
            (p) => String(p.waste_type_id) === String(w) && String(p.suffix_id) === String(s)
        );
        const note = row && row.ride_note ? String(row.ride_note).trim() : "";
        if (note) {
            contactNoteInput.value = note;
        }
    }

    function markEditWasteContextIfChanged() {
        if (!cfg.isEdit || !editInitialWaste) return;
        const w = wasteTypeSelect ? (wasteTypeSelect.value || "").trim() : "";
        const s = suffixSelect ? (suffixSelect.value || "").trim() : "";
        if (w !== editInitialWaste.wasteTypeId || s !== editInitialWaste.suffixId) {
            editWasteContextChanged = true;
        }
    }
    const datalist = document.getElementById("ico-lookup-list");
    const wasteTypeCombobox = document.getElementById("waste-type-combobox");
    const wasteTypeDatalist = document.getElementById("waste-type-datalist");
    const wasteTypeSelect = document.getElementById("id_waste_type");
    const wasteTypeClearBtn = document.getElementById("waste-type-clear");
    const wasteCodeDisplay = document.getElementById("id_waste_code_display");
    const wasteCategoryDisplay = document.getElementById("id_waste_category_display");
    const suffixSelect = document.getElementById("id_suffix");
    const suffixFilterNote = document.getElementById("suffix-filter-note");
    const followUpPick = document.getElementById("follow-up-pick");
    const skipFollowRow = document.querySelector('[data-field-key="skip_follow_up_row"]');
    const followPickRow = document.querySelector('[data-field-key="follow_up_pick_row"]');
    const followUpHidden = document.getElementById("id_follow_up_parent");
    const followUpActivityHint = document.getElementById("jedis-follow-up-activity-hint");
    const rideTemplateSelect = document.getElementById("ride-template-select");
    const rideTemplateApplyBtn = document.getElementById("ride-template-apply-btn");
    const nameHiddenInput = document.getElementById("id_name");
    let followUpPrefillById = {};
    let lastActivityZpoRule = null;

    function syncFollowUpActivityHint() {
        if (!followUpActivityHint || !followUpHidden) return;
        const hasParent = String(followUpHidden.value || "").trim() !== "";
        followUpActivityHint.style.display = hasParent ? "block" : "none";
    }

    async function applyActivityRules(activityId) {
        const params = new URLSearchParams();
        if (activityId) params.set("activity_id", activityId);
        let data = { rules: {}, expects_follow_up: false, can_complete_follow_up: false };
        try {
            const res = await fetch(`${U.activityFieldRules}?${params.toString()}`);
            data = await res.json();
        } catch (e) {}
        canCompleteFollowUpActive = Boolean(data.can_complete_follow_up);
        const rules = data.rules || {};
        const eff = (k) => rules[k] || "required";

        [
            "driver",
            "vehicle_rz",
            "container_1",
            "container_2",
            "contact_note",
            "name",
            "fulfillment_address",
            "contact_phone",
            "contract_number",
            "waste_type",
            "suffix",
        ].forEach((k) => {
            showFieldRow(k, eff(k));
        });
        showFieldRow("container_passport", eff("container_1"));

        if (eff("driver") === "off") {
            if (driverSelect) driverSelect.value = "";
            if (driverCombobox) driverCombobox.value = "";
            if (driverHint) driverHint.textContent = "";
            applyRzFilterByDriver(null);
        }
        if (driverSelect) {
            const driverRequired = !cfg.isEdit && eff("driver") !== "off";
            driverSelect.required = driverRequired;
            if (driverCombobox) driverCombobox.required = driverRequired;
        }
        if (eff("vehicle_rz") === "off") {
            if (vehicleRzSelect) {
                vehicleRzSelect.value = "";
                vehicleRzSelect.selectedIndex = 0;
            }
            if (vehicleRzCombobox) vehicleRzCombobox.value = "";
            if (vehicleRzDatalist) {
                vehicleRzDatalistLabelsKey = "";
                vehicleRzDatalist.innerHTML = "";
            }
            const passportSelectRzOff = document.getElementById("id_container_passport");
            if (passportSelectRzOff) {
                passportSelectRzOff.value = "";
                passportSelectRzOff.selectedIndex = 0;
            }
            if (window.jedisRefreshZpoPairingDock) window.jedisRefreshZpoPairingDock();
        }
        const c1 = document.getElementById("id_container_number");
        if (eff("container_1") === "off" && c1) {
            c1.value = "";
            const passportSelectC1Off = document.getElementById("id_container_passport");
            if (passportSelectC1Off) {
                passportSelectC1Off.value = "";
                passportSelectC1Off.selectedIndex = 0;
            }
        }
        const c2 = document.getElementById("id_container_number_2");
        if (eff("container_2") === "off" && c2) {
            c2.value = "";
        }
        if (eff("contact_phone") === "off" && contactPhoneInput) {
            contactPhoneInput.value = "";
        }
        if (eff("contract_number") === "off" && contractNumberInput) {
            contractNumberInput.value = "";
        }
        if (eff("contact_note") === "off" && contactNoteInput) {
            contactNoteInput.value = "";
        }

        const zpoDock = document.getElementById("zpo-pairing-dock");
        const zpoRule = rules.zpo === "off" ? "off" : "on";
        if (zpoDock) {
            if (rules.zpo === "off") {
                zpoDock.dataset.jedisActivityZpoOff = "1";
                zpoDock.style.setProperty("display", "none", "important");
                zpoDock.classList.remove("is-visible");
            } else {
                delete zpoDock.dataset.jedisActivityZpoOff;
                zpoDock.style.removeProperty("display");
            }
            if (lastActivityZpoRule !== null && lastActivityZpoRule !== zpoRule) {
                if (window.jedisRefreshZpoPairingDock) window.jedisRefreshZpoPairingDock();
            }
        }
        lastActivityZpoRule = zpoRule;
        if (rules.suffix === "off" && suffixSelect) {
            suffixSelect.value = "";
        }
        if (rules.fulfillment_address === "off" && fulfillmentAddressInput) {
            fulfillmentAddressMode = "auto";
            setFulfillmentAddressValue("");
        } else if (eff("fulfillment_address") !== "off" && fulfillmentAddressInput) {
            const curFul = (fulfillmentAddressInput.value || "").trim();
            // Nikdy neplnit plnění z provozovny — jen centrální adresa plnění subjektu.
            if (!curFul && fulfillmentAddressMode === "auto" && lastCentralFulfillmentAddress) {
                setFulfillmentAddressValue(lastCentralFulfillmentAddress);
            }
        }
        if (rules.waste_type === "off" && wasteTypeSelect) {
            wasteTypeSelect.value = "";
            if (wasteTypeCombobox) wasteTypeCombobox.value = "";
            if (wasteCodeDisplay) wasteCodeDisplay.value = "";
            if (wasteCategoryDisplay) wasteCategoryDisplay.value = "";
        }
        if (skipFollowRow) {
            skipFollowRow.style.display = data.expects_follow_up ? "" : "none";
        }
        if (followPickRow) {
            followPickRow.style.display = data.can_complete_follow_up ? "" : "none";
        }
        if (!data.can_complete_follow_up && followUpHidden && !cfgInitialFollowUpPk) {
            followUpHidden.value = "";
        }
        if (icoLookupInput) {
            icoLookupInput.placeholder = data.require_nitropodnikovy_subjekt
                ? icoLookupPlaceholderNitro
                : icoLookupPlaceholderDefault;
        }
        if (followUpPick && data.can_complete_follow_up && activityId) {
            await refillFollowUpCandidates(activityId);
        } else if (followUpPick) {
            followUpPick.innerHTML = "";
            const opt0 = document.createElement("option");
            opt0.value = "";
            opt0.textContent = "— nová jízda bez vazby na 1. část —";
            followUpPick.appendChild(opt0);
            followUpPick.value = "";
            if (followUpHidden && !cfgInitialFollowUpPk) {
                followUpHidden.value = "";
            }
        }

        restoreInitialFollowUpParentIfNeeded();
        await updateSuffixOptions({ skipYardStandaloneSync: true });
        syncFulfillmentMapLink();
        syncFollowUpActivityHint();
        if (!data.can_complete_follow_up) {
            clearSubjectOpenFollowUpsHint();
        } else {
            scheduleSubjectOpenFollowUpsHint();
        }
    }

    async function refillFollowUpCandidates(activityId) {
        if (!followUpPick || !activityId) return;
        const params = new URLSearchParams({ activity_id: String(activityId) });
        if (cfg.isEdit) {
            params.set("include_closed", "1");
            if (cfg.editItemPk != null && cfg.editItemPk !== "") {
                params.set("edit_item_id", String(cfg.editItemPk));
            }
        }
        const selectedNameId = nameHiddenInput ? String(nameHiddenInput.value || "").trim() : "";
        if (selectedNameId) {
            params.set("name_id", selectedNameId);
        }
        const res = await fetch(`${U.followUpCandidates}?${params.toString()}`);
        const data = await res.json();
        const current = followUpHidden ? String(followUpHidden.value || "") : "";
        followUpPick.innerHTML = "";
        followUpPrefillById = {};
        const opt0 = document.createElement("option");
        opt0.value = "";
        opt0.textContent = "— nová jízda bez vazby na 1. část —";
        followUpPick.appendChild(opt0);
        (data.candidates || []).forEach((c) => {
            const o = document.createElement("option");
            o.value = String(c.pk);
            o.textContent = String(c.label || "");
            followUpPick.appendChild(o);
            followUpPrefillById[String(c.pk)] = c.prefill || null;
        });
        if (current && [...followUpPick.options].some((o) => o.value === current)) {
            followUpPick.value = current;
        } else if (cfgInitialFollowUpPk && current === cfgInitialFollowUpPk) {
            restoreInitialFollowUpParentIfNeeded();
        } else {
            followUpPick.value = "";
            if (followUpHidden && !cfgInitialFollowUpPk) {
                followUpHidden.value = "";
            }
        }
        syncFollowUpActivityHint();
    }

    function clearSubjectOpenFollowUpsHint() {
        const hintEl = document.getElementById("jedis-subject-open-followups-hint");
        if (!hintEl) return;
        hintEl.innerHTML = "";
        hintEl.hidden = true;
    }

    async function fetchSubjectOpenFollowUpsHint(nameId) {
        const hintEl = document.getElementById("jedis-subject-open-followups-hint");
        if (!hintEl || !U.subjectOpenFollowUps) return;
        if (!canCompleteFollowUpActive) {
            clearSubjectOpenFollowUpsHint();
            return;
        }
        if (!nameId) {
            clearSubjectOpenFollowUpsHint();
            return;
        }
        try {
            const params = new URLSearchParams({ name_id: String(nameId) });
            const activityId = activitySelect ? String(activitySelect.value || "").trim() : "";
            if (activityId) {
                params.set("activity_id", activityId);
            }
            const res = await fetch(`${U.subjectOpenFollowUps}?${params.toString()}`);
            const data = await res.json();
            const items = Array.isArray(data.items) ? data.items : [];
            if (!items.length) {
                hintEl.innerHTML = "";
                hintEl.hidden = true;
                return;
            }
            const parts = [
                "<strong>U tohoto subjektu jsou neuzavřené návaznosti:</strong> ",
            ];
            items.forEach((it) => {
                const url = (it.detail_url || "#").replace(/"/g, "&quot;");
                const act = (it.activity_name || "—").replace(/</g, "&lt;");
                const dt = (it.drive_date || "—").replace(/</g, "&lt;");
                parts.push(
                    `<a href="${url}">#${String(it.pk)}</a> <span style="white-space:nowrap;">(${act}, ${dt})</span> `
                );
            });
            if (data.has_more) {
                parts.push("… ");
            }
            parts.push(
                "— při zakládání 2. části propojte správný záznam v „Dokončit otevřenou návaznost“."
            );
            hintEl.innerHTML = parts.join("");
            hintEl.hidden = false;
        } catch (e) {
            hintEl.innerHTML = "";
            hintEl.hidden = true;
        }
    }

    function scheduleSubjectOpenFollowUpsHint() {
        if (subjectOpenFollowUpsHintTimer) {
            clearTimeout(subjectOpenFollowUpsHintTimer);
            subjectOpenFollowUpsHintTimer = null;
        }
        if (!canCompleteFollowUpActive) {
            clearSubjectOpenFollowUpsHint();
            return;
        }
        const nameId = nameHiddenInput ? String(nameHiddenInput.value || "").trim() : "";
        if (!nameId) {
            clearSubjectOpenFollowUpsHint();
            return;
        }
        subjectOpenFollowUpsHintTimer = setTimeout(() => {
            subjectOpenFollowUpsHintTimer = null;
            void fetchSubjectOpenFollowUpsHint(nameId);
        }, 300);
    }

    async function maybeRefreshFollowUpAfterSubject() {
        const activityId = activitySelect ? String(activitySelect.value || "").trim() : "";
        if (!activityId || !canCompleteFollowUpActive || !followUpPick) {
            return;
        }
        await refillFollowUpCandidates(activityId);
        if (cfg.isEdit) {
            return;
        }
        const realOpts = [...followUpPick.options].filter((o) => o.value);
        if (realOpts.length !== 1) {
            return;
        }
        const onlyVal = realOpts[0].value;
        const prevHidden = followUpHidden ? String(followUpHidden.value || "") : "";
        followUpPick.value = onlyVal;
        if (followUpHidden) {
            followUpHidden.value = onlyVal;
        }
        const pre = followUpPrefillById[onlyVal];
        if (pre && prevHidden !== onlyVal) {
            await applyFollowUpPrefill(pre);
            if (followUpHidden) {
                followUpHidden.value = onlyVal;
            }
        }
        syncFollowUpActivityHint();
    }

    async function onSubjectStableChange() {
        await maybeRefreshFollowUpAfterSubject();
        scheduleSubjectOpenFollowUpsHint();
    }

    if (followUpPick && followUpHidden) {
        followUpPick.addEventListener("change", async () => {
            followUpHidden.value = followUpPick.value || "";
            if (!cfg.isEdit && followUpHidden.value && followUpPrefillById[followUpHidden.value]) {
                await applyFollowUpPrefill(followUpPrefillById[followUpHidden.value]);
                followUpHidden.value = followUpPick.value || "";
            }
            syncFollowUpActivityHint();
        });
    }

    const icoLookupCreateHint = document.getElementById("jedis-ico-lookup-create-hint");
    let subjectSearchSeq = 0;

    function setIcoLookupCreateHint(show) {
        if (!icoLookupCreateHint) return;
        if (show) {
            icoLookupCreateHint.removeAttribute("hidden");
        } else {
            icoLookupCreateHint.setAttribute("hidden", "");
        }
    }

    let subjectRows = [];
    /** Všichni řidiči pro aktuální činnost (pro výběr a vyhodnocení textu). */
    let driverRowsFull = [];
    let driverMapFull = {};
    /** RZ pro aktuální činnost (řádky z API; podle řidiče se skrývají nepovolené option). */
    let vehicleRzRowsFull = [];
    let vehicleRzMapFull = {};
    let vehicleRzMeta = {};
    let vehicleRzDatalistLabelsKey = "";
    let rideTemplateRows = [];

    function getRequiredPairVehicleKindId() {
        const p = cfg.customerRequestPrefill || cfg.yardHazardPrefill || cfg.svozPrefill;
        if (p && p.required_vehicle_kind_id != null && p.required_vehicle_kind_id !== "") {
            return String(p.required_vehicle_kind_id);
        }
        const ys = cfg.yardStandalone;
        if (ys && ys.active && wasteTypeSelect && suffixSelect) {
            const w = String(wasteTypeSelect.value || "");
            const s = String(suffixSelect.value || "");
            if (!w || !s || !Array.isArray(ys.pairHints)) return "";
            const row = ys.pairHints.find(
                (h) => String(h.waste_type_id) === w && String(h.suffix_id) === s
            );
            if (row && row.vehicle_kind_id != null && row.vehicle_kind_id !== "") {
                return String(row.vehicle_kind_id);
            }
        }
        return "";
    }

    function getCoveringKindIds() {
        const prefill = cfg.customerRequestPrefill || cfg.yardHazardPrefill || cfg.svozPrefill;
        if (prefill && Array.isArray(prefill.covering_kind_ids) && prefill.covering_kind_ids.length) {
            return prefill.covering_kind_ids.map(String);
        }
        const w = wasteTypeSelect ? String(wasteTypeSelect.value || "") : "";
        const s = suffixSelect ? String(suffixSelect.value || "") : "";
        if (w && s) {
            const hints = pickSubjectPairHintsForContext();
            if (hints.length) {
                const union = new Set();
                hints.forEach((h) => {
                    (h.covering_kind_ids || []).forEach((id) => union.add(String(id)));
                });
                if (union.size) return Array.from(union);
            }
            const ys = cfg.yardStandalone;
            if (ys && ys.active && Array.isArray(ys.pairHints)) {
                const row = ys.pairHints.find(
                    (h) => String(h.waste_type_id) === w && String(h.suffix_id) === s
                );
                if (row && Array.isArray(row.covering_kind_ids) && row.covering_kind_ids.length) {
                    return row.covering_kind_ids.map(String);
                }
            }
        }
        const req = getRequiredPairVehicleKindId();
        return req ? [req] : [];
    }

    function syncVehicleKindConstraintHint() {
        const el = document.getElementById("jedis-vehicle-kind-constraint-hint");
        if (!el) return;
        let hint = "";
        const prefill = cfg.customerRequestPrefill || cfg.yardHazardPrefill || cfg.svozPrefill;
        if (prefill && prefill.vehicle_kind_constraint_hint) {
            hint = String(prefill.vehicle_kind_constraint_hint);
        }
        if (!hint && wasteTypeSelect && suffixSelect) {
            const hints = pickSubjectPairHintsForContext();
            const withText = hints.find((h) => h.vehicle_kind_constraint_hint);
            if (withText) hint = String(withText.vehicle_kind_constraint_hint);
        }
        if (hint) {
            el.textContent = hint;
            el.removeAttribute("hidden");
        } else {
            el.textContent = "";
            el.setAttribute("hidden", "");
        }
    }

    function hiddenByRequiredVehicleKind(optVal) {
        const covering = getCoveringKindIds();
        if (!covering.length || !optVal) return false;
        const meta = vehicleRzMeta[String(optVal)] || { kind_ids: [] };
        const ids = (meta.kind_ids || []).map((x) => String(x));
        return !ids.some((id) => covering.includes(id));
    }

    /** Po filtrování řidičem: omezení RZ podle druhu vozidla (úkol svozu nebo řádek F/P u průvodky z dvora). */
    function applySvozOverlayToRzHidden() {
        if (!vehicleRzSelect || !getCoveringKindIds().length) return;
        Array.from(vehicleRzSelect.options).forEach((opt) => {
            if (!opt.value) return;
            const hidden = hiddenByRequiredVehicleKind(opt.value);
            opt.hidden = hidden;
            if (hidden) {
                const meta = vehicleRzMeta[String(opt.value)] || {};
                const kinds = (meta.kind_ids || []).join(", ");
                opt.title = kinds
                    ? "RZ neodpovídá druhu vozidla u řádku matice (F/P)."
                    : "";
            } else {
                opt.removeAttribute("title");
            }
        });
        syncVehicleKindConstraintHint();
    }

    function visibleVehicleRzRows() {
        if (!vehicleRzSelect) return [];
        return vehicleRzRowsFull.filter((row) => {
            const opt = Array.from(vehicleRzSelect.options).find((o) => String(o.value) === String(row.id));
            return opt && !opt.hidden;
        });
    }

    function autoSelectVehicleRzByRequiredKind() {
        if (!vehicleRzSelect || !getCoveringKindIds().length) return;
        if (vehicleRzSelect.value) return;
        const covering = getCoveringKindIds();
        const req = getRequiredPairVehicleKindId();
        const rows = visibleVehicleRzRows();
        let pick = null;
        if (req) {
            pick = rows.find((row) => (row.kind_ids || []).map(String).includes(String(req)));
        }
        if (!pick) {
            pick = rows.find((row) =>
                (row.kind_ids || []).map(String).some((id) => covering.includes(id))
            );
        }
        if (!pick) pick = rows[0];
        if (!pick) return;
        vehicleRzSelect.value = String(pick.id);
        if (vehicleRzCombobox) vehicleRzCombobox.value = pick.label;
        afterVehicleRzFilterChanged();
    }

    function syncVehicleRzComboboxFromSelect() {
        if (!vehicleRzCombobox || !vehicleRzSelect) return;
        const v = vehicleRzSelect.value;
        if (!v) {
            vehicleRzCombobox.value = "";
            return;
        }
        const opt = Array.from(vehicleRzSelect.options).find((o) => String(o.value) === String(v));
        if (!opt || opt.hidden) {
            vehicleRzCombobox.value = "";
            return;
        }
        vehicleRzCombobox.value = opt.textContent;
    }

    function refillVehicleRzDatalist(queryRaw) {
        if (!vehicleRzDatalist) return;
        const query = normalizeLabelSearch(queryRaw);
        const labels = visibleVehicleRzRows()
            .filter((row) => !query || normalizeLabelSearch(row.label).includes(query))
            .map((row) => row.label);
        const labelsKey = labels.join("\u0001");
        if (labelsKey === vehicleRzDatalistLabelsKey) return;
        vehicleRzDatalistLabelsKey = labelsKey;
        vehicleRzDatalist.innerHTML = "";
        labels.forEach((label) => {
            const dOption = document.createElement("option");
            dOption.value = label;
            vehicleRzDatalist.appendChild(dOption);
        });
    }

    function triggerVehicleRzSelectChange() {
        if (!vehicleRzSelect) return;
        vehicleRzSelect.dispatchEvent(new Event("change", { bubbles: true }));
    }

    function afterVehicleRzFilterChanged() {
        syncVehicleRzComboboxFromSelect();
        refillVehicleRzDatalist(vehicleRzCombobox ? vehicleRzCombobox.value : "");
        triggerVehicleRzSelectChange();
        if (window.jedisRefreshZpoPairingDock) window.jedisRefreshZpoPairingDock();
    }
    let applySubjectWasteTypes = null;

    async function syncYardStandaloneActivity() {
        const ys = cfg.yardStandalone;
        if (!ys || !ys.active || !activitySelect || !wasteTypeSelect || !suffixSelect) return;
        const w = String(wasteTypeSelect.value || "");
        const s = String(suffixSelect.value || "");
        const hints = ys.pairHints || [];
        const row = hints.find((h) => String(h.waste_type_id) === w && String(h.suffix_id) === s);
        const aid = row && row.activity_id ? String(row.activity_id) : "";
        if (aid && w && s) {
            activitySelect.value = aid;
            await loadVehicleRzByActivity(aid);
            await applyActivityRules(aid);
            if (datalist) datalist.innerHTML = "";
            subjectRows = [];
            if (icoLookupInput && icoLookupInput.value.trim().length >= 2) {
                await searchIco(icoLookupInput.value.trim());
            }
            syncVehicleKindConstraintHint();
            applySvozOverlayToRzHidden();
        } else if (!aid && w && s) {
            activitySelect.value = "";
            await loadVehicleRzByActivity("");
            await applyActivityRules("");
        }
    }

    async function loadRideTemplatesForSelectedVehicleKind() {
        if (!rideTemplateSelect || !U.rideTemplatesByVehicleKind) return;
        const rzId = vehicleRzSelect ? String(vehicleRzSelect.value || "") : "";
        const meta = rzId ? vehicleRzMeta[rzId] || { kind_ids: [] } : { kind_ids: [] };
        const rzKindIds = (meta.kind_ids || []).map((x) => String(x)).filter(Boolean);
        const activityId = activitySelect ? String(activitySelect.value || "") : "";
        if (!rzKindIds.length && !activityId) {
            rideTemplateRows = [];
            refillRideTemplateSelect([]);
            return;
        }
        try {
            const params = new URLSearchParams();
            if (rzKindIds.length) {
                params.set("vehicle_kind_ids", rzKindIds.join(","));
            } else if (activityId) {
                params.set("activity_id", activityId);
            }
            const response = await fetch(`${U.rideTemplatesByVehicleKind}?${params.toString()}`);
            const payload = await response.json();
            if (!payload.ok) {
                rideTemplateRows = [];
                refillRideTemplateSelect([]);
                return;
            }
            rideTemplateRows = payload.data || [];
            refillRideTemplateSelect(rideTemplateRows);
        } catch (e) {
            rideTemplateRows = [];
            refillRideTemplateSelect([]);
        }
    }

    function refillRideTemplateSelect(rows) {
        if (!rideTemplateSelect) return;
        rideTemplateSelect.innerHTML = "";
        const empty = document.createElement("option");
        empty.value = "";
        empty.textContent = "--- vyberte šablonu ---";
        rideTemplateSelect.appendChild(empty);
        (rows || []).forEach((row) => {
            const option = document.createElement("option");
            option.value = String(row.id);
            option.textContent = row.title;
            rideTemplateSelect.appendChild(option);
        });
    }

    async function applyRideTemplateById(templateId) {
        const row = (rideTemplateRows || []).find((item) => String(item.id) === String(templateId));
        if (!row) return;
        const templateFulfillmentAddress = Object.prototype.hasOwnProperty.call(row, "address_value")
            ? row.address_value || ""
            : null;
        function applyTemplateFulfillmentAddress() {
            if (templateFulfillmentAddress === null || !fulfillmentAddressInput) return;
            fulfillmentAddressMode = "manual";
            setFulfillmentAddressValue(templateFulfillmentAddress);
        }
        if (activitySelect && row.activity_id) {
            activitySelect.value = String(row.activity_id);
            await loadVehicleRzByActivity(String(row.activity_id));
            await loadDriversByContext(String(row.activity_id));
            await applyActivityRules(String(row.activity_id));
        }
        setSelectValue(icoSelect, row.ico_id);
        setSelectValue(nameSelect, row.name_id);
        if (icoLookupInput) {
            const subjectLabel = row.name_value || "";
            icoLookupInput.value = subjectLabel || icoLookupInput.value || "";
        }
        if (facilityAddressDisplay && Object.prototype.hasOwnProperty.call(row, "facility_address_value")) {
            facilityAddressDisplay.value = row.facility_address_value || "";
        }
        if (wasteTypeSelect && row.waste_type_id) {
            wasteTypeSelect.value = String(row.waste_type_id);
            const meta = wasteTypeMeta[String(row.waste_type_id)] || { code: "", category: "", label: "" };
            if (wasteTypeCombobox) wasteTypeCombobox.value = meta.label || "";
            if (wasteCodeDisplay) wasteCodeDisplay.value = meta.code || "";
            if (wasteCategoryDisplay) wasteCategoryDisplay.value = meta.category || "";
        }
        await updateSuffixOptions();
        if (suffixSelect && row.suffix_id) {
            const ok = Array.from(suffixSelect.options).some((o) => String(o.value) === String(row.suffix_id));
            if (ok) suffixSelect.value = String(row.suffix_id);
        }
        applyTemplateFulfillmentAddress();
        const c1 = document.getElementById("id_container_number");
        const c2 = document.getElementById("id_container_number_2");
        if (c1 && Object.prototype.hasOwnProperty.call(row, "container_number")) c1.value = row.container_number || "";
        if (c2 && Object.prototype.hasOwnProperty.call(row, "container_number_2")) c2.value = row.container_number_2 || "";
        if (contactPhoneInput && Object.prototype.hasOwnProperty.call(row, "contact_phone")) {
            contactPhoneInput.value = row.contact_phone || "";
        }
        if (contractNumberInput && Object.prototype.hasOwnProperty.call(row, "contract_number")) {
            contractNumberInput.value = row.contract_number || "";
        }
        if (contactNoteInput && Object.prototype.hasOwnProperty.call(row, "contact_note")) {
            contactNoteInput.value = row.contact_note || "";
        }
        // Šablona nepřenáší řidiče ani RZ z uložené šablony — uživatel je vybírá dole.
        // (Po změně činnosti loadDriversByContext obnoví předchozí výběr, pokud existuje — proto zde vynutíme prázdný stav.)
        if (driverSelect) driverSelect.value = "";
        if (driverCombobox) driverCombobox.value = "";
        if (driverHint) driverHint.textContent = "";
        if (vehicleRzSelect) vehicleRzSelect.value = "";
        applyRzFilterByDriver(null);
        syncVehicleRzComboboxFromSelect();
        refillVehicleRzDatalist("");
        const activityAfterTemplate = activitySelect ? String(activitySelect.value || "") : "";
        if (activityAfterTemplate) {
            await loadDriversByContext(activityAfterTemplate);
        }
        applyTemplateFulfillmentAddress();
        if (window.jedisRefreshZpoPairingDock) window.jedisRefreshZpoPairingDock();
    }

    function resolveSubjectHit(rawValue) {
        const value = (rawValue || "").trim();
        if (!value) return null;
        const valueLower = value.toLowerCase();
        return (
            subjectRows.find((item) => (item.name_value || "").toLowerCase() === valueLower) ||
            subjectRows.find((item) => (item.ico || "").trim() === value) ||
            subjectRows.find((item) => (item.label || "").toLowerCase() === valueLower) ||
            null
        );
    }

    function fetchSubjectProfileIdByNameId(nameId) {
        if (!nameId || !U.subjectProfileByName) return Promise.resolve(null);
        return fetch(`${U.subjectProfileByName}?name_id=${encodeURIComponent(nameId)}`, {
            credentials: "same-origin",
        })
            .then((r) => r.json())
            .then((payload) => (payload.ok && payload.subject_profile_id ? payload.subject_profile_id : null))
            .catch(() => null);
    }

    async function applySubjectHit(hit, options) {
        options = options || {};
        if (!hit) return;
        activeSubjectProfileId = hit.subject_profile_id != null ? hit.subject_profile_id : null;
        if (!activeSubjectProfileId && hit.name_id) {
            void fetchSubjectProfileIdByNameId(hit.name_id).then((pk) => {
                if (pk) {
                    activeSubjectProfileId = pk;
                    if (typeof window.jedisSyncSubjectPairsEditButton === "function") {
                        window.jedisSyncSubjectPairsEditButton();
                    }
                }
            });
        }
        lastSubjectPairHints = normalizePairHints(hit.pair_hints);
        lastCentralFulfillmentAddress = hit.fulfillment_address_value || "";
        if (!options.preserveFulfillmentMode) {
            fulfillmentAddressMode = "auto";
            pairAddressPinnedByUser = false;
            pairAddressPinWasteId = "";
            lastPrefillAddressOptions = [];
        }
        setSelectValue(icoSelect, hit.ico_id);
        setSelectValue(nameSelect, hit.name_id);
        if (icoLookupInput) {
            icoLookupInput.value = hit.name_value || hit.label || "";
        }
        if (facilityAddressDisplay) {
            facilityAddressDisplay.value = hit.facility_address_value || "";
        }
        if (contactPhoneInput && hit.contact_phone && window.CzechPhoneInput) {
            contactPhoneInput.value = window.CzechPhoneInput.format(hit.contact_phone);
        }
        if (contactNoteInput && hit.contact_note && !contactNoteManual) {
            contactNoteInput.value = hit.contact_note;
        }
        if (typeof applySubjectWasteTypes === "function") {
            applySubjectWasteTypes(hit);
        }
        // Při preserve await — fire-and-forget updateSuffixOptions jinak později schová prefill combo.
        if (options.preserveFulfillmentMode) {
            await updateSuffixOptions();
        } else {
            updateSuffixOptions();
        }
        void onSubjectStableChange();
        if (typeof window.jedisSyncSubjectPairsEditButton === "function") {
            window.jedisSyncSubjectPairsEditButton();
        }
    }

    async function ensureSubjectSelected(rawValue) {
        const value = (rawValue || "").trim();
        if (!value) return null;
        let hit = resolveSubjectHit(value);
        if (hit) {
            applySubjectHit(hit);
            return hit;
        }
        await searchIco(value);
        hit = resolveSubjectHit(value);
        if (hit) {
            applySubjectHit(hit);
            return hit;
        }
        return null;
    }

    async function updateSuffixOptions(opts) {
        const skipYardStandaloneSync = opts && opts.skipYardStandaloneSync;
        if (!suffixSelect || !wasteTypeSelect) return;
        const wasteTypeId = (wasteTypeSelect.value || "").trim();
        if (!wasteTypeId) {
            suffixSelect.innerHTML = "";
            const empty = document.createElement("option");
            empty.value = "";
            empty.textContent = "--- vyberte koncovku ---";
            suffixSelect.appendChild(empty);
            suffixSelect.value = "";
            if (suffixFilterNote) suffixFilterNote.textContent = "";
            syncContractFromSubjectPair();
            syncRideNoteFromSubjectPair();
            syncFulfillmentFromSubjectPair();
            return;
        }
        const previous = suffixSelect.value;
        const params = new URLSearchParams();
        params.set("waste_type_id", wasteTypeId);
        if (nameSelect && nameSelect.value) {
            params.set("name_id", nameSelect.value);
        }
        if (fulfillmentAddressInput && fulfillmentAddressInput.value) {
            params.set("address", fulfillmentAddressInput.value);
        }
        if (cfg.yardStandalone && cfg.yardStandalone.active) {
            params.set("yard_pruvodka_only", "1");
        }
        const response = await fetch(`${U.suffixesByContext}?${params.toString()}`);
        const payload = await response.json();
        if (!payload.ok) return;
        if (suffixFilterNote) {
            suffixFilterNote.textContent = payload.filter_note || "";
        }
        const rows = payload.data || [];
        suffixSelect.innerHTML = "";
        const empty = document.createElement("option");
        empty.value = "";
        empty.textContent = rows.length ? "--- vyberte koncovku ---" : "--- bez dostupné koncovky ---";
        suffixSelect.appendChild(empty);
        rows.forEach((row) => {
            const option = document.createElement("option");
            option.value = row.suffix_id;
            option.textContent = row.label;
            suffixSelect.appendChild(option);
        });
        const stillExists = previous && rows.some((row) => String(row.suffix_id) === String(previous));
        if (stillExists) {
            suffixSelect.value = previous;
        } else if (rows.length === 1) {
            // Jedna dostupná koncovka -> předvyplnit automaticky.
            suffixSelect.value = String(rows[0].suffix_id);
        } else {
            suffixSelect.value = "";
        }
        syncContractFromSubjectPair();
        syncRideNoteFromSubjectPair();
        syncFulfillmentFromSubjectPair();
        if (window.jedisRefreshZpoPairingDock) window.jedisRefreshZpoPairingDock();
        if (cfg.yardStandalone && cfg.yardStandalone.active && !skipYardStandaloneSync) {
            await syncYardStandaloneActivity();
        }
    }

    if (suffixSelect) {
        suffixSelect.addEventListener("change", async () => {
            markEditWasteContextIfChanged();
            // Neměnit mode ani mazat už vyplněnou adresu — jen obnovit options/smlouvu.
            syncContractFromSubjectPair();
            syncRideNoteFromSubjectPair();
            syncFulfillmentFromSubjectPair();
            if (cfg.yardStandalone && cfg.yardStandalone.active) {
                await syncYardStandaloneActivity();
            }
        });
    }

    async function loadVehicleRzByActivity(activityId) {
        if (!vehicleRzSelect) return;
        if (!activityId) {
            vehicleRzSelect.innerHTML = "";
            vehicleRzMeta = {};
            vehicleRzRowsFull = [];
            vehicleRzMapFull = {};
            if (vehicleRzCombobox) vehicleRzCombobox.value = "";
            if (vehicleRzDatalist) {
                vehicleRzDatalistLabelsKey = "";
                vehicleRzDatalist.innerHTML = "";
            }
            return;
        }
        const current = vehicleRzSelect.value;
        const params = new URLSearchParams();
        params.set("activity_id", String(activityId));
        const reqVehicleKindId = getRequiredPairVehicleKindId();
        if (reqVehicleKindId) {
            params.set("required_vehicle_kind_id", reqVehicleKindId);
        }
        const response = await fetch(`${U.vehicleRzByActivity}?${params.toString()}`);
        const payload = await response.json();
        if (!payload.ok) return;
        const options = payload.data || [];
        vehicleRzRowsFull = options.slice();
        vehicleRzMapFull = {};
        options.forEach((item) => {
            vehicleRzMapFull[item.label] = item;
        });
        vehicleRzSelect.innerHTML = "";
        vehicleRzMeta = {};
        const emptyOption = document.createElement("option");
        emptyOption.value = "";
        emptyOption.textContent = "-----";
        vehicleRzSelect.appendChild(emptyOption);
        options.forEach((item) => {
            const option = document.createElement("option");
            option.value = item.id;
            option.textContent = item.label;
            vehicleRzSelect.appendChild(option);
            vehicleRzMeta[String(item.id)] = { kind_ids: item.kind_ids || [] };
        });
        applySvozOverlayToRzHidden();
        const stillExists =
            current &&
            Array.from(vehicleRzSelect.options).some(
                (o) => String(o.value) === String(current) && !o.hidden
            );
        if (stillExists) vehicleRzSelect.value = current;
        syncVehicleRzComboboxFromSelect();
        refillVehicleRzDatalist(vehicleRzCombobox ? vehicleRzCombobox.value : "");
        await loadDriversByContext(activitySelect ? activitySelect.value : "");
        await loadRideTemplatesForSelectedVehicleKind();
    }

    function filterSvozTasksPanelByDriver(driver) {
        const panel = document.querySelector(".jedis-svoz-tasks-panel");
        if (!panel) return;
        const list = panel.querySelector("#jedis-svoz-tasks-list");
        if (!list) return;
        const items = list.querySelectorAll("li[data-svoz-vk]");
        const emptyNote = panel.querySelector("#jedis-svoz-tasks-driver-filter-empty");
        const ids = driver && Array.isArray(driver.kind_ids) ? driver.kind_ids.map((x) => String(x)) : [];
        const filterActive = Boolean(driver && ids.length > 0);
        let visibleCount = 0;
        items.forEach((li) => {
            const vk = (li.getAttribute("data-svoz-vk") || "").trim();
            if (!filterActive) {
                li.style.display = "";
                visibleCount += 1;
                return;
            }
            if (!vk) {
                li.style.display = "";
                visibleCount += 1;
                return;
            }
            const show = ids.includes(vk);
            li.style.display = show ? "" : "none";
            if (show) visibleCount += 1;
        });
        if (emptyNote) {
            emptyNote.style.display = filterActive && visibleCount === 0 ? "" : "none";
        }
    }

    function applyRzFilterByDriver(driver) {
        if (vehicleRzSelect) {
            const rzIds = (driver && driver.rz_ids) ? driver.rz_ids.map((x) => String(x)) : [];
            const options = Array.from(vehicleRzSelect.options);
            const current = String(vehicleRzSelect.value || "");

            // Výběr řidiče nesmí zamknout RZ na "předvolenou" hodnotu.
            // Necháváme všechny RZ podle činnosti; případné omezení řeší jen svoz overlay.
            options.forEach((opt) => {
                opt.hidden = false;
            });
            applySvozOverlayToRzHidden();
            const stillVisible =
                current &&
                options.some((opt) => opt.value && String(opt.value) === current && !opt.hidden);
            if (stillVisible) {
                vehicleRzSelect.value = current;
            } else {
                // Předvolba: pokud má řidič přiřazené konkrétní RZ, vybereme první
                // dostupnou; ostatní volby ale zůstávají normálně v seznamu.
                const preferred = rzIds.find((rid) =>
                    options.some((opt) => opt.value && String(opt.value) === rid && !opt.hidden)
                );
                if (preferred) {
                    vehicleRzSelect.value = preferred;
                } else {
                    vehicleRzSelect.value = "";
                    vehicleRzSelect.selectedIndex = 0;
                }
            }
            afterVehicleRzFilterChanged();
        }
        filterSvozTasksPanelByDriver(driver);
    }

    async function loadDriversByContext(activityId) {
        if (!driverSelect || !driverCombobox || !driverDatalist) return;
        if (!activityId) {
            driverSelect.innerHTML = "";
            const emptyOption = document.createElement("option");
            emptyOption.value = "";
            emptyOption.textContent = "-----";
            driverSelect.appendChild(emptyOption);
            driverDatalist.innerHTML = "";
            driverRowsFull = [];
            driverMapFull = {};
            driverSelect.value = "";
            driverCombobox.value = "";
            if (driverHint) driverHint.textContent = "";
            applyRzFilterByDriver(null);
            return;
        }
        const params = new URLSearchParams();
        params.set("activity_id", activityId);
        const driveDateVal = driveDateInput && driveDateInput.value ? driveDateInput.value.trim() : "";
        if (driveDateVal) {
            params.set("drive_date", driveDateVal);
        }
        const reqVehicleKindId = getRequiredPairVehicleKindId();
        if (reqVehicleKindId) {
            params.set("required_vehicle_kind_id", reqVehicleKindId);
        }
        const response = await fetch(`${U.driversByContext}?${params.toString()}`);
        const payload = await response.json();
        if (!payload.ok) return;
        const rows = payload.data || [];
        const current = driverSelect.value;
        driverRowsFull = rows;
        driverMapFull = {};
        rows.forEach((row) => {
            driverMapFull[row.label] = row;
        });
        driverSelect.innerHTML = "";
        const emptyOption = document.createElement("option");
        emptyOption.value = "";
        emptyOption.textContent = "-----";
        driverSelect.appendChild(emptyOption);
        rows.forEach((row) => {
            const option = document.createElement("option");
            option.value = row.id;
            option.textContent = row.label;
            driverSelect.appendChild(option);
        });
        const stillExists = current && rows.some((row) => String(row.id) === String(current));
        if (stillExists) {
            driverSelect.value = current;
            const hit = rows.find((row) => String(row.id) === String(current));
            if (hit) {
                driverCombobox.value = hit.label;
                if (driverHint) {
                    driverHint.textContent = hit.rz_text || hit.kinds_text || "";
                }
                applyRzFilterByDriver(hit);
            }
        } else {
            driverSelect.value = "";
            driverCombobox.value = "";
            if (driverHint) driverHint.textContent = "";
            applyRzFilterByDriver(null);
        }
        refillDriverDatalist(driverCombobox.value);
    }

    async function searchIco(query) {
        const qTrim = (query || "").trim();
        if (!qTrim || qTrim.length < 2) {
            datalist.innerHTML = "";
            subjectRows = [];
            setIcoLookupCreateHint(false);
            return;
        }
        const seq = ++subjectSearchSeq;
        const params = new URLSearchParams();
        params.set("q", qTrim);
        if (activitySelect && activitySelect.value) {
            params.set("activity_id", activitySelect.value);
        }
        try {
            const response = await fetch(`${U.subjectSearch}?${params.toString()}`);
            const payload = await response.json();
            if (seq !== subjectSearchSeq) return;
            const rows = payload.data || [];
            subjectRows = rows;
            datalist.innerHTML = "";
            rows.forEach((item) => {
                const option = document.createElement("option");
                option.value = item.name_value || item.label;
                datalist.appendChild(option);
            });
            setIcoLookupCreateHint(rows.length === 0);
        } catch (e) {
            if (seq !== subjectSearchSeq) return;
            subjectRows = [];
            if (datalist) datalist.innerHTML = "";
            setIcoLookupCreateHint(false);
        }
    }

    if (activitySelect) {
        activitySelect.addEventListener("change", async () => {
            const aid = activitySelect.value;
            await loadVehicleRzByActivity(aid);
            await applyActivityRules(aid);
            if (datalist) datalist.innerHTML = "";
            subjectRows = [];
            if (icoLookupInput && icoLookupInput.value.trim().length >= 2) {
                await searchIco(icoLookupInput.value.trim());
            }
            if (window.jedisRefreshZpoPairingDock) window.jedisRefreshZpoPairingDock();
        });
    }

    if (driveDateInput && activitySelect) {
        driveDateInput.addEventListener("change", async () => {
            const aid = activitySelect.value;
            if (aid) {
                await loadDriversByContext(aid);
            }
        });
    }

    if (vehicleRzCombobox && vehicleRzSelect) {
        vehicleRzCombobox.setAttribute("list", "vehicle-rz-datalist");
        vehicleRzCombobox.addEventListener("mousedown", () => {
            if (document.activeElement !== vehicleRzCombobox) {
                refillVehicleRzDatalist("");
            }
        });
        vehicleRzCombobox.addEventListener("keydown", (e) => {
            if (e.key === "ArrowDown" || e.key === "F4") {
                refillVehicleRzDatalist("");
            }
        });
        vehicleRzCombobox.addEventListener("input", () => {
            refillVehicleRzDatalist(vehicleRzCombobox.value);
        });
        vehicleRzCombobox.addEventListener("change", () => {
            const hit = resolveVehicleRzHitByText(vehicleRzCombobox.value);
            if (hit) {
                vehicleRzCombobox.value = hit.label;
                applyVehicleRzHit(hit);
            }
            refillVehicleRzDatalist(vehicleRzCombobox.value);
            if (window.jedisRefreshZpoPairingDock) window.jedisRefreshZpoPairingDock();
        });
        vehicleRzCombobox.addEventListener("blur", () => {
            const hit = resolveVehicleRzHitByText(vehicleRzCombobox.value);
            if (hit) {
                vehicleRzCombobox.value = hit.label;
                applyVehicleRzHit(hit);
            }
            refillVehicleRzDatalist(vehicleRzCombobox.value);
            if (window.jedisRefreshZpoPairingDock) window.jedisRefreshZpoPairingDock();
        });
        vehicleRzSelect.style.display = "none";
        vehicleRzSelect.addEventListener("change", async () => {
            syncFulfillmentFromSubjectPair();
            await loadRideTemplatesForSelectedVehicleKind();
        });
    }

    if (rideTemplateApplyBtn && rideTemplateSelect) {
        rideTemplateApplyBtn.addEventListener("click", async () => {
            const id = String(rideTemplateSelect.value || "");
            if (!id) return;
            await applyRideTemplateById(id);
        });
    }

    /** V ES module (strict) nesmí být funkce deklarovaná uvnitř if pro použití z applyFollowUpPrefill. */
    let refillDriverDatalist = function () {};

    function resolveDriverHitByText(rawValue) {
        const raw = (rawValue || "").trim();
        if (!raw) return null;
        const direct = driverMapFull[raw];
        if (direct) return direct;
        const q = normalizeLabelSearch(rawValue);
        if (!q) return null;
        const exact = driverRowsFull.find((row) => normalizeLabelSearch(row.label) === q);
        if (exact) return exact;
        const partials = driverRowsFull.filter((row) => normalizeLabelSearch(row.label).includes(q));
        if (partials.length === 1) return partials[0];
        return null;
    }

    function applyDriverHit(hit) {
        if (!driverSelect) return;
        if (!hit) {
            driverSelect.value = "";
            if (driverHint) driverHint.textContent = "";
            applyRzFilterByDriver(null);
            return;
        }
        driverSelect.value = hit.id;
        if (driverHint) {
            driverHint.textContent = hit.rz_text || hit.kinds_text || "";
        }
        applyRzFilterByDriver(hit);
    }

    function resolveVehicleRzHitByText(rawValue) {
        const raw = (rawValue || "").trim();
        if (!raw) return null;
        const direct = vehicleRzMapFull[raw];
        if (direct && visibleVehicleRzRows().some((r) => String(r.id) === String(direct.id))) {
            return direct;
        }
        const q = normalizeLabelSearch(rawValue);
        if (!q) return null;
        const vis = visibleVehicleRzRows();
        const exact = vis.find((row) => normalizeLabelSearch(row.label) === q);
        if (exact) return exact;
        const partials = vis.filter((row) => normalizeLabelSearch(row.label).includes(q));
        if (partials.length === 1) return partials[0];
        return null;
    }

    function applyVehicleRzHit(hit) {
        if (!vehicleRzSelect) return;
        if (!hit) {
            vehicleRzSelect.value = "";
        } else {
            vehicleRzSelect.value = String(hit.id);
        }
        triggerVehicleRzSelectChange();
    }

    function syncWasteTypeFromCombobox() {
        if (!wasteTypeCombobox || !wasteTypeSelect) return;
        const label = (wasteTypeCombobox.value || "").trim();
        if (!label) return;
        const exact = Object.entries(wasteTypeMeta).find(([, meta]) => meta.label === label);
        if (exact) {
            wasteTypeSelect.value = exact[0];
            return;
        }
        const q = normalizeLabelSearch(label);
        if (!q) return;
        const partials = Object.entries(wasteTypeMeta).filter(([, meta]) =>
            normalizeLabelSearch(meta.label).includes(q)
        );
        if (partials.length === 1) {
            wasteTypeSelect.value = partials[0][0];
        }
    }

    function syncComboboxFieldsBeforeSubmit() {
        fulfillmentSyncSuspended = true;
        const addrBeforeSubmit = fulfillmentAddressInput
            ? String(fulfillmentAddressInput.value || "").trim()
            : "";
        const comboBeforeSubmit = pairAddressSelect
            ? String(pairAddressSelect.value || "").trim()
            : "";
        const keepAddr = addrBeforeSubmit || comboBeforeSubmit;
        try {
            // Nevolat applySubjectHit — spouští async suffix sync a prefer last adresu.
            if (keepAddr) {
                fulfillmentAddressMode = "manual";
                pairAddressPinnedByUser = true;
                pairAddressPinWasteId = wasteTypeSelect
                    ? String(wasteTypeSelect.value || "")
                    : "";
                if (fulfillmentAddressInput && !addrBeforeSubmit && comboBeforeSubmit) {
                    setFulfillmentAddressValue(comboBeforeSubmit);
                }
            }
            syncWasteTypeFromCombobox();
            if (driverCombobox) {
                const driverHit = resolveDriverHitByText(driverCombobox.value);
                if (driverHit) {
                    driverCombobox.value = driverHit.label;
                }
                applyDriverHit(driverHit);
            }
            if (vehicleRzCombobox) {
                const rzHit = resolveVehicleRzHitByText(vehicleRzCombobox.value);
                if (rzHit) {
                    vehicleRzCombobox.value = rzHit.label;
                }
                applyVehicleRzHit(rzHit);
            }
            // Po syncu RZ/řidiče znovu prosadit zvolenou adresu (jako u CR).
            if (keepAddr && fulfillmentAddressInput) {
                fulfillmentAddressMode = "manual";
                pairAddressPinnedByUser = true;
                pairAddressPinWasteId = wasteTypeSelect
                    ? String(wasteTypeSelect.value || "")
                    : "";
                setFulfillmentAddressValue(keepAddr);
                if (pairAddressSelect) {
                    const hasOpt = Array.from(pairAddressSelect.options).some(
                        (o) => o.value === keepAddr
                    );
                    if (hasOpt) {
                        pairAddressSelectProgrammatic = true;
                        try {
                            pairAddressSelect.value = keepAddr;
                        } finally {
                            pairAddressSelectProgrammatic = false;
                        }
                    }
                }
            }
        } finally {
            fulfillmentSyncSuspended = false;
        }
    }

    if (driverCombobox && driverSelect) {
        refillDriverDatalist = function (queryRaw) {
            const query = normalizeLabelSearch(queryRaw);
            driverDatalist.innerHTML = "";
            driverRowsFull
                .filter((row) => !query || normalizeLabelSearch(row.label).includes(query))
                .forEach((row) => {
                    const dOption = document.createElement("option");
                    dOption.value = row.label;
                    driverDatalist.appendChild(dOption);
                });
        };


        driverCombobox.setAttribute("list", "driver-datalist");
        driverCombobox.addEventListener("input", () => {
            refillDriverDatalist(driverCombobox.value);
        });
        driverCombobox.addEventListener("change", () => {
            const hit = resolveDriverHitByText(driverCombobox.value);
            if (hit) {
                driverCombobox.value = hit.label;
            }
            refillDriverDatalist(driverCombobox.value);
            applyDriverHit(hit);
        });
        driverCombobox.addEventListener("blur", () => {
            const hit = resolveDriverHitByText(driverCombobox.value);
            if (hit) {
                driverCombobox.value = hit.label;
            }
            refillDriverDatalist(driverCombobox.value);
            applyDriverHit(hit);
        });
        driverSelect.style.display = "none";
    }

    if (icoLookupInput) {
        icoLookupInput.setAttribute("list", "ico-lookup-list");
        icoLookupInput.addEventListener("input", async () => {
            await searchIco(icoLookupInput.value);
            const hit = resolveSubjectHit(icoLookupInput.value);
            if (hit) {
                applySubjectHit(hit);
            } else {
                activeSubjectProfileId = null;
                if (typeof applySubjectWasteTypes === "function") {
                    applySubjectWasteTypes(null);
                }
                if (typeof window.jedisSyncSubjectPairsEditButton === "function") {
                    window.jedisSyncSubjectPairsEditButton();
                }
            }
        });
        icoLookupInput.addEventListener("change", async () => {
            await ensureSubjectSelected(icoLookupInput.value);
        });
        icoLookupInput.addEventListener("blur", async () => {
            await ensureSubjectSelected(icoLookupInput.value);
        });
    }

    if (nameSelect) {
        nameSelect.addEventListener("change", () => {
            void fetchSubjectProfileIdByNameId(nameSelect.value).then((pk) => {
                activeSubjectProfileId = pk;
            });
        });
        if (nameSelect.value && !activeSubjectProfileId) {
            void fetchSubjectProfileIdByNameId(nameSelect.value).then((pk) => {
                activeSubjectProfileId = pk;
            });
        }
    }

    if (fulfillmentAddressInput) {
        fulfillmentAddressInput.addEventListener("input", () => {
            if (!fulfillmentAddressProgrammatic) {
                fulfillmentAddressMode = "manual";
            }
            syncFulfillmentMapLink();
        });
        fulfillmentAddressInput.addEventListener("change", () => {
            if (!fulfillmentAddressProgrammatic) {
                fulfillmentAddressMode = "manual";
            }
            updateSuffixOptions();
            syncFulfillmentMapLink();
        });
        fulfillmentAddressInput.addEventListener("blur", () => {
            if (!fulfillmentAddressProgrammatic) {
                fulfillmentAddressMode = "manual";
            }
            updateSuffixOptions();
            syncFulfillmentMapLink();
        });
    }

    if (pairAddressSelect) {
        pairAddressSelect.addEventListener("change", () => {
            // Rebuild options nesmí vymazat už zapsanou adresu plnění.
            if (pairAddressSelectProgrammatic) return;
            const wasteId = wasteTypeSelect ? String(wasteTypeSelect.value || "") : "";
            const chosen = String(pairAddressSelect.value || "").trim();
            if (chosen) {
                pairAddressPinnedByUser = true;
                pairAddressPinWasteId = wasteId;
                fulfillmentAddressMode = "manual";
                setFulfillmentAddressValue(chosen);
                return;
            }
            // Prázdný výběr jen od uživatele — nechat pole, pokud už má hodnotu z dřívějška.
            pairAddressPinnedByUser = false;
            pairAddressPinWasteId = "";
            if (!(fulfillmentAddressInput && String(fulfillmentAddressInput.value || "").trim())) {
                fulfillmentAddressMode = "auto";
            }
        });
    }

    window.FulfillmentAddressField.init({
        inputId: "id_fulfillment_address_value",
        datalistId: "waste-docs-address-suggestions",
        mapButtonId: "waste-docs-map-open-btn",
        suggestionsUrl: U.addressSuggestions,
        geocodeUrl: U.addressGeocode,
        reverseGeocodeUrl: U.addressReverseGeocode,
        defaultLat: cfg.defaultMapLat,
        defaultLng: cfg.defaultMapLng,
        preferredCity: defaultCity,
        minChars: 2,
        debounceMs: 300,
        normalizeOnBlur: true,
        prefillSuggestionsOnFocus: true,
        onAddressChange: () => {
            if (!fulfillmentAddressProgrammatic) {
                fulfillmentAddressMode = "manual";
            }
            syncFulfillmentMapLink();
        },
    });

    if (wasteTypeCombobox && wasteTypeSelect && wasteTypeDatalist) {
        const optionMap = {};
        Object.entries(wasteTypeMeta).forEach(([id, meta]) => {
            optionMap[meta.label] = id;
        });
        let activeWasteTypeIds = null;

        function isYardStandaloneActive() {
            return Boolean(cfg.yardStandalone && cfg.yardStandalone.active);
        }

        function yardStandaloneWasteTypeIds() {
            if (!isYardStandaloneActive()) {
                return null;
            }
            return (cfg.yardStandalone.allowedWasteTypeIds || []).map(String);
        }

        function refillWasteTypeDatalist(query) {
            const normalizedQuery = (query || "").toLowerCase().replace(/\s+/g, "");
            wasteTypeDatalist.innerHTML = "";
            const yardIds = yardStandaloneWasteTypeIds();
            const ids = yardIds !== null ? yardIds : activeWasteTypeIds;
            const allowed =
                ids !== null
                    ? ids.map((id) => wasteTypeMeta[String(id)]).filter(Boolean)
                    : Object.values(wasteTypeMeta);
            allowed.forEach((meta) => {
                const searchable = `${meta.code} ${meta.label}`.toLowerCase().replace(/\s+/g, "");
                if (!normalizedQuery || searchable.includes(normalizedQuery)) {
                    const option = document.createElement("option");
                    option.value = meta.label;
                    wasteTypeDatalist.appendChild(option);
                }
            });
        }

        wasteTypeCombobox.setAttribute("list", "waste-type-datalist");
        refillWasteTypeDatalist("");

        if (wasteTypeSelect.value && wasteTypeMeta[wasteTypeSelect.value]) {
            wasteTypeCombobox.value = wasteTypeMeta[wasteTypeSelect.value].label;
        }

        wasteTypeCombobox.addEventListener("input", () => {
            refillWasteTypeDatalist(wasteTypeCombobox.value);
            const selectedId = optionMap[wasteTypeCombobox.value];
            if (selectedId) {
                wasteTypeSelect.value = selectedId;
            }
            syncWasteMeta();
        });

        wasteTypeCombobox.addEventListener("change", () => {
            const selectedId = optionMap[wasteTypeCombobox.value];
            if (selectedId) {
                wasteTypeSelect.value = selectedId;
            }
            syncWasteMeta();
        });

        wasteTypeSelect.style.display = "none";

        const syncWasteMeta = () => {
            const selectedId = wasteTypeSelect.value;
            const meta = wasteTypeMeta[selectedId] || { code: "", category: "" };
            if (wasteCodeDisplay) wasteCodeDisplay.value = meta.code || "";
            if (wasteCategoryDisplay) wasteCategoryDisplay.value = meta.category || "";
            markEditWasteContextIfChanged();
            pairAddressPinnedByUser = false;
            pairAddressPinWasteId = "";
            fulfillmentAddressMode = "auto";
            setFulfillmentAddressValue("");
            updateSuffixOptions();
        };
        wasteTypeSelect.addEventListener("change", syncWasteMeta);
        applySubjectWasteTypes = (hit) => {
            const yardIds = yardStandaloneWasteTypeIds();
            if (yardIds !== null) {
                activeWasteTypeIds = yardIds;
                lastSubjectPairHints = normalizePairHints(cfg.yardStandalone.pairHints);
            } else {
                activeWasteTypeIds = null;
                if (!hit) {
                    lastSubjectPairHints = [];
                }
                if (hit && Array.isArray(hit.allowed_waste_type_ids) && hit.allowed_waste_type_ids.length) {
                    activeWasteTypeIds = hit.allowed_waste_type_ids.map((x) => String(x));
                }
            }
            refillWasteTypeDatalist(wasteTypeCombobox.value);
            if (activeWasteTypeIds && activeWasteTypeIds.length) {
                const selected = String(wasteTypeSelect.value || "");
                if (!activeWasteTypeIds.includes(selected)) {
                    if (activeWasteTypeIds.length === 1) {
                        const preferred = String(activeWasteTypeIds[0] || "");
                        if (preferred && wasteTypeMeta[preferred]) {
                            wasteTypeSelect.value = preferred;
                            wasteTypeCombobox.value = wasteTypeMeta[preferred].label;
                        } else {
                            wasteTypeSelect.value = "";
                            wasteTypeCombobox.value = "";
                        }
                    } else {
                        wasteTypeSelect.value = "";
                        wasteTypeCombobox.value = "";
                    }
                }
            }
            syncWasteMeta();
        };
        if (wasteTypeClearBtn) {
            wasteTypeClearBtn.addEventListener("click", () => {
                wasteTypeCombobox.value = "";
                wasteTypeSelect.value = "";
                refillWasteTypeDatalist("");
                syncWasteMeta();
                wasteTypeCombobox.focus();
            });
        }
        if (cfg.yardStandalone && cfg.yardStandalone.active) {
            lastSubjectPairHints = normalizePairHints(cfg.yardStandalone.pairHints);
            activeWasteTypeIds = (cfg.yardStandalone.allowedWasteTypeIds || []).map(String);
            refillWasteTypeDatalist(wasteTypeCombobox.value);
            if (driveDateInput && cfg.yardStandalone.driveDateIso) {
                driveDateInput.value = cfg.yardStandalone.driveDateIso;
                driveDateInput.setAttribute("readonly", "readonly");
            }
        }
        syncWasteMeta();
    }
    if (contactPhoneInput && window.CzechPhoneInput) {
        window.CzechPhoneInput.bind(contactPhoneInput);
    }
    if (contactNoteInput) {
        contactNoteInput.addEventListener("input", () => {
            contactNoteManual = true;
            contactNoteTypedByUser = true;
        });
        contactNoteInput.addEventListener("change", () => {
            contactNoteManual = true;
            contactNoteTypedByUser = true;
        });
    }

    async function applyFollowUpPrefill(p) {
        if (!p) return;
        const isEdit = Boolean(cfg.isEdit);
        const skipDriverRz = Boolean(p.skip_driver_rz_auto_select);
        const prefillAddr = (p.fulfillment_address || "").trim();
        const prefillAddressOptions = Array.isArray(p.fulfillment_address_options)
            ? p.fulfillment_address_options
            : [];
        const usedPrefillAddressCombo = applyPrefillAddressOptions(
            prefillAddressOptions,
            prefillAddr
        );
        if (!usedPrefillAddressCombo) {
            if (prefillAddr) {
                fulfillmentAddressMode = "manual";
                setFulfillmentAddressValue(prefillAddr);
            }
        }
        if (!isEdit && driverSelect && driverCombobox) {
            driverSelect.value = "";
            driverCombobox.value = "";
            if (driverHint) driverHint.textContent = "";
            applyRzFilterByDriver(null);
        }
        setSelectValue(icoSelect, p.ico_id);
        setSelectValue(nameSelect, p.name_id);
        if (icoLookupInput) {
            icoLookupInput.value = p.ico_lookup || "";
        }
        if (!usedPrefillAddressCombo && !prefillAddr && fulfillmentAddressInput) {
            setFulfillmentAddressValue("");
        }
        if (facilityAddressDisplay) {
            facilityAddressDisplay.value = p.facility_address || "";
        }
        if (contractNumberInput) {
            contractNumberInput.value = p.contract_number || "";
        }
        if (contactPhoneInput && p.contact_phone) {
            contactPhoneInput.value = window.CzechPhoneInput
                ? window.CzechPhoneInput.format(p.contact_phone)
                : p.contact_phone;
        }
        const q = (p.subject_search_query || "").trim();
        if (q.length >= 2) {
            await searchIco(q);
            const hit =
                (subjectRows || []).find(
                    (item) =>
                        String(item.ico_id) === String(p.ico_id) &&
                        String(item.name_id) === String(p.name_id)
                ) || resolveSubjectHit(icoLookupInput ? icoLookupInput.value : "");
            if (hit) {
                await applySubjectHit(hit, {
                    preserveFulfillmentMode: Boolean(prefillAddr || usedPrefillAddressCombo),
                });
            }
        }
        if (p.vehicle_rz_id && vehicleRzSelect && !skipDriverRz) {
            if (cfgInitialFollowUpPk) {
                ensureVehicleRzOptionVisible(p.vehicle_rz_id);
            }
            const stillExists = Array.from(vehicleRzSelect.options).some(
                (o) => String(o.value) === String(p.vehicle_rz_id) && !o.hidden
            );
            if (stillExists) {
                vehicleRzSelect.value = String(p.vehicle_rz_id);
                const row = vehicleRzRowsFull.find((r) => String(r.id) === String(p.vehicle_rz_id));
                if (row && vehicleRzCombobox) {
                    vehicleRzCombobox.value = row.label;
                }
                afterVehicleRzFilterChanged();
            }
        }
        const passportSelect = document.getElementById("id_container_passport");
        if (p.container_passport_id && passportSelect) {
            const okPass = Array.from(passportSelect.options).some(
                (o) => String(o.value) === String(p.container_passport_id)
            );
            if (okPass) {
                passportSelect.value = String(p.container_passport_id);
            }
        }
        if (p.waste_type_id && wasteTypeSelect && wasteCodeDisplay && wasteCategoryDisplay) {
            wasteTypeSelect.value = String(p.waste_type_id);
            const meta = wasteTypeMeta[String(p.waste_type_id)] || { code: "", category: "" };
            if (wasteTypeCombobox) {
                wasteTypeCombobox.value = meta.label || "";
            }
            wasteCodeDisplay.value = meta.code || "";
            wasteCategoryDisplay.value = meta.category || "";
            await updateSuffixOptions();
            if (p.suffix_id && suffixSelect) {
                const ok = Array.from(suffixSelect.options).some(
                    (o) => String(o.value) === String(p.suffix_id)
                );
                if (ok) {
                    suffixSelect.value = String(p.suffix_id);
                }
            }
        }
        syncContractFromSubjectPair();
        syncRideNoteFromSubjectPair();
        if (usedPrefillAddressCombo) {
            applyPrefillAddressOptions(prefillAddressOptions, prefillAddr);
        } else {
            syncFulfillmentFromSubjectPair();
        }
        if (isEdit) {
            if (facilityAddressDisplay && Object.prototype.hasOwnProperty.call(p, "facility_address")) {
                facilityAddressDisplay.value = p.facility_address || "";
            }
            if (usedPrefillAddressCombo) {
                applyPrefillAddressOptions(prefillAddressOptions, prefillAddr);
            } else if (prefillAddr) {
                fulfillmentAddressMode = "manual";
                pairAddressPinnedByUser = true;
                pairAddressPinWasteId = wasteTypeSelect
                    ? String(wasteTypeSelect.value || "")
                    : "";
                setFulfillmentAddressValue(prefillAddr);
                // Jeden sync: inOptions ponechá uloženou adresu a zobrazí combo.
                syncFulfillmentFromSubjectPair();
            } else if (
                fulfillmentAddressInput &&
                Object.prototype.hasOwnProperty.call(p, "fulfillment_address")
            ) {
                fulfillmentAddressMode = "manual";
                pairAddressPinnedByUser = true;
                pairAddressPinWasteId = wasteTypeSelect
                    ? String(wasteTypeSelect.value || "")
                    : "";
                setFulfillmentAddressValue(p.fulfillment_address || "");
                syncFulfillmentFromSubjectPair();
            }
            if (contractNumberInput && Object.prototype.hasOwnProperty.call(p, "contract_number")) {
                contractNumberInput.value = p.contract_number || "";
            }
            if (contactPhoneInput && Object.prototype.hasOwnProperty.call(p, "contact_phone")) {
                const rawPh = p.contact_phone || "";
                contactPhoneInput.value = rawPh
                    ? window.CzechPhoneInput
                        ? window.CzechPhoneInput.format(rawPh)
                        : rawPh
                    : "";
            }
            if (contactNoteInput && Object.prototype.hasOwnProperty.call(p, "contact_note") && p.contact_note && !contactNoteManual) {
                contactNoteInput.value = p.contact_note;
            }
            const c1 = document.getElementById("id_container_number");
            const c2 = document.getElementById("id_container_number_2");
            if (c1 && Object.prototype.hasOwnProperty.call(p, "container_number")) {
                c1.value = p.container_number || "";
            }
            if (c2 && Object.prototype.hasOwnProperty.call(p, "container_number_2")) {
                c2.value = p.container_number_2 || "";
            }
            if (p.driver_id != null && p.driver_id !== "" && driverSelect && !skipDriverRz) {
                const did = String(p.driver_id);
                const stillDr = Array.from(driverSelect.options).some(
                    (o) => String(o.value) === did && !o.hidden
                );
                if (stillDr) {
                    driverSelect.value = did;
                    const row = driverRowsFull.find((r) => String(r.id) === did);
                    if (row && driverCombobox) {
                        driverCombobox.value = row.label;
                    }
                    if (driverHint) {
                        driverHint.textContent = row ? row.rz_text || row.kinds_text || "" : "";
                    }
                    applyRzFilterByDriver(row || null);
                    if (driverCombobox) refillDriverDatalist(driverCombobox.value);
                }
            }
        }
        if (!isEdit) {
            if (prefillAddr) {
                fulfillmentAddressMode = "manual";
                setFulfillmentAddressValue(prefillAddr);
            }
            const c1 = document.getElementById("id_container_number");
            const c2 = document.getElementById("id_container_number_2");
            if (c1 && Object.prototype.hasOwnProperty.call(p, "container_number")) {
                c1.value = p.container_number || "";
            }
            if (c2 && Object.prototype.hasOwnProperty.call(p, "container_number_2")) {
                c2.value = p.container_number_2 || "";
            }
            if (contactNoteInput && Object.prototype.hasOwnProperty.call(p, "contact_note") && p.contact_note) {
                contactNoteInput.value = p.contact_note || "";
            }
            if (p.driver_id != null && p.driver_id !== "" && driverSelect && !skipDriverRz) {
                const did = String(p.driver_id);
                const stillDr = Array.from(driverSelect.options).some(
                    (o) => String(o.value) === did && !o.hidden
                );
                if (stillDr) {
                    driverSelect.value = did;
                    const row = driverRowsFull.find((r) => String(r.id) === did);
                    if (row && driverCombobox) {
                        driverCombobox.value = row.label;
                    }
                    if (driverHint && row) {
                        driverHint.textContent = row.rz_text || row.kinds_text || "";
                    }
                    applyRzFilterByDriver(row || null);
                    if (driverCombobox) refillDriverDatalist(driverCombobox.value);
                }
            }
            const hasPrefillRz = !skipDriverRz && p.vehicle_rz_id != null && p.vehicle_rz_id !== "";
            if (hasPrefillRz && vehicleRzSelect) {
                if (cfgInitialFollowUpPk) {
                    ensureVehicleRzOptionVisible(p.vehicle_rz_id);
                }
                const stillRz = Array.from(vehicleRzSelect.options).some(
                    (o) => String(o.value) === String(p.vehicle_rz_id) && !o.hidden
                );
                if (stillRz) {
                    vehicleRzSelect.value = String(p.vehicle_rz_id);
                    const rzRow = vehicleRzRowsFull.find((r) => String(r.id) === String(p.vehicle_rz_id));
                    if (rzRow && vehicleRzCombobox) {
                        vehicleRzCombobox.value = rzRow.label;
                    }
                    afterVehicleRzFilterChanged();
                } else if (!skipDriverRz) {
                    autoSelectVehicleRzByRequiredKind();
                }
            } else if (!skipDriverRz && (!vehicleRzSelect || !vehicleRzSelect.value)) {
                autoSelectVehicleRzByRequiredKind();
            }
        }
        restoreInitialFollowUpParentIfNeeded();
        if (window.jedisRefreshZpoPairingDock) window.jedisRefreshZpoPairingDock();
    }

    (async function initPruvodkaFormForActivity() {
        if (cfg.yardStandalone && cfg.yardStandalone.active) {
            await syncYardStandaloneActivity();
        }
        const aid = activitySelect ? activitySelect.value : "";
        await loadVehicleRzByActivity(aid);
        if (aid) {
            await loadDriversByContext(aid);
        } else {
            await loadDriversByContext("");
        }
        await applyActivityRules(aid);
        if (cfg.followUpPrefill && aid) {
            await applyFollowUpPrefill(cfg.followUpPrefill);
        } else if (cfg.customerRequestPrefill && aid) {
            await applyFollowUpPrefill(cfg.customerRequestPrefill);
        } else if (cfg.yardHazardPrefill && aid) {
            await applyFollowUpPrefill(cfg.yardHazardPrefill);
        } else if (cfg.svozPrefill && aid) {
            await applyFollowUpPrefill(cfg.svozPrefill);
        } else if (cfg.editFormPrefill && aid) {
            await applyFollowUpPrefill(cfg.editFormPrefill);
        }
        await loadRideTemplatesForSelectedVehicleKind();
        scheduleSubjectOpenFollowUpsHint();
        highlightFormErrorsAndScroll();
    })();

    function highlightFormErrorsAndScroll() {
        document.querySelectorAll(".field-row .errorlist").forEach((errEl) => {
            const row = errEl.closest(".field-row");
            if (row) row.classList.add("field-row--has-error");
        });
        if (!cfg.hasFormErrors) return;
        const summary = document.getElementById("pruvodka-form-error-summary");
        const target = summary || document.querySelector(".field-row--has-error");
        if (target && typeof target.scrollIntoView === "function") {
            target.scrollIntoView({ behavior: "smooth", block: "center" });
        }
    }

    window.jedisGetActiveSubjectProfileId = function () {
        return activeSubjectProfileId;
    };
    window.jedisApplySubjectSnapshot = function (snapshot) {
        if (snapshot) applySubjectHit(snapshot);
    };
    window.jedisEnsureSubjectSelected = ensureSubjectSelected;

    const pruvodkaFormEl = document.querySelector("form.form-grid");
    const pruvodkaSubmitBtn = pruvodkaFormEl
        ? pruvodkaFormEl.querySelector('button[type="submit"]')
        : null;
    if (pruvodkaFormEl && pruvodkaSubmitBtn) {
        pruvodkaSubmitBtn.addEventListener("click", () => syncComboboxFieldsBeforeSubmit(), true);
        pruvodkaFormEl.addEventListener("submit", () => syncComboboxFieldsBeforeSubmit());
    }

    if (document.getElementById("jedis-edit-subject-pairs-btn")) {
        bootSubjectPairsModal(cfg, {
            getProfileId: () => activeSubjectProfileId,
            ensureSubject: ensureSubjectSelected,
            applySnapshot: (snapshot) => {
                if (snapshot) applySubjectHit(snapshot);
            },
        });
    }

    if (editInitialWaste) {
        editInitialWaste.wasteTypeId = wasteTypeSelect
            ? (wasteTypeSelect.value || "").trim()
            : "";
        editInitialWaste.suffixId = suffixSelect ? (suffixSelect.value || "").trim() : "";
    }
}
