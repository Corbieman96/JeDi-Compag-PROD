/**
 * Plovoucí panel: náhled ZPO + textový detail jízdy při zakládání průvodky (párování pasů).
 * Vyžaduje `window.JEDIS_ZPO_PAIRING = { endpoint: "<url>" }` a v šabloně prvek `#zpo-pairing-dock`.
 */
(function () {
    var DEFAULT_FIELD_MAP = [
        ["name_id", "id_name"],
        ["waste_type_id", "id_waste_type"],
        ["suffix_id", "id_suffix"],
        ["activity_id", "id_activity"],
        ["vehicle_rz_id", "id_vehicle_rz"],
        ["driver_id", "id_driver"],
        ["drive_date", "id_drive_date"],
        ["container_number", "id_container_number"],
        ["contact_phone", "id_contact_phone"],
        ["contact_note", "id_contact_note"],
        ["fulfillment_address_value", "id_fulfillment_address_value"],
        ["facility_address_display", "id_facility_address_display"],
    ];

    function byId(id) {
        return document.getElementById(id);
    }

    function getFieldMap() {
        var cfg = window.JEDIS_ZPO_PAIRING || {};
        if (Array.isArray(cfg.fieldMap) && cfg.fieldMap.length) {
            return cfg.fieldMap;
        }
        return DEFAULT_FIELD_MAP;
    }

    function getWatchIds() {
        var cfg = window.JEDIS_ZPO_PAIRING || {};
        if (Array.isArray(cfg.watchElementIds) && cfg.watchElementIds.length) {
            return cfg.watchElementIds;
        }
        var ids = [];
        getFieldMap().forEach(function (pair) {
            var id = pair[1];
            if (id && ids.indexOf(id) === -1) {
                ids.push(id);
            }
        });
        return ids;
    }

    function collectParams() {
        var params = new URLSearchParams();
        getFieldMap().forEach(function (pair) {
            var key = pair[0];
            var id = pair[1];
            var el = byId(id);
            if (!el) return;
            var v = (el.value || "").trim();
            if (v) params.set(key, v);
        });
        return params;
    }

    function escapeHtml(s) {
        var d = document.createElement("div");
        d.textContent = s == null ? "" : String(s);
        return d.innerHTML;
    }

    function detailKey(lines) {
        if (!lines || !lines.length) return "";
        return lines
            .map(function (row) {
                return (row.label || "") + "\u0001" + (row.value || "");
            })
            .join("\u0002");
    }

    function renderLines(lines) {
        if (!lines || !lines.length) return "<p class=\"zpo-pairing-dock__muted\">—</p>";
        var rows = lines
            .map(function (row) {
                var lab = row.label || "";
                var val = row.value || "—";
                return (
                    "<tr><th>" +
                    escapeHtml(lab) +
                    "</th><td>" +
                    escapeHtml(val) +
                    "</td></tr>"
                );
            })
            .join("");
        return "<table class=\"zpo-pairing-dock__table\"><tbody>" + rows + "</tbody></table>";
    }

    function renderZpo(url, kind) {
        if (kind === "pdf") {
            return (
                '<iframe class="zpo-pairing-dock__frame" src="' +
                url +
                '" title="ZPO"></iframe>'
            );
        }
        if (kind === "image") {
            return (
                '<img class="zpo-pairing-dock__img" src="' +
                url +
                '" alt="ZPO dokument">'
            );
        }
        return (
            '<p class="zpo-pairing-dock__muted">Formát souboru nelze vložit do náhledu. ' +
            '<a href="' +
            url +
            '" target="_blank" rel="noopener">Otevřít ZPO</a></p>'
        );
    }

    function currentZpoMedia(zpoHost) {
        var frame = zpoHost.querySelector("iframe.zpo-pairing-dock__frame");
        if (frame) {
            return { kind: "pdf", url: frame.getAttribute("src") || "" };
        }
        var img = zpoHost.querySelector("img.zpo-pairing-dock__img");
        if (img) {
            return { kind: "image", url: img.getAttribute("src") || "" };
        }
        return { kind: "", url: "" };
    }

    function updateZpoHost(zpoHost, url, kind, lastZpo) {
        if (!url) {
            if (zpoHost.innerHTML) {
                zpoHost.innerHTML = "";
            }
            lastZpo.url = "";
            lastZpo.kind = "";
            return;
        }
        var current = currentZpoMedia(zpoHost);
        if (current.url === url && current.kind === kind) {
            lastZpo.url = url;
            lastZpo.kind = kind;
            return;
        }
        zpoHost.innerHTML = renderZpo(url, kind);
        lastZpo.url = url;
        lastZpo.kind = kind;
    }

    function init() {
        var cfg = window.JEDIS_ZPO_PAIRING || {};
        var endpoint = cfg.endpoint;
        var dock = byId("zpo-pairing-dock");
        var body = byId("zpo-pairing-dock-body");
        var zpoHost = byId("zpo-pairing-dock-zpo");
        var detailHost = byId("zpo-pairing-dock-detail");
        if (!endpoint || !dock || !body || !zpoHost || !detailHost) return;

        var debounceMs = typeof cfg.debounceMs === "number" ? cfg.debounceMs : 480;
        var timer = null;
        var refreshSeq = 0;
        var inFlightQueryKey = "";
        var lastQueryKey = "";
        var lastDetailKey = "";
        var lastZpo = { url: "", kind: "" };
        var panelHasZpo = false;

        function setVisible(on) {
            if (on) dock.classList.add("is-visible");
            else dock.classList.remove("is-visible");
        }

        async function refresh() {
            if (dock.dataset.jedisActivityZpoOff === "1") {
                zpoHost.innerHTML = "";
                detailHost.innerHTML = "";
                setVisible(false);
                lastQueryKey = "";
                lastDetailKey = "";
                lastZpo.url = "";
                lastZpo.kind = "";
                panelHasZpo = false;
                inFlightQueryKey = "";
                return;
            }

            var queryKey = collectParams().toString();
            if (queryKey === lastQueryKey) {
                return;
            }
            if (queryKey === inFlightQueryKey) {
                return;
            }

            var seq = ++refreshSeq;
            inFlightQueryKey = queryKey;
            var url = endpoint + "?" + queryKey;

            try {
                var res = await fetch(url, { credentials: "same-origin" });
                var data = await res.json();
                if (seq !== refreshSeq) return;

                if (!data || !data.ok) return;

                lastQueryKey = queryKey;

                var lines = data.ride_detail_lines || [];
                var nextDetailKey = detailKey(lines);
                if (nextDetailKey !== lastDetailKey) {
                    detailHost.innerHTML = renderLines(lines);
                    lastDetailKey = nextDetailKey;
                }

                if (!data.has_zpo) {
                    panelHasZpo = false;
                    updateZpoHost(zpoHost, "", "", lastZpo);
                    setVisible(false);
                    return;
                }

                updateZpoHost(zpoHost, data.zpo_url || "", data.zpo_kind || "", lastZpo);
                panelHasZpo = true;
                setVisible(true);
            } catch (e) {
                if (seq !== refreshSeq) return;
                if (!panelHasZpo) {
                    setVisible(false);
                }
            } finally {
                if (inFlightQueryKey === queryKey) {
                    inFlightQueryKey = "";
                }
            }
        }

        function schedule() {
            clearTimeout(timer);
            timer = setTimeout(refresh, debounceMs);
        }

        function forceSchedule() {
            lastQueryKey = "";
            schedule();
        }

        getWatchIds().forEach(function (id) {
            var el = byId(id);
            if (!el) return;
            el.addEventListener("change", schedule);
        });

        var btnMin = byId("zpo-pairing-dock-min");
        if (btnMin) {
            btnMin.addEventListener("click", function () {
                dock.classList.toggle("is-collapsed");
            });
        }

        window.jedisRefreshZpoPairingDock = forceSchedule;
        schedule();
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", init);
    } else {
        init();
    }
})();
