/**
 * Combobox pro druh odpadu v kartách páru F/P (plná editace i modal z jízdy).
 */
(function () {
    window._jedisWasteComboDlIdx = window._jedisWasteComboDlIdx || 0;

    window.jedisStripWasteComboWrappers = function (root) {
        if (!root) return;
        root.querySelectorAll(".name-subject-waste-combo").forEach(function (wrap) {
            const sel = wrap.querySelector("select[name*='waste_type']");
            if (!sel || !wrap.parentNode) return;
            wrap.parentNode.insertBefore(sel, wrap);
            wrap.remove();
            sel.style.display = "";
        });
    };

    window.jedisInitWasteCombosIn = function (listRoot) {
        const metaEl = document.getElementById("name-subject-waste-meta");
        if (!metaEl || !listRoot) return;
        let wasteTypeMeta = {};
        try {
            wasteTypeMeta = JSON.parse(metaEl.textContent);
        } catch (e) {
            return;
        }
        const optionMap = {};
        Object.entries(wasteTypeMeta).forEach(function (entry) {
            const meta = entry[1];
            optionMap[meta.label] = entry[0];
        });

        function normalizeWasteQuery(q) {
            return (q || "")
                .toLowerCase()
                .replace(/\s+/g, "")
                .replace(/[^0-9a-záčďéěíňóôřšťúůýž+\-*]/gi, "");
        }

        function refillWastePairDatalist(datalistEl, query) {
            const nq = normalizeWasteQuery(query);
            datalistEl.innerHTML = "";
            Object.values(wasteTypeMeta).forEach(function (meta) {
                const searchable = normalizeWasteQuery((meta.code || "") + " " + (meta.label || ""));
                if (!nq || searchable.includes(nq)) {
                    const opt = document.createElement("option");
                    opt.value = meta.label;
                    datalistEl.appendChild(opt);
                }
            });
        }

        listRoot.querySelectorAll("select[name*='waste_type']").forEach(function (selectEl) {
            if (selectEl.closest(".name-subject-waste-combo")) return;
            const wrap = document.createElement("div");
            wrap.className = "name-subject-waste-combo";
            const input = document.createElement("input");
            input.type = "text";
            input.className = "waste-combo-q";
            input.setAttribute("autocomplete", "off");
            input.placeholder = "Kód (00 00 00 / 000000) nebo text…";
            const dl = document.createElement("datalist");
            dl.id = "name-subject-waste-dl-" + window._jedisWasteComboDlIdx++;
            input.setAttribute("list", dl.id);

            const parent = selectEl.parentNode;
            parent.insertBefore(wrap, selectEl);
            wrap.appendChild(input);
            wrap.appendChild(dl);
            wrap.appendChild(selectEl);
            selectEl.style.display = "none";
            if (selectEl.title) {
                input.title = selectEl.title;
            }

            function syncInputFromSelect() {
                const v = selectEl.value;
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
                const hit = optionMap[input.value];
                if (hit) selectEl.value = hit;
            });
            input.addEventListener("change", function () {
                const hit = optionMap[input.value];
                if (hit) {
                    selectEl.value = hit;
                } else if (!(input.value || "").trim()) {
                    selectEl.value = "";
                }
            });
            input.addEventListener("blur", function () {
                const hit = optionMap[input.value];
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

    window.jedisFlushWasteCombosInForm = function (formEl) {
        if (!formEl) return;
        formEl.querySelectorAll(".name-subject-waste-combo .waste-combo-q").forEach(function (el) {
            el.blur();
        });
    };
})();
