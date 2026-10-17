(function () {
    function appMapFallbackCoords() {
        const modal = document.getElementById("map-modal");
        if (!modal) {
            return { lat: 49.8175, lng: 15.473 };
        }
        const dl = Number.parseFloat(modal.dataset.defaultLat || "");
        const dn = Number.parseFloat(modal.dataset.defaultLng || "");
        return {
            lat: Number.isFinite(dl) ? dl : 49.8175,
            lng: Number.isFinite(dn) ? dn : 15.473,
        };
    }

    function normalizeAddress(value) {
        let text = (value || "").trim().replace(/\s+/g, " ");
        if (!text) return "";
        const cpCity = text.match(/^(?:č\.?\s*p\.?\s*)?(\d+[a-zA-Z]?(?:\/\d+)?)\s*,\s*(?:(?:\d{3}\s?\d{2})\s+)?(.+)$/i);
        if (cpCity) {
            const number = cpCity[1].trim();
            const city = cpCity[2].replace(/^\d{3}\s?\d{2}\s+/, "").trim();
            if (city && number) return `${city}, ${number}, ${city}`;
        }
        const onlyCityAndNumber = text.match(/^([^,]+),\s*(\d+[a-zA-Z]?(?:\/\d+)?)$/);
        if (onlyCityAndNumber) {
            const city = onlyCityAndNumber[1].trim();
            const number = onlyCityAndNumber[2].trim();
            return `${city}, ${number}, ${city}`;
        }
        text = text.replace(/\s*,\s*/g, ", ").replace(/ ,/g, ",").replace(/,,/g, ",");
        const strict = text.match(/^([^,]+),\s*(\d+[a-zA-Z]?(?:\/\d+)?),\s*([^,]+)$/);
        if (strict) {
            return `${strict[1].trim()}, ${strict[2].trim()}, ${strict[3].trim()}`;
        }
        let m = text.match(/^(\d+[a-zA-Z]?)\s+(.+?)(?:\s+\d{5})?$/);
        if (m) {
            return m[2].includes(",")
                ? m[2].replace(/\s*,\s*/g, ", ").trim()
                : `${m[2].trim()}, ${m[1].trim()}`;
        }
        m = text.match(/^(.+?)\s+(\d+[a-zA-Z]?(?:\/\d+)?)(?:\s+\d{5})?$/);
        if (m) {
            const source = m[1].trim();
            if (source.includes(",")) {
                const parts = source.split(",").map((p) => p.trim()).filter(Boolean);
                if (parts.length >= 2) {
                    return `${parts[0]}, ${m[2].trim()}, ${parts.slice(1).join(" ")}`;
                }
            }
            return `${source}, ${m[2].trim()}, ${source}`;
        }
        return text.replace(/(^[,\s]+|[,\s]+$)/g, "");
    }

    function parseCoord(value, fallback) {
        const normalized = String(value || "").replace(",", ".");
        const parsed = Number.parseFloat(normalized);
        return Number.isFinite(parsed) ? parsed : fallback;
    }

    function hasValidCoords(lat, lng) {
        return Number.isFinite(lat) && Number.isFinite(lng);
    }

    function clearCoordInputs(latInput, lngInput) {
        if (latInput) latInput.value = "";
        if (lngInput) lngInput.value = "";
    }

    async function geocodeAddressToCoords(geocodeUrl, addressText, minChars) {
        if (!geocodeUrl || addressText.length < minChars) {
            return null;
        }
        try {
            const geocodeResp = await fetch(`${geocodeUrl}?q=${encodeURIComponent(addressText)}`);
            const geocodePayload = await geocodeResp.json();
            if (!geocodePayload.ok || !geocodePayload.data) {
                return null;
            }
            const lat = parseCoord(geocodePayload.data.lat, NaN);
            const lng = parseCoord(geocodePayload.data.lng, NaN);
            return hasValidCoords(lat, lng) ? { lat, lng } : null;
        } catch (error) {
            return null;
        }
    }

    function init(config) {
        const input = config.inputEl || (config.inputId ? document.getElementById(config.inputId) : null);
        if (!input) return;

        const datalist =
            config.datalistEl || (config.datalistId ? document.getElementById(config.datalistId) : null);
        const mapBtn =
            config.mapButtonEl || (config.mapButtonId ? document.getElementById(config.mapButtonId) : null);
        const latInput = config.latInputEl
            || (config.latInputId ? document.getElementById(config.latInputId) : null);
        const lngInput = config.lngInputEl
            || (config.lngInputId ? document.getElementById(config.lngInputId) : null);
        const minChars = config.minChars || 2;
        const geocodeMinChars = config.geocodeMinChars || minChars;
        const debounceMs = config.debounceMs || 300;
        const preferredCity = config.preferredCity || "";
        let debounceTimer = null;
        let contextDebounceTimer = null;

        function emitAddressContext() {
            if (typeof config.onAddressChange !== "function") return;
            clearTimeout(contextDebounceTimer);
            contextDebounceTimer = setTimeout(() => {
                config.onAddressChange({
                    address: (input.value || "").trim(),
                    lat: latInput ? (latInput.value || "").trim() : "",
                    lng: lngInput ? (lngInput.value || "").trim() : "",
                });
            }, 250);
        }

        function resolveStaticSuggestions() {
            if (typeof config.staticSuggestions === "function") {
                return config.staticSuggestions() || [];
            }
            return config.staticSuggestions || [];
        }

        function mergeSuggestions(query, apiValues) {
            const q = (query || "").trim().toLowerCase();
            const staticOnes = resolveStaticSuggestions()
                .map((value) => (value || "").trim())
                .filter(Boolean);
            const staticFiltered = q
                ? staticOnes.filter((value) => value.toLowerCase().includes(q))
                : staticOnes;
            const seen = new Set();
            const out = [];
            staticFiltered.concat(apiValues || []).forEach((value) => {
                const text = (value || "").trim();
                if (!text || seen.has(text)) return;
                seen.add(text);
                out.push(text);
            });
            return out;
        }

        function fillDatalist(values) {
            if (!datalist) return;
            datalist.innerHTML = "";
            (values || []).forEach((value) => {
                const option = document.createElement("option");
                option.value = value;
                datalist.appendChild(option);
            });
        }

        async function fetchSuggestions(query) {
            const trimmed = (query || "").trim();
            if (!config.suggestionsUrl || !trimmed || trimmed.length < minChars) {
                fillDatalist(mergeSuggestions(trimmed, []));
                return;
            }
            const cityParam = preferredCity ? `&preferred_city=${encodeURIComponent(preferredCity)}` : "";
            try {
                const response = await fetch(
                    `${config.suggestionsUrl}?q=${encodeURIComponent(trimmed)}${cityParam}`
                );
                if (!response.ok) {
                    console.warn("Address suggestions request failed:", response.status);
                    fillDatalist(mergeSuggestions(trimmed, []));
                    return;
                }
                const payload = await response.json();
                fillDatalist(mergeSuggestions(trimmed, payload.data || []));
            } catch (error) {
                console.warn("Address suggestions request error:", error);
                fillDatalist(mergeSuggestions(trimmed, []));
            }
        }

        if (datalist) {
            const listId = datalist.id || config.datalistId;
            if (listId) {
                input.setAttribute("list", listId);
            }
        }

        function resolveGeocodeQuery() {
            const own = (input.value || "").trim();
            if (own) return own;
            if (typeof config.resolveGeocodeAddress === "function") {
                return (config.resolveGeocodeAddress() || "").trim();
            }
            return "";
        }

        input.addEventListener("input", () => {
            clearCoordInputs(latInput, lngInput);
            clearTimeout(debounceTimer);
            debounceTimer = setTimeout(() => {
                fetchSuggestions(input.value);
            }, debounceMs);
            if (typeof config.onAddressInput === "function") {
                config.onAddressInput(input.value);
            }
        });

        if (config.normalizeOnBlur) {
            input.addEventListener("blur", () => {
                input.value = normalizeAddress(input.value);
                emitAddressContext();
                if (typeof config.onAddressInput === "function") {
                    config.onAddressInput(input.value);
                }
            });
        }

        if (config.prefillStaticOnFocus) {
            input.addEventListener("focus", () => {
                fillDatalist(mergeSuggestions(input.value, []));
                if (config.suggestionsUrl && (input.value || "").trim().length >= minChars) {
                    fetchSuggestions(input.value);
                }
            });
        } else if (config.prefillSuggestionsOnFocus && preferredCity) {
            input.addEventListener("focus", () => {
                if (!input.value) {
                    fetchSuggestions(preferredCity);
                }
            });
        }

        if (mapBtn) {
            mapBtn.addEventListener("click", async () => {
                if (!window.MapModal) {
                    alert("Mapa ještě není připravená.");
                    return;
                }
                const mapModalEl = document.getElementById("map-modal");
                let restoredZIndex = null;
                if (config.elevateMapZIndex && mapModalEl) {
                    restoredZIndex = mapModalEl.style.zIndex || "";
                    mapModalEl.style.zIndex = "10050";
                }
                const restoreMapZIndex = () => {
                    if (config.elevateMapZIndex && mapModalEl) {
                        mapModalEl.style.zIndex = restoredZIndex || "";
                    }
                };
                const fb = appMapFallbackCoords();
                let existingLat = parseCoord(latInput ? latInput.value : config.defaultLat, NaN);
                let existingLng = parseCoord(lngInput ? lngInput.value : config.defaultLng, NaN);
                if (!hasValidCoords(existingLat, existingLng) && typeof config.resolveMapCenter === "function") {
                    const center = config.resolveMapCenter();
                    if (center && hasValidCoords(center.lat, center.lng)) {
                        existingLat = center.lat;
                        existingLng = center.lng;
                    }
                }
                let lat = hasValidCoords(existingLat, existingLng)
                    ? existingLat
                    : parseCoord(config.defaultLat, fb.lat);
                let lng = hasValidCoords(existingLat, existingLng)
                    ? existingLng
                    : parseCoord(config.defaultLng, fb.lng);

                const addressText = resolveGeocodeQuery();
                if (!hasValidCoords(existingLat, existingLng)) {
                    const geocoded = await geocodeAddressToCoords(config.geocodeUrl, addressText, geocodeMinChars);
                    if (geocoded) {
                        lat = geocoded.lat;
                        lng = geocoded.lng;
                        if (latInput) latInput.value = lat.toFixed(7);
                        if (lngInput) lngInput.value = lng.toFixed(7);
                    }
                }

                window.MapModal.open({
                    lat,
                    lng,
                    onClose: restoreMapZIndex,
                    onSave: async (point, meta) => {
                        if (latInput) latInput.value = point.lat.toFixed(7);
                        if (lngInput) lngInput.value = point.lng.toFixed(7);
                        const moved = !meta || meta.moved !== false;
                        const addressEmpty = !((input.value || "").trim());
                        if (config.reverseGeocodeUrl && (moved || addressEmpty)) {
                            try {
                                const reverseResp = await fetch(
                                    `${config.reverseGeocodeUrl}?lat=${encodeURIComponent(point.lat)}&lng=${encodeURIComponent(point.lng)}`
                                );
                                const reversePayload = await reverseResp.json();
                                if (reversePayload.ok && reversePayload.data && reversePayload.data.label) {
                                    input.value = reversePayload.data.label;
                                }
                            } catch (error) {}
                        }
                        restoreMapZIndex();
                        emitAddressContext();
                        if (typeof config.onAddressInput === "function") {
                            config.onAddressInput(input.value);
                        }
                    },
                });
            });
        }

        if (latInput) latInput.addEventListener("change", emitAddressContext);
        if (lngInput) lngInput.addEventListener("change", emitAddressContext);
    }

    async function bootstrapCoordsFromAddress(config) {
        const input = document.getElementById(config.inputId);
        const latInput = config.latInputId ? document.getElementById(config.latInputId) : null;
        const lngInput = config.lngInputId ? document.getElementById(config.lngInputId) : null;
        if (!input || !latInput || !lngInput) return;
        const addressText = (input.value || "").trim();
        if (!addressText || (latInput.value || "").trim() || (lngInput.value || "").trim()) {
            return;
        }
        const geocoded = await geocodeAddressToCoords(
            config.geocodeUrl,
            addressText,
            config.minChars || 2
        );
        if (!geocoded) return;
        latInput.value = geocoded.lat.toFixed(7);
        lngInput.value = geocoded.lng.toFixed(7);
    }

    function buildNameSubjectFulfillmentDefaults() {
        return {
            minChars: 3,
            geocodeMinChars: 3,
            debounceMs: 300,
            normalizeOnBlur: true,
            prefillStaticOnFocus: false,
            elevateMapZIndex: true,
        };
    }

    function initNameSubjectFulfillmentField(config) {
        const merged = Object.assign({}, buildNameSubjectFulfillmentDefaults(), config || {});
        return init(merged);
    }

    window.FulfillmentAddressField = {
        init,
        initNameSubjectFulfillmentField,
        buildNameSubjectFulfillmentDefaults,
        bootstrapCoordsFromAddress,
        clearCoordInputs,
    };
})();
