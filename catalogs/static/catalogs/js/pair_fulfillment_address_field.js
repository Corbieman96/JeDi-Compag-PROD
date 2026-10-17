/**
 * Adresa plnění u řádku F/P — našeptávač (3+ znaky) a výběr z mapy (MapModal).
 */
(function () {
    const INPUT_CLASS = "name-subject-pairs__fulfillment-address-input";
    const CUSTOM_VALUE = "__custom__";

    function parseCoord(value, fallback) {
        const normalized = String(value || "").replace(",", ".");
        const parsed = Number.parseFloat(normalized);
        return Number.isFinite(parsed) ? parsed : fallback;
    }

    async function geocodeAddressToCoords(geocodeUrl, addressText, minChars) {
        if (!geocodeUrl || addressText.length < minChars) return null;
        try {
            const geocodeResp = await fetch(geocodeUrl + "?q=" + encodeURIComponent(addressText));
            const geocodePayload = await geocodeResp.json();
            if (!geocodePayload.ok || !geocodePayload.data) return null;
            const lat = parseCoord(geocodePayload.data.lat, NaN);
            const lng = parseCoord(geocodePayload.data.lng, NaN);
            return Number.isFinite(lat) && Number.isFinite(lng) ? { lat: lat, lng: lng } : null;
        } catch (error) {
            return null;
        }
    }

    function resolvePairCards(rootEl) {
        if (!rootEl) return [];
        if (rootEl.classList && rootEl.classList.contains("name-subject-pairs__card")) {
            return [rootEl];
        }
        return Array.prototype.slice.call(rootEl.querySelectorAll(".name-subject-pairs__card"));
    }

    function ensureInputClass(input) {
        if (input && !input.classList.contains(INPUT_CLASS)) {
            input.classList.add(INPUT_CLASS);
        }
    }

    function getPairInput(card) {
        if (!card) return null;

        let input = card.querySelector("." + INPUT_CLASS);
        if (input) return input;

        input = card.querySelector('input[name$="-fulfillment_address_value"]');
        if (input) {
            ensureInputClass(input);
            return input;
        }

        const mapBtn = card.querySelector(".name-subject-pairs__pair-map-btn");
        if (mapBtn && mapBtn.id && mapBtn.id.endsWith("-map-btn")) {
            input = document.getElementById(mapBtn.id.slice(0, -"-map-btn".length));
            if (input && card.contains(input)) {
                ensureInputClass(input);
                return input;
            }
        }

        const row = card.querySelector(".name-subject-pairs__card-head-address-row");
        if (row) {
            input = row.querySelector('input:not([type="hidden"])');
            if (input) {
                ensureInputClass(input);
                return input;
            }
        }

        return null;
    }

    function ensureCustomFulfillmentMode(card) {
        const select = card.querySelector(".name-subject-pairs__fulfillment-address-select");
        if (select) {
            select.value = CUSTOM_VALUE;
        }
    }

    function notifyAddressChanged(card, hooks, fromMap) {
        if (typeof hooks.onAddressInput === "function") {
            hooks.onAddressInput(card);
        }
        if (fromMap && typeof hooks.onAddressEdited === "function") {
            hooks.onAddressEdited(card);
        }
        if (fromMap && typeof hooks.onAfterMapSave === "function") {
            hooks.onAfterMapSave(card);
        }
    }

    async function openMapForCard(card, hooks) {
        const input = getPairInput(card);
        if (!input || !hooks) return;
        if (!window.MapModal) {
            alert("Mapa ještě není připravená.");
            return;
        }
        const mapModalEl = document.getElementById("map-modal");
        if (!mapModalEl) {
            alert("Mapa ještě není připravená.");
            return;
        }

        const config = typeof hooks.getConfig === "function" ? hooks.getConfig() || {} : {};
        let restoredZIndex = mapModalEl.style.zIndex || "";
        mapModalEl.style.zIndex = "10050";
        const restoreMapZIndex = function () {
            mapModalEl.style.zIndex = restoredZIndex || "";
        };

        const mapDefaults =
            typeof hooks.getMapDefaults === "function"
                ? hooks.getMapDefaults()
                : { lat: 49.8175, lng: 15.473 };
        let lat = NaN;
        let lng = NaN;
        if (typeof hooks.resolveMapCenter === "function") {
            const center = hooks.resolveMapCenter();
            if (center && Number.isFinite(center.lat) && Number.isFinite(center.lng)) {
                lat = center.lat;
                lng = center.lng;
            }
        }
        if (!Number.isFinite(lat) || !Number.isFinite(lng)) {
            lat = mapDefaults.lat;
            lng = mapDefaults.lng;
        }

        const ownAddress = (input.value || "").trim();
        const centralAddress =
            typeof hooks.getCentralAddress === "function" ? (hooks.getCentralAddress() || "").trim() : "";
        const addressText = ownAddress || centralAddress;
        if (addressText && config.geocodeUrl) {
            const geocoded = await geocodeAddressToCoords(config.geocodeUrl, addressText, 3);
            if (geocoded) {
                lat = geocoded.lat;
                lng = geocoded.lng;
            }
        }

        window.MapModal.open({
            lat: lat,
            lng: lng,
            onClose: restoreMapZIndex,
            onSave: async function (point, meta) {
                const moved = !meta || meta.moved !== false;
                const addressEmpty = !((input.value || "").trim());
                if (config.reverseGeocodeUrl && (moved || addressEmpty)) {
                    try {
                        const reverseResp = await fetch(
                            config.reverseGeocodeUrl +
                                "?lat=" +
                                encodeURIComponent(point.lat) +
                                "&lng=" +
                                encodeURIComponent(point.lng)
                        );
                        const reversePayload = await reverseResp.json();
                        if (reversePayload.ok && reversePayload.data && reversePayload.data.label) {
                            input.value = reversePayload.data.label;
                        }
                    } catch (error) {}
                }
                notifyAddressChanged(card, hooks, true);
                restoreMapZIndex();
            },
        });
    }

    function bindMapButtonForCard(card, hooks) {
        const mapBtn = card.querySelector(".name-subject-pairs__pair-map-btn");
        if (!mapBtn || mapBtn.dataset.pairMapClickBound === "1") return;
        mapBtn.dataset.pairMapClickBound = "1";
        mapBtn.type = "button";
        mapBtn.addEventListener("click", function (e) {
            e.preventDefault();
            e.stopPropagation();
            ensureCustomFulfillmentMode(card);
            initSuggestForCard(card, hooks);
            void openMapForCard(card, hooks);
        });
    }

    function initSuggestForCard(card, hooks) {
        if (!card || !hooks) return;
        const config = typeof hooks.getConfig === "function" ? hooks.getConfig() : null;
        if (!config) return;

        const input = getPairInput(card);
        if (!input || input.dataset.fulfillmentBound === "1") return;

        const datalist = card.querySelector(".name-subject-pairs__pair-fulfillment-datalist");
        const datalistId = datalist ? datalist.id || input.id + "-datalist" : "";
        if (datalist && !datalist.id) {
            datalist.id = datalistId;
        }

        const mapBtn = card.querySelector(".name-subject-pairs__pair-map-btn");
        const mapButtonId = mapBtn ? mapBtn.id || input.id + "-map-btn" : "";
        if (mapBtn && !mapBtn.id) {
            mapBtn.id = mapButtonId;
        }

        const mapDefaults =
            typeof hooks.getMapDefaults === "function"
                ? hooks.getMapDefaults()
                : { lat: 49.8175, lng: 15.473 };

        input.dataset.fulfillmentBound = "1";

        if (window.FulfillmentAddressField) {
            const initField = window.FulfillmentAddressField.initNameSubjectFulfillmentField
                ? window.FulfillmentAddressField.initNameSubjectFulfillmentField.bind(
                      window.FulfillmentAddressField
                  )
                : window.FulfillmentAddressField.init.bind(window.FulfillmentAddressField);
            initField({
                inputEl: input,
                datalistEl: datalist,
                inputId: input.id,
                datalistId: datalistId,
                suggestionsUrl: config.suggestionsUrl,
                geocodeUrl: config.geocodeUrl,
                reverseGeocodeUrl: config.reverseGeocodeUrl,
                defaultLat: String(mapDefaults.lat),
                defaultLng: String(mapDefaults.lng),
                resolveGeocodeAddress: function () {
                    const own = (input.value || "").trim();
                    if (own) return own;
                    return typeof hooks.getCentralAddress === "function"
                        ? hooks.getCentralAddress() || ""
                        : "";
                },
                resolveMapCenter:
                    typeof hooks.resolveMapCenter === "function" ? hooks.resolveMapCenter : undefined,
                onAddressInput: function () {
                    notifyAddressChanged(card, hooks, false);
                },
                onAddressChange: function () {
                    if (typeof hooks.onAddressEdited === "function") {
                        hooks.onAddressEdited(card);
                    }
                },
            });
        }

        if (!input.dataset.pairAddressEditedBound) {
            input.dataset.pairAddressEditedBound = "1";
            const onAddressEdited = function () {
                if (typeof hooks.onAddressEdited === "function") {
                    hooks.onAddressEdited(card);
                }
            };
            input.addEventListener("change", onAddressEdited);
            input.addEventListener("blur", onAddressEdited);
        }

        if (typeof hooks.onCardInit === "function") {
            hooks.onCardInit(card);
        }
    }

    function initCard(card, hooks) {
        bindMapButtonForCard(card, hooks);
        initSuggestForCard(card, hooks);
    }

    function initForm(formEl, hooks) {
        if (!formEl || !hooks) return false;
        const pairsRoot = formEl.querySelector(".name-subject-pairs");
        const list = formEl.querySelector(".name-subject-pairs__list");
        if (!pairsRoot || !list) return false;

        pairsRoot._jedisPairFulfillmentHooks = hooks;
        resolvePairCards(list).forEach(function (card) {
            initCard(card, hooks);
        });
        return true;
    }

    window.PairFulfillmentAddressField = {
        getPairInput: getPairInput,
        initForm: initForm,
        initCard: initCard,
        openMapForCard: openMapForCard,
    };
})();
