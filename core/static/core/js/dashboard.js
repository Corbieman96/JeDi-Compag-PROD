(function () {
    const picker = document.getElementById("dash-date-picker");
    if (picker) {
        picker.addEventListener("change", function () {
            if (!this.value) return;
            const u = new URL(window.location.href);
            u.searchParams.set("date", this.value);
            u.searchParams.delete("ride_group");
            u.searchParams.delete("ride_pk");
            window.location.href = u.toString();
        });
    }

    (function initSvozDriverSelects() {
        const tpl = document.getElementById("svoz-quick-edit-driver-options");
        if (!tpl || !tpl.content) return;
        document.querySelectorAll("[data-svoz-driver-select]").forEach(function (select) {
            const selected = String(select.getAttribute("data-selected-driver") || "");
            tpl.content.querySelectorAll("option").forEach(function (opt) {
                const clone = opt.cloneNode(true);
                if (selected && clone.value === selected) {
                    clone.selected = true;
                }
                select.appendChild(clone);
            });
        });
    })();

    function closeAllDriverCtxMenus() {
        document.querySelectorAll(".dash-driver-ctx-menu.is-open").forEach(function (menu) {
            menu.classList.remove("is-open");
            menu.setAttribute("hidden", "");
            menu.style.top = "";
            menu.style.left = "";
        });
        document.querySelectorAll(".dash-driver-ctx-trigger").forEach(function (b) {
            b.setAttribute("aria-expanded", "false");
        });
    }

    function closeAllAbsenceCtxMenus() {
        document.querySelectorAll(".dash-absence-ctx-menu.is-open").forEach(function (menu) {
            menu.classList.remove("is-open");
            menu.setAttribute("hidden", "");
            menu.style.top = "";
            menu.style.left = "";
        });
        document.querySelectorAll(".dash-absence-ctx-trigger").forEach(function (b) {
            b.setAttribute("aria-expanded", "false");
        });
    }

    function positionAbsenceCtxMenu(btn, menu) {
        const br = btn.getBoundingClientRect();
        const margin = 8;
        const mw = menu.offsetWidth;
        const mh = menu.offsetHeight;
        let top = br.bottom + 6;
        let left = br.right - mw;
        if (left < margin) left = margin;
        if (left + mw > window.innerWidth - margin) {
            left = window.innerWidth - mw - margin;
        }
        if (top + mh > window.innerHeight - margin) {
            top = Math.max(margin, br.top - mh - 6);
        }
        menu.style.top = top + "px";
        menu.style.left = left + "px";
    }

    function positionDriverCtxMenu(btn, menu) {
        const br = btn.getBoundingClientRect();
        const margin = 8;
        const mw = menu.offsetWidth;
        const mh = menu.offsetHeight;
        let top = br.bottom + 6;
        let left = br.right - mw;
        if (left < margin) left = margin;
        if (left + mw > window.innerWidth - margin) {
            left = window.innerWidth - mw - margin;
        }
        if (top + mh > window.innerHeight - margin) {
            top = Math.max(margin, br.top - mh - 6);
        }
        menu.style.top = top + "px";
        menu.style.left = left + "px";
    }

    document.querySelectorAll(".dash-driver-ctx-wrap").forEach(function (wrap) {
        const btn = wrap.querySelector(".dash-driver-ctx-trigger");
        const menu = wrap.querySelector(".dash-driver-ctx-menu");
        if (!btn || !menu) return;
        btn.addEventListener("click", function (e) {
            e.stopPropagation();
            const opening = !menu.classList.contains("is-open");
            closeAllDriverCtxMenus();
            if (opening) {
                menu.removeAttribute("hidden");
                menu.classList.add("is-open");
                btn.setAttribute("aria-expanded", "true");
                requestAnimationFrame(function () {
                    positionDriverCtxMenu(btn, menu);
                });
            }
        });
        menu.addEventListener("click", function (e) {
            e.stopPropagation();
        });
    });

    document.querySelectorAll(".dash-absence-ctx-wrap").forEach(function (wrap) {
        const btn = wrap.querySelector(".dash-absence-ctx-trigger");
        const menu = wrap.querySelector(".dash-absence-ctx-menu");
        if (!btn || !menu) return;
        btn.addEventListener("click", function (e) {
            e.stopPropagation();
            const opening = !menu.classList.contains("is-open");
            closeAllAbsenceCtxMenus();
            if (opening) {
                menu.removeAttribute("hidden");
                menu.classList.add("is-open");
                btn.setAttribute("aria-expanded", "true");
                requestAnimationFrame(function () {
                    positionAbsenceCtxMenu(btn, menu);
                });
            }
        });
        menu.addEventListener("click", function (e) {
            e.stopPropagation();
        });
    });

    document.addEventListener("click", closeAllDriverCtxMenus);
    document.addEventListener("click", closeAllAbsenceCtxMenus);
    document.addEventListener("keydown", function (e) {
        if (e.key === "Escape") {
            closeAllDriverCtxMenus();
            closeAllAbsenceCtxMenus();
        }
    });
    window.addEventListener(
        "scroll",
        function () {
            closeAllDriverCtxMenus();
            closeAllAbsenceCtxMenus();
        },
        true
    );
    window.addEventListener("resize", function () {
        closeAllDriverCtxMenus();
        closeAllAbsenceCtxMenus();
    });
})();

(function () {
    function setupDashboardModal(modalId, openBtnId, closeSelector) {
        var modal = document.getElementById(modalId);
        var openBtn = document.getElementById(openBtnId);
        if (!modal || !openBtn) return;
        if (modal.parentElement !== document.body) {
            document.body.appendChild(modal);
        }
        var prevOverflow = "";
        function openModal() {
            modal.hidden = false;
            modal.removeAttribute("hidden");
            modal.setAttribute("aria-hidden", "false");
            openBtn.setAttribute("aria-expanded", "true");
            openBtn.classList.add("is-active");
            prevOverflow = document.body.style.overflow;
            document.body.style.overflow = "hidden";
            var closeBtn = modal.querySelector(".dash-rides-modal__close");
            if (closeBtn) closeBtn.focus();
        }
        function closeModal() {
            modal.hidden = true;
            modal.setAttribute("hidden", "");
            modal.setAttribute("aria-hidden", "true");
            openBtn.setAttribute("aria-expanded", "false");
            openBtn.classList.remove("is-active");
            document.body.style.overflow = prevOverflow;
            openBtn.focus();
        }
        openBtn.addEventListener("click", function (e) {
            e.preventDefault();
            openModal();
        });
        modal.querySelectorAll(closeSelector).forEach(function (el) {
            el.addEventListener("click", function (e) {
                e.preventDefault();
                closeModal();
            });
        });
        document.addEventListener("keydown", function (e) {
            if (e.key === "Escape" && !modal.hidden) closeModal();
        });
    }
    setupDashboardModal("dash-rides-modal", "dash-rides-view-toggle", "[data-dash-rides-modal-close]");
    setupDashboardModal("dash-ride-detail-modal", "dash-ride-detail-expand", "[data-dash-ride-detail-modal-close]");
})();

(function () {
    try {
        var url = new URL(window.location.href);
        var q = url.searchParams.get("dash_debug");
        if (q === "0") {
            try {
                localStorage.removeItem("jedis_dash_debug");
            } catch (e) {}
        }
        var enabled = q === "1";
        if (enabled) {
            try {
                localStorage.setItem("jedis_dash_debug", "1");
            } catch (e) {}
        }
        if (!enabled) {
            try {
                enabled = localStorage.getItem("jedis_dash_debug") === "1";
            } catch (e) {}
        }
        if (!enabled) return;
    } catch (e) {
        return;
    }

    function line(k, v) {
        return k + ": " + String(v);
    }

    function gather() {
        var bodyCols = document.querySelector(".dash-board > .dash-board__body-cols");
        var board = document.querySelector(".dash-board");
        var out = [];
        out.push("JeDiS dashboard — ladění layoutu");
        out.push(line("URL width×height", window.innerWidth + "×" + window.innerHeight));
        out.push(line("documentElement.clientW", document.documentElement && document.documentElement.clientWidth));
        out.push(line("MQ (max-width:640px)", window.matchMedia && window.matchMedia("(max-width:640px)").matches));
        out.push(line("MQ (max-width:768px)", window.matchMedia && window.matchMedia("(max-width:768px)").matches));
        out.push(line("MQ (max-width:900px)", window.matchMedia && window.matchMedia("(max-width:900px)").matches));
        out.push(line(".dash-board nalezen", !!board));
        out.push(line(".dash-board__body-cols nalezen", !!bodyCols));
        if (bodyCols) {
            var cs = window.getComputedStyle(bodyCols);
            out.push(line("display", cs.display));
            out.push(line("grid-template-columns", cs.gridTemplateColumns));
            out.push(line("grid-template-rows", cs.gridTemplateRows));
            out.push(line("flex-direction", cs.flexDirection));
            out.push(line("počet přímých dětí", bodyCols.children.length));
            for (var i = 0; i < bodyCols.children.length; i += 1) {
                var ch = bodyCols.children[i];
                var gcs = window.getComputedStyle(ch);
                out.push(
                    "  [" +
                        i +
                        "] " +
                        ch.tagName +
                        "." +
                        ch.className +
                        " | gridColumn=" +
                        gcs.gridColumn +
                        " gridRow=" +
                        gcs.gridRow
                );
            }
        }
        var sheets = document.querySelectorAll('link[rel="stylesheet"][href*="dashboard"]');
        out.push(line("načtené dashboard.css odkazy", sheets.length));
        for (var s = 0; s < sheets.length; s += 1) {
            out.push("  " + (sheets[s].href || sheets[s].getAttribute("href")));
        }
        return out.join("\n");
    }

    var pre = document.createElement("div");
    pre.setAttribute("data-dash-debug", "");
    pre.style.cssText =
        "position:fixed;right:8px;bottom:8px;max-width:min(520px,92vw);max-height:46vh;overflow:auto;margin:0;" +
        "padding:10px 12px;font:12px/1.35 Consolas,monospace;white-space:pre-wrap;word-break:break-word;" +
        "background:rgba(30,40,30,0.92);color:#e8f5e9;border:1px solid #5a9e63;border-radius:8px;" +
        "z-index:2147483000;box-shadow:0 8px 28px rgba(0,0,0,0.35);";

    var cap = document.createElement("div");
    cap.style.cssText =
        "display:flex;flex-direction:column;gap:6px;" +
        "margin:-10px -12px 8px;padding:6px 10px;background:rgba(45,124,66,0.95);color:#fff;font-weight:700;";
    var capRow = document.createElement("div");
    capRow.style.cssText = "display:flex;justify-content:space-between;align-items:center;gap:8px;flex-wrap:wrap;";
    var capTitle = document.createElement("span");
    capTitle.textContent = "dash_debug";
    var capHint = document.createElement("span");
    capHint.style.cssText = "font-weight:400;font-size:10px;opacity:0.9;";
    capHint.textContent = "Zapnuto: ?dash_debug=1 · Trvale vypnout: ?dash_debug=0";
    var btnClose = document.createElement("button");
    btnClose.type = "button";
    btnClose.textContent = "Skrýt";
    btnClose.style.cssText =
        "font:inherit;padding:2px 8px;border-radius:6px;border:1px solid rgba(255,255,255,0.5);" +
        "background:rgba(255,255,255,0.15);color:#fff;cursor:pointer;";
    btnClose.addEventListener("click", function () {
        pre.remove();
    });
    var btnCopy = document.createElement("button");
    btnCopy.type = "button";
    btnCopy.textContent = "Kopírovat";
    btnCopy.style.cssText = btnClose.style.cssText;
    var inner = document.createElement("pre");
    inner.setAttribute("data-dash-debug-inner", "");
    inner.style.cssText = "margin:0;font:inherit;white-space:pre-wrap;word-break:break-word;";
    inner.textContent = gather();
    btnCopy.addEventListener("click", function () {
        var text = inner.textContent || "";
        if (navigator.clipboard && navigator.clipboard.writeText) {
            navigator.clipboard.writeText(text).catch(function () {});
        }
    });
    var tools = document.createElement("div");
    tools.style.cssText = "display:flex;gap:6px;align-items:center;flex-shrink:0;";
    tools.appendChild(btnCopy);
    tools.appendChild(btnClose);
    capRow.appendChild(capTitle);
    capRow.appendChild(tools);
    cap.appendChild(capRow);
    cap.appendChild(capHint);
    pre.appendChild(cap);
    pre.appendChild(inner);

    function refresh() {
        inner.textContent = gather();
    }
    window.addEventListener("resize", function () {
        refresh();
    });
    setInterval(refresh, 2000);

    console.group("[JeDiS dash_debug]");
    console.log(gather());
    console.groupEnd();

    document.body.appendChild(pre);
})();
