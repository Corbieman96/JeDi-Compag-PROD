/**
 * Interakce formsetu Povolené odpady a koncovky (kopírování, řazení, sloty výjimek).
 */
(function () {
    function escapeRe(s) {
        return s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
    }

    function getCardFormIndex(card, prefix) {
        const inp = card.querySelector("input[name^='" + prefix + "-']");
        if (!inp || !inp.name) return null;
        const m = inp.name.match(new RegExp("^" + escapeRe(prefix) + "-(\\d+)-"));
        return m ? parseInt(m[1], 10) : null;
    }

    function patchIndexedAttrs(el, prefix, oldIdx, newIdx) {
        const ol = prefix + "-" + oldIdx + "-";
        const nw = prefix + "-" + newIdx + "-";
        const nspRe = new RegExp("nsp-(body|yard|doc)-" + oldIdx + "(?!\\d)", "g");
        ["name", "id", "href", "aria-controls", "aria-labelledby"].forEach(function (attr) {
            if (!el.hasAttribute(attr)) return;
            let v = el.getAttribute(attr);
            if (!v) return;
            if (v.indexOf(ol) !== -1) v = v.split(ol).join(nw);
            v = v.replace(nspRe, function (_, kind) {
                return "nsp-" + kind + "-" + newIdx;
            });
            el.setAttribute(attr, v);
        });
    }

    function reindexClonedPairCard(clone, prefix, oldIdx, newIdx) {
        clone.querySelectorAll("*").forEach(function (el) {
            patchIndexedAttrs(el, prefix, oldIdx, newIdx);
        });
        clone.querySelectorAll("label[for]").forEach(function (lab) {
            const v = lab.getAttribute("for");
            if (!v) return;
            const ol = prefix + "-" + oldIdx + "-";
            const nw = prefix + "-" + newIdx + "-";
            let nv = v.indexOf(ol) !== -1 ? v.split(ol).join(nw) : v;
            const nspRe = new RegExp("nsp-(body|yard|doc)-" + oldIdx + "(?!\\d)", "g");
            nv = nv.replace(nspRe, function (_, kind) {
                return "nsp-" + kind + "-" + newIdx;
            });
            lab.setAttribute("for", nv);
        });
    }

    function clearCopiedPairMetadata(clone, prefix, newIdx) {
        const pkInp = clone.querySelector("input[name='" + prefix + "-" + newIdx + "-id']");
        if (pkInp) pkInp.value = "";
        const delInp = clone.querySelector("input[name='" + prefix + "-" + newIdx + "-DELETE']");
        if (delInp) {
            delInp.checked = false;
            delInp.removeAttribute("checked");
        }
        clone.querySelectorAll('input[type="file"]').forEach(function (fi) {
            fi.value = "";
        });
        const zpoSelCopy = clone.querySelector(".name-subject-pairs__zpo-select");
        if (zpoSelCopy) {
            zpoSelCopy.selectedIndex = 0;
        }
        const zpoLinkCopy = clone.querySelector(".name-subject-pairs__zpo-open-link");
        if (zpoLinkCopy) {
            zpoLinkCopy.setAttribute("hidden", "hidden");
            zpoLinkCopy.href = "#";
        }
        const zpoHintCopy = clone.querySelector(".name-subject-pairs__zpo-hint");
        if (zpoHintCopy) {
            zpoHintCopy.textContent = "";
        }
        clone.querySelectorAll("a.pair-file-link").forEach(function (a) {
            a.remove();
        });
        clone.querySelectorAll(".name-subject-pairs__pio-row").forEach(function (row) {
            if (row.querySelector("a[href*='pio'], a[href*='xlsx']")) {
                row.innerHTML = '<small class="dash-muted">Po uložení páru</small>';
            }
        });
        const addrInp = clone.querySelector(".name-subject-pairs__fulfillment-address-input");
        if (addrInp) {
            delete addrInp.dataset.fulfillmentBound;
            delete addrInp.dataset.pairAddressEditedBound;
        }
        const addrSel = clone.querySelector(".name-subject-pairs__fulfillment-address-select");
        if (addrSel) {
            delete addrSel.dataset.pairSelectBound;
        }
        const mapBtn = clone.querySelector(".name-subject-pairs__pair-map-btn");
        if (mapBtn) {
            delete mapBtn.dataset.pairMapClickBound;
        }
        delete clone._refreshFulfillmentSelect;
    }

    function jedisSyncLabelTitlesIn(root, formEl) {
        if (!root || !formEl) return;
        root.querySelectorAll("label[for]").forEach(function (lab) {
            if (lab.hasAttribute("data-no-tooltip-sync")) return;
            const id = lab.getAttribute("for");
            if (!id) return;
            const el = document.getElementById(id);
            if (!el || el.type === "hidden") return;
            const title = (el.getAttribute("title") || "").trim();
            if (title) lab.setAttribute("title", title);
        });
    }

    function renumberPairSortOrder(list) {
        let order = 0;
        list.querySelectorAll(".name-subject-pairs__card").forEach(function (card) {
            const inp = card.querySelector('input[name$="-sort_order"]');
            if (!inp) return;
            const wasteSel = card.querySelector('select[name$="-waste_type"]');
            const suffixSel = card.querySelector('select[name$="-suffix"]');
            const idInp = card.querySelector('input[name$="-id"]');
            const deleteInp = card.querySelector('input[name$="-DELETE"]');
            const hasPersistedId = !!(idInp && (idInp.value || "").trim());
            const hasWaste = !!(wasteSel && (wasteSel.value || "").trim());
            const hasSuffix = !!(suffixSel && (suffixSel.value || "").trim());
            const isDeleting = !!(deleteInp && deleteInp.checked);
            const hasMeaningfulData = hasPersistedId || hasWaste || hasSuffix;
            if (hasMeaningfulData && !isDeleting) {
                inp.value = String(order);
                order += 1;
            } else {
                inp.value = "";
            }
        });
    }

    function syncCollapseButton(card, expanded) {
        const btn = card.querySelector("[data-pair-collapse-toggle]");
        if (!btn) return;
        btn.setAttribute("aria-expanded", expanded ? "true" : "false");
        btn.textContent = expanded ? "▾" : "▸";
    }

    function updateExceptionSlotVisibility(card) {
        const svoz = card.querySelector('input[name$="-yard_svoz_enabled"]');
        const regular = card.querySelector('input[name$="-yard_svoz_auto_assign_driver"]');
        const wrap = card.querySelector(".name-subject-pairs__exception-slot-wrap");
        if (!wrap) return;
        const show = svoz && svoz.checked && regular && !regular.checked;
        wrap.hidden = !show;
    }

    function updateSvozMatrixCardStyle(card) {
        const svoz = card.querySelector('input[name$="-yard_svoz_enabled"]');
        if (!svoz) return;
        card.classList.toggle("name-subject-pairs__card--svoz-matrix", svoz.checked);
        card.classList.toggle("name-subject-pairs__card--no-svoz-matrix", !svoz.checked);
    }

    function bindExceptionSlotVisibility(card) {
        updateExceptionSlotVisibility(card);
        updateSvozMatrixCardStyle(card);
        card.querySelectorAll(
            'input[name$="-yard_svoz_enabled"], input[name$="-yard_svoz_auto_assign_driver"]'
        ).forEach(function (inp) {
            inp.addEventListener("change", function () {
                updateExceptionSlotVisibility(card);
                if (inp.matches('input[name$="-yard_svoz_enabled"]')) {
                    updateSvozMatrixCardStyle(card);
                }
            });
        });
    }

    function parseCoord(value, fallback) {
        const normalized = String(value || "").replace(",", ".");
        const parsed = Number.parseFloat(normalized);
        return Number.isFinite(parsed) ? parsed : fallback;
    }

    function getCentralFulfillmentAddressInput() {
        const rootForm = document.querySelector("form.name-subject-form");
        if (rootForm) {
            return rootForm.querySelector("#id_fulfillment_address_value");
        }
        return document.getElementById("id_fulfillment_address_value");
    }

    function getCentralFulfillmentAddressValue() {
        const rootForm = document.querySelector("form.name-subject-form");
        if (rootForm) {
            const centralInput = rootForm.querySelector("#id_fulfillment_address_value");
            if (centralInput) {
                return (centralInput.value || "").trim();
            }
        }
        const knownEl =
            document.getElementById("known-fulfillment-addresses") ||
            document.querySelector(".name-subject-pairs #known-fulfillment-addresses");
        if (knownEl) {
            try {
                const parsed = JSON.parse(knownEl.textContent || "[]");
                if (Array.isArray(parsed) && parsed.length) {
                    return (parsed[0] || "").trim();
                }
            } catch (error) {}
        }
        const fallback = document.getElementById("id_fulfillment_address_value");
        return fallback ? (fallback.value || "").trim() : "";
    }

    function getKnownFulfillmentAddressesFromServer(pairsRoot) {
        const el =
            (pairsRoot && pairsRoot.querySelector("#known-fulfillment-addresses")) ||
            document.getElementById("known-fulfillment-addresses");
        if (!el) return [];
        try {
            const parsed = JSON.parse(el.textContent || "[]");
            return Array.isArray(parsed) ? parsed : [];
        } catch (error) {
            return [];
        }
    }

    function getCentralFulfillmentMapDefaults() {
        const latIn = document.getElementById("id_fulfillment_latitude");
        const lngIn = document.getElementById("id_fulfillment_longitude");
        const defaultsEl = document.getElementById("name-subject-app-map-defaults");
        const lat = parseCoord(latIn ? latIn.value : "", NaN);
        const lng = parseCoord(lngIn ? lngIn.value : "", NaN);
        if (Number.isFinite(lat) && Number.isFinite(lng)) {
            return { lat: lat, lng: lng };
        }
        const dl = defaultsEl ? parseCoord(defaultsEl.dataset.lat, NaN) : NaN;
        const dn = defaultsEl ? parseCoord(defaultsEl.dataset.lng, NaN) : NaN;
        return {
            lat: Number.isFinite(dl) ? dl : 49.8175,
            lng: Number.isFinite(dn) ? dn : 15.473,
        };
    }

    const PAIR_FULFILLMENT_CUSTOM = "__custom__";

    function getPairFulfillmentSelect(card) {
        return card ? card.querySelector(".name-subject-pairs__fulfillment-address-select") : null;
    }

    function getPairFulfillmentConfig(pairsRoot) {
        if (!pairsRoot) return null;
        return {
            suggestionsUrl: pairsRoot.getAttribute("data-address-suggestions-url") || "",
            geocodeUrl: pairsRoot.getAttribute("data-address-geocode-url") || "",
            reverseGeocodeUrl: pairsRoot.getAttribute("data-address-reverse-geocode-url") || "",
        };
    }

    function formatCentralOptionLabel(central) {
        const text = (central || "").trim();
        if (!text) {
            return "Adresa plnění subjektu (doplňte výše)";
        }
        return text.length > 80 ? text.slice(0, 77) + "…" : text;
    }

    function updateKnownFulfillmentAddressesJson(pairsRoot, central) {
        const el =
            (pairsRoot && pairsRoot.querySelector("#known-fulfillment-addresses")) ||
            document.getElementById("known-fulfillment-addresses");
        if (!el) return;
        let base = [];
        try {
            base = JSON.parse(el.textContent || "[]");
        } catch (error) {
            base = [];
        }
        const seen = new Set();
        const out = [];
        const centralText = (central || "").trim();
        if (centralText) {
            seen.add(centralText);
            out.push(centralText);
        }
        (base || []).forEach(function (addr) {
            const text = (addr || "").trim();
            if (!text || seen.has(text)) return;
            seen.add(text);
            out.push(text);
        });
        el.textContent = JSON.stringify(out);
    }

    function populateFulfillmentAddressSelect(select, options, central) {
        if (!select) return;
        const centralText = (central || "").trim();
        select.innerHTML = "";
        const optCentral = document.createElement("option");
        optCentral.value = "";
        optCentral.textContent = formatCentralOptionLabel(centralText);
        optCentral.title = centralText
            ? "Použije se hodnota z pole Adresa plnění v sekci Adresy subjektu: " + centralText
            : "Použije se hodnota z pole Adresa plnění výše ve formuláři";
        select.appendChild(optCentral);
        (options || []).forEach(function (addr) {
            const text = (addr || "").trim();
            if (!text || (centralText && text === centralText)) return;
            const opt = document.createElement("option");
            opt.value = text;
            opt.textContent = text.length > 80 ? text.slice(0, 77) + "…" : text;
            opt.title = text;
            select.appendChild(opt);
        });
        const optCustom = document.createElement("option");
        optCustom.value = PAIR_FULFILLMENT_CUSTOM;
        optCustom.textContent = "Jiná adresa (zadejte ručně)";
        optCustom.title = "Vlastní adresa plnění pro tento řádek F/P";
        select.appendChild(optCustom);
    }

    function syncSelectFromInput(card, list, pairsRoot) {
        const select = getPairFulfillmentSelect(card);
        const input = getPairFulfillmentInput(card);
        if (!select || !input) return;
        const central = getCentralFulfillmentAddressValue();
        const current = (input.value || "").trim();
        if (!current) {
            select.value = "";
            return;
        }
        if (current === central) {
            select.value = "";
            return;
        }
        const options = collectPairFulfillmentAddressOptions(list, null, pairsRoot);
        if (options.indexOf(current) !== -1) {
            select.value = current;
        } else {
            select.value = PAIR_FULFILLMENT_CUSTOM;
        }
    }

    function initPairFulfillmentSelectForCard(card, list, pairsRoot) {
        const select = getPairFulfillmentSelect(card);
        if (!select || select.dataset.pairSelectBound === "1") return;
        select.dataset.pairSelectBound = "1";
        const refreshOptions = function () {
            const central = getCentralFulfillmentAddressValue();
            const opts = collectPairFulfillmentAddressOptions(list, card, pairsRoot);
            populateFulfillmentAddressSelect(select, opts, central);
            syncSelectFromInput(card, list, pairsRoot);
        };
        refreshOptions();
        card._refreshFulfillmentSelect = refreshOptions;
        select.addEventListener("change", function () {
            const input = getPairFulfillmentInput(card);
            if (!input) return;
            const val = select.value;
            if (val === PAIR_FULFILLMENT_CUSTOM) {
                const formEl = pairsRoot.closest("form");
                ensurePairFulfillmentInputReady(card, formEl, list, pairsRoot, null);
                input.focus();
                return;
            }
            input.value = val;
            normalizePairFulfillmentToCentral(card);
            syncSelectFromInput(card, list, pairsRoot);
        });
    }

    function refreshAllPairFulfillmentSelects(list, pairsRoot) {
        if (!list) return;
        list.querySelectorAll(".name-subject-pairs__card").forEach(function (card) {
            if (typeof card._refreshFulfillmentSelect === "function") {
                card._refreshFulfillmentSelect();
            } else {
                initPairFulfillmentSelectForCard(card, list, pairsRoot);
            }
            syncSelectFromInput(card, list, pairsRoot);
        });
    }

    function buildPairFulfillmentHooks(formEl, list, pairsRoot) {
        return {
            getConfig: function () {
                return getPairFulfillmentConfig(pairsRoot);
            },
            getMapDefaults: function () {
                return getCentralFulfillmentMapDefaults();
            },
            getCentralAddress: function () {
                return getCentralFulfillmentAddressValue();
            },
            resolveMapCenter: function () {
                const mapDefaults = getCentralFulfillmentMapDefaults();
                const latIn = document.getElementById("id_fulfillment_latitude");
                const lngIn = document.getElementById("id_fulfillment_longitude");
                const lat = parseCoord(latIn ? latIn.value : "", NaN);
                const lng = parseCoord(lngIn ? lngIn.value : "", NaN);
                if (Number.isFinite(lat) && Number.isFinite(lng)) {
                    return { lat: lat, lng: lng };
                }
                return { lat: mapDefaults.lat, lng: mapDefaults.lng };
            },
            onAddressInput: function (card) {
                const select = getPairFulfillmentSelect(card);
                const input = getPairFulfillmentInput(card);
                if (select && input && (input.value || "").trim()) {
                    select.value = PAIR_FULFILLMENT_CUSTOM;
                }
                syncSelectFromInput(card, list, pairsRoot);
            },
            onAddressEdited: function (card) {
                normalizePairFulfillmentToCentral(card);
                syncSelectFromInput(card, list, pairsRoot);
            },
            onAfterMapSave: function (card) {
                refreshAllPairFulfillmentSelects(list, pairsRoot);
            },
            onCardInit: function (card) {
                syncPairFulfillmentPlaceholder(card);
            },
        };
    }

    function bindPairFulfillmentInteractionDelegation(pairsRoot, formEl, list, config) {
        if (!pairsRoot || pairsRoot.dataset.pairFulfillmentInteraction === "1") return;
        pairsRoot.dataset.pairFulfillmentInteraction = "1";
        pairsRoot.addEventListener("focusin", function (e) {
            const input = e.target.closest(".name-subject-pairs__fulfillment-address-input");
            if (!input || !pairsRoot.contains(input)) return;
            const card = input.closest(".name-subject-pairs__card");
            if (card) ensurePairFulfillmentInputReady(card, formEl, list, pairsRoot, config);
        });
        pairsRoot.addEventListener("input", function (e) {
            const input = e.target.closest(".name-subject-pairs__fulfillment-address-input");
            if (!input || !pairsRoot.contains(input)) return;
            const card = input.closest(".name-subject-pairs__card");
            if (!card) return;
            const select = getPairFulfillmentSelect(card);
            if (select && (input.value || "").trim()) {
                select.value = PAIR_FULFILLMENT_CUSTOM;
            }
            ensurePairFulfillmentInputReady(card, formEl, list, pairsRoot, config);
        });
    }

    function ensurePairFulfillmentInputReady(card, formEl, list, pairsRoot, config) {
        if (!card) return;
        const pairsRootEl = pairsRoot || (formEl ? formEl.querySelector(".name-subject-pairs") : null);
        const listEl = list || (formEl ? formEl.querySelector(".name-subject-pairs__list") : null);
        const cfg = config || getPairFulfillmentConfig(pairsRootEl);
        if (!listEl || !cfg || !pairsRootEl) return;
        if (!window.PairFulfillmentAddressField) {
            console.warn("PairFulfillmentAddressField: chybí modul pair_fulfillment_address_field.js");
            return;
        }
        const hooks = buildPairFulfillmentHooks(formEl, listEl, pairsRootEl);
        window.PairFulfillmentAddressField.initCard(card, hooks);
        const input = getPairFulfillmentInput(card);
        if (input && input.dataset.fulfillmentBound !== "1") {
            console.warn("Pair fulfillment address field failed to bind:", input.id || input.name);
        }
    }

    function getPairFulfillmentInput(card) {
        if (
            window.PairFulfillmentAddressField &&
            typeof window.PairFulfillmentAddressField.getPairInput === "function"
        ) {
            return window.PairFulfillmentAddressField.getPairInput(card);
        }
        return card ? card.querySelector(".name-subject-pairs__fulfillment-address-input") : null;
    }

    function collectPairFulfillmentAddressOptions(list, excludeCard, pairsRoot) {
        const seen = new Set();
        const out = [];
        getKnownFulfillmentAddressesFromServer(pairsRoot).forEach(function (value) {
            const text = (value || "").trim();
            if (!text || seen.has(text)) return;
            seen.add(text);
            out.push(text);
        });
        const central = getCentralFulfillmentAddressValue();
        if (central && !seen.has(central)) {
            seen.add(central);
            out.unshift(central);
        }
        if (!list) return out;
        list.querySelectorAll(".name-subject-pairs__card").forEach(function (card) {
            if (excludeCard && card === excludeCard) return;
            const value = (getPairFulfillmentInput(card)?.value || "").trim();
            if (!value || seen.has(value)) return;
            seen.add(value);
            out.push(value);
        });
        return out;
    }

    function syncPairFulfillmentPlaceholder(card, centralValue) {
        const input = getPairFulfillmentInput(card);
        if (!input) return;
        const central = centralValue !== undefined ? centralValue : getCentralFulfillmentAddressValue();
        if (!(input.value || "").trim() && central) {
            input.setAttribute("placeholder", "Centrální: " + central);
        } else {
            input.setAttribute(
                "placeholder",
                "Centrální adresa subjektu (nebo vyberte / zadejte jinou)"
            );
        }
    }

    function normalizePairFulfillmentToCentral(card, centralValue) {
        const input = getPairFulfillmentInput(card);
        if (!input) return;
        const central = centralValue !== undefined ? centralValue : getCentralFulfillmentAddressValue();
        const current = (input.value || "").trim();
        if (central && current === central) {
            input.value = "";
        }
        syncPairFulfillmentPlaceholder(card, central);
    }

    function syncPairFulfillmentUi(list, pairsRoot) {
        if (!list) return;
        const central = getCentralFulfillmentAddressValue();
        updateKnownFulfillmentAddressesJson(pairsRoot, central);
        list.querySelectorAll(".name-subject-pairs__card").forEach(function (card) {
            normalizePairFulfillmentToCentral(card, central);
            syncPairFulfillmentPlaceholder(card, central);
            syncSelectFromInput(card, list, pairsRoot);
        });
        refreshAllPairFulfillmentSelects(list, pairsRoot);
    }

    function bindCentralFulfillmentWatcher(list, pairsRoot) {
        const centralInput = getCentralFulfillmentAddressInput();
        if (!centralInput || centralInput.dataset.pairFulfillmentWatcher === "1") return;
        centralInput.dataset.pairFulfillmentWatcher = "1";
        const refresh = function () {
            const central = getCentralFulfillmentAddressValue();
            updateKnownFulfillmentAddressesJson(pairsRoot, central);
            syncPairFulfillmentUi(list, pairsRoot);
        };
        centralInput.addEventListener("change", refresh);
        centralInput.addEventListener("blur", refresh);
        centralInput.addEventListener("input", refresh);
    }

    function jedisInitPairFulfillmentForCard(card, formEl) {
        if (!card || !formEl) return;
        const pairsRoot = formEl.querySelector(".name-subject-pairs");
        const list = formEl.querySelector(".name-subject-pairs__list");
        if (!list || !pairsRoot) return;
        initPairFulfillmentSelectForCard(card, list, pairsRoot);
        syncSelectFromInput(card, list, pairsRoot);
        ensurePairFulfillmentInputReady(card, formEl, list, pairsRoot, null);
    }

    function jedisInitPairFulfillmentCore(formEl) {
        if (!formEl) return false;
        const pairsRoot = formEl.querySelector(".name-subject-pairs");
        const list = formEl.querySelector(".name-subject-pairs__list");
        if (!pairsRoot || !list) return false;
        const config = getPairFulfillmentConfig(pairsRoot) || {
            suggestionsUrl: "",
            geocodeUrl: "",
            reverseGeocodeUrl: "",
        };
        list.querySelectorAll(".name-subject-pairs__card").forEach(function (card) {
            initPairFulfillmentSelectForCard(card, list, pairsRoot);
        });
        bindPairFulfillmentInteractionDelegation(pairsRoot, formEl, list, config);
        bindCentralFulfillmentWatcher(list, pairsRoot);
        syncPairFulfillmentUi(list, pairsRoot);
        if (window.PairFulfillmentAddressField) {
            const hooks = buildPairFulfillmentHooks(formEl, list, pairsRoot);
            window.PairFulfillmentAddressField.initForm(formEl, hooks);
        } else {
            console.warn("PairFulfillmentAddressField: chybí modul pair_fulfillment_address_field.js");
        }
        return true;
    }

    window.jedisInitPairFulfillmentSafe = function (formEl) {
        if (!formEl) return;
        function boot() {
            if (jedisInitPairFulfillmentCore(formEl)) return;
            let attempts = 0;
            const retry = function () {
                attempts += 1;
                if (jedisInitPairFulfillmentCore(formEl) || attempts >= 20) return;
                setTimeout(retry, 50);
            };
            retry();
        }
        if (document.readyState === "loading") {
            document.addEventListener("DOMContentLoaded", boot);
        } else {
            boot();
        }
    };

    /**
     * @param {HTMLFormElement} formEl formulář obsahující .name-subject-pairs__list
     */
    window.jedisInitNameSubjectPairsFormset = function (formEl) {
        if (!formEl) return;
        const list = formEl.querySelector(".name-subject-pairs__list");
        if (!list) return;
        const pairsRoot = formEl.querySelector(".name-subject-pairs");
        const formsetPrefix = pairsRoot ? pairsRoot.getAttribute("data-formset-prefix") : null;
        if (!formsetPrefix) return;

        list.querySelectorAll(".name-subject-pairs__card").forEach(function (card) {
            syncCollapseButton(card, false);
            bindExceptionSlotVisibility(card);
        });

        list.addEventListener("change", function (e) {
            const card = e.target.closest(".name-subject-pairs__card");
            if (!card || !list.contains(card)) return;
            if (e.target.matches(".name-subject-pairs__fulfillment-address-input")) {
                normalizePairFulfillmentToCentral(card);
                syncSelectFromInput(card, list, pairsRoot);
                return;
            }
            if (
                e.target.matches('input[name$="-yard_svoz_enabled"]') ||
                e.target.matches('input[name$="-yard_svoz_auto_assign_driver"]')
            ) {
                updateExceptionSlotVisibility(card);
                if (e.target.matches('input[name$="-yard_svoz_enabled"]')) {
                    updateSvozMatrixCardStyle(card);
                }
            }
        });

        list.addEventListener("click", function (e) {
            const copyBtn = e.target.closest("[data-copy-pair]");
            if (copyBtn && list.contains(copyBtn)) {
                e.preventDefault();
                if (!formsetPrefix || !window.jedisInitWasteCombosIn || !window.jedisStripWasteComboWrappers) return;
                const srcCard = copyBtn.closest(".name-subject-pairs__card");
                if (!srcCard) return;
                const oldIdx = getCardFormIndex(srcCard, formsetPrefix);
                if (oldIdx === null) return;
                const totalEl = formEl.querySelector('[name="' + formsetPrefix + '-TOTAL_FORMS"]');
                const maxEl = formEl.querySelector('[name="' + formsetPrefix + '-MAX_NUM_FORMS"]');
                if (!totalEl) return;
                const newIdx = parseInt(totalEl.value, 10);
                const formsetMax = maxEl ? parseInt(maxEl.value, 10) : 50;
                if (newIdx >= formsetMax) {
                    alert("Dosáhli jste maximálního počtu párů (" + formsetMax + ").");
                    return;
                }
                const clone = srcCard.cloneNode(true);
                window.jedisStripWasteComboWrappers(clone);
                reindexClonedPairCard(clone, formsetPrefix, oldIdx, newIdx);
                clearCopiedPairMetadata(clone, formsetPrefix, newIdx);
                list.appendChild(clone);
                totalEl.value = String(newIdx + 1);
                clone.classList.add("is-collapsed");
                syncCollapseButton(clone, false);
                window.jedisInitWasteCombosIn(clone);
                jedisSyncLabelTitlesIn(clone, formEl);
                bindExceptionSlotVisibility(clone);
                updateSvozMatrixCardStyle(clone);
                jedisInitPairFulfillmentForCard(clone, formEl);
                syncPairFulfillmentUi(list, pairsRoot);
                renumberPairSortOrder(list);
                clone.scrollIntoView({ behavior: "smooth", block: "nearest" });
                return;
            }
            const btn = e.target.closest("[data-pair-collapse-toggle]");
            if (!btn || !list.contains(btn)) return;
            const card = btn.closest(".name-subject-pairs__card");
            if (!card) return;
            const collapsed = card.classList.toggle("is-collapsed");
            syncCollapseButton(card, !collapsed);
        });

        let dragGroup = null;
        list.addEventListener("dragstart", function (e) {
            const h = e.target.closest(".name-subject-pairs__handle");
            if (!h || !list.contains(h)) return;
            dragGroup = h.closest(".name-subject-pairs__card");
            if (!dragGroup) return;
            e.dataTransfer.effectAllowed = "move";
            e.dataTransfer.setData("text/plain", "row");
            dragGroup.classList.add("name-subject-pairs__card--dragging");
        });
        list.addEventListener("dragend", function () {
            if (dragGroup) dragGroup.classList.remove("name-subject-pairs__card--dragging");
            dragGroup = null;
            renumberPairSortOrder(list);
        });
        list.addEventListener("dragover", function (e) {
            if (!dragGroup) return;
            e.preventDefault();
            e.dataTransfer.dropEffect = "move";
            const refCard = e.target.closest(".name-subject-pairs__card");
            if (!refCard || refCard === dragGroup || !list.contains(refCard)) return;
            const rect = refCard.getBoundingClientRect();
            const before = e.clientY < rect.top + rect.height / 2;
            list.insertBefore(dragGroup, before ? refCard : refCard.nextSibling);
        });

        formEl.addEventListener(
            "submit",
            function () {
                renumberPairSortOrder(list);
            },
            true
        );

        renumberPairSortOrder(list);
    };
})();
