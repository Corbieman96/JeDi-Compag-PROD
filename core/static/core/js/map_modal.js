(function () {
    let map;
    let marker;
    let selected = null;
    let activeCallback = null;
    let activeCloseCallback = null;
    let initialPoint = null;

    function pointMoved(point) {
        if (!initialPoint || !point) return false;
        const dLat = Math.abs(point.lat - initialPoint.lat);
        const dLng = Math.abs(point.lng - initialPoint.lng);
        return dLat > 0.00002 || dLng > 0.00002;
    }

    const modal = document.getElementById("map-modal");
    const closeBtn = document.getElementById("map-modal-close");
    const saveBtn = document.getElementById("map-modal-save");
    const mapRoot = document.getElementById("map-modal-root");
    const fallback = document.getElementById("map-modal-fallback");
    const fallbackLat = document.getElementById("map-modal-lat");
    const fallbackLng = document.getElementById("map-modal-lng");

    function hasLeaflet() {
        return typeof window.L !== "undefined" && mapRoot;
    }

    function scheduleMapResize() {
        if (!map) return;
        requestAnimationFrame(() => {
            map.invalidateSize();
            requestAnimationFrame(() => {
                map.invalidateSize();
            });
        });
    }

    function ensureMap(lat, lng) {
        if (!hasLeaflet()) {
            if (mapRoot) {
                mapRoot.style.display = "none";
            }
            if (fallback) {
                fallback.style.display = "block";
            }
            if (fallbackLat) fallbackLat.value = Number(lat).toFixed(7);
            if (fallbackLng) fallbackLng.value = Number(lng).toFixed(7);
            selected = { lat, lng };
            return;
        }
        if (mapRoot) {
            mapRoot.style.display = "block";
        }
        if (fallback) {
            fallback.style.display = "none";
        }
        if (!map) {
            map = L.map("map-modal-root").setView([lat, lng], 13);
            L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
                maxZoom: 19,
                attribution: "&copy; OpenStreetMap contributors",
            }).addTo(map);
            marker = L.marker([lat, lng], { draggable: true }).addTo(map);
            marker.on("dragend", () => {
                const p = marker.getLatLng();
                selected = { lat: p.lat, lng: p.lng };
            });
            map.on("click", (e) => {
                marker.setLatLng(e.latlng);
                selected = { lat: e.latlng.lat, lng: e.latlng.lng };
            });
        } else {
            map.setView([lat, lng], 13);
            marker.setLatLng([lat, lng]);
        }
        selected = { lat, lng };
        scheduleMapResize();
    }

    function readGlobalDefaultCoords() {
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

    function open(options) {
        if (!modal) return;
        const globals = readGlobalDefaultCoords();
        const lat = Number(options && options.lat);
        const lng = Number(options && options.lng);
        const startLat = Number.isFinite(lat) ? lat : globals.lat;
        const startLng = Number.isFinite(lng) ? lng : globals.lng;
        activeCallback = typeof options.onSave === "function" ? options.onSave : null;
        activeCloseCallback = typeof options.onClose === "function" ? options.onClose : null;
        initialPoint = { lat: startLat, lng: startLng };
        modal.classList.add("is-open");
        modal.setAttribute("aria-hidden", "false");
        ensureMap(startLat, startLng);
    }

    function close() {
        if (!modal) return;
        modal.classList.remove("is-open");
        modal.setAttribute("aria-hidden", "true");
        if (activeCloseCallback) {
            const cb = activeCloseCallback;
            activeCloseCallback = null;
            cb();
        }
    }

    if (closeBtn) closeBtn.addEventListener("click", close);
    if (saveBtn) {
        saveBtn.addEventListener("click", () => {
            if (hasLeaflet() && marker) {
                const p = marker.getLatLng();
                selected = { lat: p.lat, lng: p.lng };
            } else if (!hasLeaflet()) {
                const latValue = Number.parseFloat((fallbackLat?.value || "").replace(",", "."));
                const lngValue = Number.parseFloat((fallbackLng?.value || "").replace(",", "."));
                if (Number.isFinite(latValue) && Number.isFinite(lngValue)) {
                    selected = { lat: latValue, lng: lngValue };
                }
            }
            if (activeCallback && selected) {
                activeCallback(selected, { moved: pointMoved(selected) });
            }
            close();
        });
    }
    if (modal) {
        modal.addEventListener("click", (e) => {
            if (e.target === modal) {
                close();
            }
        });
    }

    window.MapModal = { open };
})();
