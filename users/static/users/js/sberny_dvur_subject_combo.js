/**
 * Combobox s AJAX vyhledáváním pro pole „Subjekt sběrného dvora (F/P)“.
 */
(function () {
    function normalizeLabelSearch(raw) {
        return (raw || "")
            .toLowerCase()
            .replace(/\s+/g, " ")
            .trim();
    }

    function initSbernyDvurSubjectCombo(rowEl) {
        if (!rowEl || rowEl.dataset.comboReady === "1") return;
        const selectEl = rowEl.querySelector("select[name='sberny_dvur_subject']");
        if (!selectEl) return;

        const searchUrl = rowEl.dataset.searchUrl || "";
        const fieldInput = rowEl.querySelector(".field-input");
        if (!fieldInput) return;

        const wrap = document.createElement("div");
        wrap.className = "sberny-dvur-subject-combo";

        const input = document.createElement("input");
        input.type = "text";
        input.className = "sberny-dvur-subject-combo__q";
        input.setAttribute("autocomplete", "off");
        input.setAttribute("spellcheck", "false");
        input.placeholder = "Název firmy, IČO nebo F/P jméno (min. 2 znaky)…";

        const dl = document.createElement("datalist");
        dl.id = "sberny-dvur-subject-dl-" + String(Math.random()).slice(2);
        input.setAttribute("list", dl.id);

        fieldInput.insertBefore(wrap, selectEl);
        wrap.appendChild(input);
        wrap.appendChild(dl);
        wrap.appendChild(selectEl);
        selectEl.classList.add("sberny-dvur-subject-combo__select");

        const labelMap = new Map();
        let debounceTimer = null;
        let fetchSeq = 0;

        function syncInputFromSelect() {
            const opt = selectEl.options[selectEl.selectedIndex];
            if (selectEl.value && opt && opt.value) {
                input.value = opt.textContent.trim();
            } else {
                input.value = "";
            }
        }

        function applyHit(hit) {
            if (!hit) {
                selectEl.value = "";
                input.value = "";
                return;
            }
            selectEl.value = String(hit.subject_profile_id);
            input.value = hit.label;
        }

        function resolveHitByText(rawValue) {
            const raw = (rawValue || "").trim();
            if (!raw) return null;
            const direct = labelMap.get(raw.toLowerCase());
            if (direct) return direct;
            const q = normalizeLabelSearch(raw);
            if (!q) return null;
            let exact = null;
            let partials = [];
            labelMap.forEach(function (hit) {
                const n = normalizeLabelSearch(hit.label);
                if (n === q) exact = hit;
                else if (n.includes(q)) partials.push(hit);
            });
            if (exact) return exact;
            if (partials.length === 1) return partials[0];
            return null;
        }

        function refillDatalist(rows) {
            dl.innerHTML = "";
            labelMap.clear();
            rows.forEach(function (row) {
                const label = String(row.label || "").trim();
                if (!label) return;
                const opt = document.createElement("option");
                opt.value = label;
                if (row.title) opt.title = row.title;
                dl.appendChild(opt);
                labelMap.set(label.toLowerCase(), row);
            });
        }

        async function fetchSuggestions(query) {
            if (!searchUrl || !query || query.length < 2) {
                refillDatalist([]);
                return;
            }
            const seq = ++fetchSeq;
            const url = searchUrl + (searchUrl.indexOf("?") >= 0 ? "&" : "?") + "q=" + encodeURIComponent(query);
            try {
                const res = await fetch(url, { headers: { "X-Requested-With": "XMLHttpRequest" } });
                if (!res.ok || seq !== fetchSeq) return;
                const payload = await res.json();
                if (seq !== fetchSeq) return;
                const rows = Array.isArray(payload.data) ? payload.data : [];
                refillDatalist(rows);
            } catch (e) {
                /* tiché selhání — uživatel může zkusit znovu */
            }
        }

        function scheduleFetch(query) {
            if (debounceTimer) window.clearTimeout(debounceTimer);
            debounceTimer = window.setTimeout(function () {
                fetchSuggestions((query || "").trim());
            }, 220);
        }

        syncInputFromSelect();

        input.addEventListener("focus", function () {
            scheduleFetch(input.value);
        });
        input.addEventListener("mousedown", function () {
            if (document.activeElement !== input) scheduleFetch(input.value);
        });
        input.addEventListener("keydown", function (e) {
            if (e.key === "ArrowDown" || e.key === "F4") scheduleFetch(input.value);
        });
        input.addEventListener("input", function () {
            const hit = resolveHitByText(input.value);
            if (hit && hit.label === input.value.trim()) {
                applyHit(hit);
            } else if (!(input.value || "").trim()) {
                selectEl.value = "";
            }
            scheduleFetch(input.value);
        });
        input.addEventListener("change", function () {
            const hit = resolveHitByText(input.value);
            if (hit) applyHit(hit);
        });
        input.addEventListener("blur", function () {
            const hit = resolveHitByText(input.value);
            if (hit) {
                applyHit(hit);
                return;
            }
            if (!(input.value || "").trim()) {
                selectEl.value = "";
                return;
            }
            syncInputFromSelect();
        });

        selectEl.addEventListener("change", syncInputFromSelect);
        rowEl.dataset.comboReady = "1";
    }

    document.addEventListener("DOMContentLoaded", function () {
        document.querySelectorAll(".sberny-dvur-subject-row").forEach(initSbernyDvurSubjectCombo);
    });
})();
