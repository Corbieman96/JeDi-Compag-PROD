(function () {
    function readJsonScript(id) {
        const el = document.getElementById(id);
        if (!el) return {};
        try {
            return JSON.parse(el.textContent);
        } catch (e) {
            return {};
        }
    }

    function getCsrf() {
        const input = document.querySelector('input[name="csrfmiddlewaretoken"]');
        if (input && input.value) return input.value;
        const m = document.cookie.match(/csrftoken=([^;]+)/);
        return m ? decodeURIComponent(m[1]) : "";
    }

    function updateUrlMapFromOptions(opts, urlMap) {
        (opts || []).forEach(function (o) {
            urlMap[String(o.id)] = o.url || "";
        });
    }

    function fillZpoSelect(selectEl, options, preferredId, currentValue, respectExplicitEmpty) {
        const emptyLabel = "— bez ZPO —";
        selectEl.innerHTML = "";
        const opt0 = document.createElement("option");
        opt0.value = "";
        opt0.textContent = emptyLabel;
        selectEl.appendChild(opt0);
        (options || []).forEach(function (o) {
            const opt = document.createElement("option");
            opt.value = String(o.id);
            opt.textContent = o.label;
            selectEl.appendChild(opt);
        });
        const cur = currentValue === undefined || currentValue === null ? "" : String(currentValue);
        let pick = "";
        if (cur && selectEl.querySelector('option[value="' + cur + '"]')) {
            pick = cur;
        } else if (respectExplicitEmpty && cur === "") {
            pick = "";
        } else if (!cur && preferredId && selectEl.querySelector('option[value="' + String(preferredId) + '"]')) {
            pick = String(preferredId);
        }
        selectEl.value = pick;
    }

    function syncOpenLink(card, zpoSelect, urlMap) {
        const link = card.querySelector(".name-subject-pairs__zpo-open-link");
        const hint = card.querySelector(".name-subject-pairs__zpo-hint");
        if (!link || !zpoSelect) return;
        const id = (zpoSelect.value || "").trim();
        const url = id ? urlMap[id] || "" : "";
        if (url) {
            link.href = url;
            link.removeAttribute("hidden");
            if (hint) hint.textContent = "";
        } else {
            link.setAttribute("hidden", "hidden");
            link.href = "#";
            if (hint) {
                hint.textContent = id ? "Soubor není k dispozici (obnovte stránku nebo znovu vyberte ZPO)." : "";
            }
        }
    }

    function refreshZpoForCard(card, urlMap, cfg, preserveCurrent) {
        const wasteSel = card.querySelector('select[name*="waste_type"]');
        const suffixSel = card.querySelector('select[name*="suffix"]');
        const zpoSel = card.querySelector(".name-subject-pairs__zpo-select");
        if (!zpoSel || !cfg.optionsUrl) return;
        const wt = wasteSel && wasteSel.value ? wasteSel.value : "";
        const suf = suffixSel && suffixSel.value ? suffixSel.value : "";
        const prev = preserveCurrent ? zpoSel.value : "";
        const u = new URL(cfg.optionsUrl, window.location.origin);
        if (wt) u.searchParams.set("waste_type_id", wt);
        if (suf) u.searchParams.set("suffix_id", suf);
        fetch(u.toString(), { credentials: "same-origin" })
            .then(function (r) {
                return r.json();
            })
            .then(function (data) {
                if (!data.ok) return;
                const urlMap = getUrlMap();
                updateUrlMapFromOptions(data.options, urlMap);
                const tgt = document.getElementById("name-subject-zpo-urls");
                if (tgt) tgt.textContent = JSON.stringify(urlMap);
                fillZpoSelect(
                    zpoSel,
                    data.options,
                    data.preferred_id,
                    preserveCurrent ? prev : "",
                    preserveCurrent,
                );
                syncOpenLink(card, zpoSel, getUrlMap());
            })
            .catch(function () {});
    }

    document.addEventListener("DOMContentLoaded", function () {
        const cfgEl = document.getElementById("name-subject-zpo-config");
        const rawAuto = cfgEl && cfgEl.dataset ? cfgEl.dataset.autoZpoByWaste : undefined;
        const cfg = {
            optionsUrl: cfgEl && cfgEl.dataset ? cfgEl.dataset.optionsUrl : "",
            inlineUrl: cfgEl && cfgEl.dataset ? cfgEl.dataset.inlineUrl : "",
            autoZpoByWaste: rawAuto === undefined ? true : rawAuto === "true",
        };
        function getUrlMap() {
            return readJsonScript("name-subject-zpo-urls");
        }

        document.addEventListener("change", function (e) {
            const pairsRoot = e.target.closest(".name-subject-pairs");
            if (!pairsRoot) return;
            const t = e.target;
            const card = t.closest(".name-subject-pairs__card");
            if (!card || !pairsRoot.contains(card)) return;
            const name = t.getAttribute("name") || "";
            if (t.classList.contains("name-subject-pairs__zpo-select")) {
                syncOpenLink(card, t, getUrlMap());
                return;
            }
            if (name.indexOf("waste_type") !== -1 || name.indexOf("suffix") !== -1) {
                const preserve = !cfg.autoZpoByWaste;
                    refreshZpoForCard(card, getUrlMap(), cfg, preserve);
            }
        });

        document.addEventListener("click", function (e) {
            const btn = e.target.closest(".name-subject-pairs__zpo-add-btn");
            if (!btn) return;
            const pairsRoot = btn.closest(".name-subject-pairs");
            if (!pairsRoot) return;
            e.preventDefault();
            const card = btn.closest(".name-subject-pairs__card");
            const modal = document.getElementById("name-subject-zpo-inline-modal");
            const form = document.getElementById("name-subject-zpo-inline-form");
            if (!modal || !card || !cfg.inlineUrl || !form) return;
            modal.classList.add("is-open");
            modal.setAttribute("aria-hidden", "false");
            modal._targetCard = card;
            form.reset();
            const wasteSel = card.querySelector('select[name*="waste_type"]');
            const suffixSel = card.querySelector('select[name*="suffix"]');
            const wEl = document.getElementById("zpo-inline-waste");
            const sEl = document.getElementById("zpo-inline-suffix");
            if (wEl) wEl.value = wasteSel && wasteSel.value ? wasteSel.value : "";
            if (sEl) sEl.value = suffixSel && suffixSel.value ? suffixSel.value : "";
        });

        function refreshZpoCardsIn(root) {
            const scope = root || document;
            scope.querySelectorAll(".name-subject-pairs__card").forEach(function (card) {
                const zpoSel = card.querySelector(".name-subject-pairs__zpo-select");
                if (!zpoSel) return;
                syncOpenLink(card, zpoSel, getUrlMap());
                const wasteSel = card.querySelector('select[name*="waste_type"]');
                const suffixSel = card.querySelector('select[name*="suffix"]');
                if ((wasteSel && wasteSel.value) || (suffixSel && suffixSel.value)) {
                    refreshZpoForCard(card, getUrlMap(), cfg, true);
                }
            });
        }

        window.jedisRefreshZpoPairCardsIn = refreshZpoCardsIn;
        refreshZpoCardsIn(document);

        const modal = document.getElementById("name-subject-zpo-inline-modal");
        if (modal) {
            modal.querySelectorAll("[data-zpo-modal-close]").forEach(function (b) {
                b.addEventListener("click", function () {
                    modal.classList.remove("is-open");
                    modal.setAttribute("aria-hidden", "true");
                });
            });
            modal.addEventListener("click", function (e) {
                if (e.target === modal) {
                    modal.classList.remove("is-open");
                    modal.setAttribute("aria-hidden", "true");
                }
            });
        }

        const form = document.getElementById("name-subject-zpo-inline-form");
        if (form && cfg.inlineUrl) {
            form.addEventListener("submit", function (e) {
                e.preventDefault();
                const fd = new FormData(form);
                fetch(cfg.inlineUrl, {
                    method: "POST",
                    headers: { "X-CSRFToken": getCsrf() },
                    body: fd,
                    credentials: "same-origin",
                })
                    .then(function (r) {
                        return r.json();
                    })
                    .then(function (data) {
                        if (!data.ok) {
                            alert(data.error || "Chyba");
                            return;
                        }
                        const urlMap = getUrlMap();
                        urlMap[String(data.id)] = data.url || "";
                        const tgt = document.getElementById("name-subject-zpo-urls");
                        if (tgt) tgt.textContent = JSON.stringify(urlMap);
                        const card = modal && modal._targetCard;
                        if (card) {
                            const zpoSel = card.querySelector(".name-subject-pairs__zpo-select");
                            if (zpoSel) {
                                const opt = document.createElement("option");
                                opt.value = String(data.id);
                                opt.textContent = data.label;
                                zpoSel.appendChild(opt);
                                zpoSel.value = String(data.id);
                                syncOpenLink(card, zpoSel, getUrlMap());
                            }
                        }
                        if (modal) {
                            modal.classList.remove("is-open");
                            modal.setAttribute("aria-hidden", "true");
                        }
                    })
                    .catch(function () {
                        alert("Uložení se nepodařilo.");
                    });
            });
        }
    });
})();
