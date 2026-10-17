/**
 * Vyhledatelný combobox nad <select name*="waste_type"> (kód 200307 / 20 03 07 + název).
 */
(function () {
    "use strict";

    function normalizeWasteQuery(q) {
        return (q || "")
            .toLowerCase()
            .replace(/\s+/g, "")
            .replace(/[^0-9a-záčďéěíňóôřšťúůýž+\-*]/gi, "");
    }

    window.jedisInitWasteTypeCombosForRoot = function (metaElementId, listRoot, options) {
        options = options || {};
        var selectMatches =
            typeof options.selectMatches === "function"
                ? options.selectMatches
                : function (selectEl) {
                      return !!(selectEl.name && selectEl.name.indexOf("waste_type") !== -1);
                  };

        var metaEl =
            typeof metaElementId === "string" ? document.getElementById(metaElementId) : metaElementId;
        if (!metaEl || !listRoot) return;

        var wasteTypeMeta = {};
        try {
            wasteTypeMeta = JSON.parse(metaEl.textContent || "{}");
        } catch (e) {
            return;
        }

        window._jedisWasteComboDlIdx = window._jedisWasteComboDlIdx || 0;

        var optionMap = {};
        Object.entries(wasteTypeMeta).forEach(function (entry) {
            var meta = entry[1];
            optionMap[meta.label] = entry[0];
        });

        function refillWastePairDatalist(datalistEl, query) {
            var nq = normalizeWasteQuery(query);
            datalistEl.innerHTML = "";
            Object.values(wasteTypeMeta).forEach(function (meta) {
                var searchable = normalizeWasteQuery((meta.code || "") + " " + (meta.label || ""));
                if (!nq || searchable.indexOf(nq) !== -1) {
                    var opt = document.createElement("option");
                    opt.value = meta.label;
                    datalistEl.appendChild(opt);
                }
            });
        }

        listRoot.querySelectorAll("select").forEach(function (selectEl) {
            if (!selectMatches(selectEl)) return;
            if (selectEl.closest(".name-subject-waste-combo")) return;

            var wrap = document.createElement("div");
            wrap.className = "name-subject-waste-combo";
            var input = document.createElement("input");
            input.type = "text";
            input.className = "waste-combo-q";
            input.setAttribute("autocomplete", "off");
            input.placeholder =
                typeof options.placeholder === "string"
                    ? options.placeholder
                    : "Kód (00 00 00 / 000000) nebo text…";

            var dl = document.createElement("datalist");
            dl.id = "jedis-waste-combo-dl-" + window._jedisWasteComboDlIdx++;
            input.setAttribute("list", dl.id);

            var parent = selectEl.parentNode;
            parent.insertBefore(wrap, selectEl);
            wrap.appendChild(input);
            wrap.appendChild(dl);
            wrap.appendChild(selectEl);
            selectEl.style.display = "none";
            if (selectEl.title) input.title = selectEl.title;

            function syncInputFromSelect() {
                var v = selectEl.value;
                if (v && wasteTypeMeta[v]) {
                    input.value = wasteTypeMeta[v].label;
                } else {
                    input.value = "";
                }
            }

            refillWastePairDatalist(dl, "");
            syncInputFromSelect();

            input.addEventListener("input", function () {
                refillWastePairDatalist(dl, input.value);
                var hit = optionMap[input.value];
                if (hit) selectEl.value = hit;
            });
            input.addEventListener("change", function () {
                var hit = optionMap[input.value];
                if (hit) {
                    selectEl.value = hit;
                } else if (!(input.value || "").trim()) {
                    selectEl.value = "";
                }
            });
            input.addEventListener("blur", function () {
                var hit = optionMap[input.value];
                if (hit) {
                    selectEl.value = hit;
                    input.value = wasteTypeMeta[hit].label;
                    return;
                }
                if (!normalizeWasteQuery(input.value)) {
                    selectEl.value = "";
                    input.value = "";
                    return;
                }
                syncInputFromSelect();
            });
            selectEl.addEventListener("change", syncInputFromSelect);
        });
    };
})();
