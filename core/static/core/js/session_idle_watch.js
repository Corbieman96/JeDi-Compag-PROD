/**
 * Globální watchdog nečinnosti — po idle timeout přesměruje na login.
 * Aktivita obnoví klientský časovač a max 1×/min pingne keepalive.
 */
(function () {
    "use strict";

    const cfgEl = document.getElementById("jedis-session-idle-config");
    if (!cfgEl) {
        return;
    }

    let cfg;
    try {
        cfg = JSON.parse(cfgEl.textContent || "{}");
    } catch (e) {
        return;
    }

    const idleMs = Number(cfg.idleTimeoutMs || 0);
    let loginUrl = String(cfg.loginUrl || "");
    const keepaliveUrl = String(cfg.keepaliveUrl || "");
    if (!idleMs || idleMs < 60000 || !loginUrl) {
        return;
    }
    // Absolutní path — relativní "login" na /accounts/login/ → /accounts/login/login (404).
    if (loginUrl.indexOf("http") !== 0 && loginUrl.charAt(0) !== "/") {
        loginUrl = "/" + loginUrl.replace(/^\/+/, "");
    }

    let deadline = Date.now() + idleMs;
    let lastKeepaliveAt = 0;
    let timerId = null;
    let redirected = false;

    function isOnLoginPage() {
        const path = String(window.location.pathname || "");
        if (path.indexOf("/accounts/login") === 0) {
            return true;
        }
        const loginPath = loginUrl.split("?")[0].replace(/\/+$/, "") || "";
        const cur = path.replace(/\/+$/, "") || "";
        return Boolean(loginPath) && cur === loginPath;
    }

    function goToLogin() {
        if (redirected) {
            return;
        }
        if (isOnLoginPage()) {
            redirected = true;
            return;
        }
        redirected = true;
        const next = window.location.pathname + window.location.search + window.location.hash;
        const sep = loginUrl.indexOf("?") >= 0 ? "&" : "?";
        window.location.href =
            loginUrl +
            sep +
            "next=" +
            encodeURIComponent(next || "/") +
            "&reason=idle";
    }

    function schedule() {
        if (timerId) {
            window.clearTimeout(timerId);
        }
        const remain = Math.max(0, deadline - Date.now());
        timerId = window.setTimeout(function () {
            if (Date.now() >= deadline) {
                goToLogin();
            } else {
                schedule();
            }
        }, Math.min(remain, 30000));
    }

    function pingKeepalive() {
        if (!keepaliveUrl) {
            return;
        }
        const now = Date.now();
        if (now - lastKeepaliveAt < 60000) {
            return;
        }
        lastKeepaliveAt = now;
        try {
            fetch(keepaliveUrl, {
                method: "GET",
                credentials: "same-origin",
                headers: { "X-Requested-With": "XMLHttpRequest", Accept: "application/json" },
                cache: "no-store",
            }).then(function (res) {
                if (res.status === 401) {
                    goToLogin();
                }
            }).catch(function () {
                /* síťová chyba — necháme klientský timer */
            });
        } catch (e) {
            /* ignore */
        }
    }

    function onActivity() {
        deadline = Date.now() + idleMs;
        schedule();
        pingKeepalive();
    }

    let moveThrottle = 0;
    function onMove() {
        const now = Date.now();
        if (now - moveThrottle < 2000) {
            return;
        }
        moveThrottle = now;
        onActivity();
    }

    ["click", "keydown", "scroll", "touchstart"].forEach(function (evt) {
        document.addEventListener(evt, onActivity, { passive: true, capture: true });
    });
    document.addEventListener("mousemove", onMove, { passive: true, capture: true });
    document.addEventListener(
        "visibilitychange",
        function () {
            if (!document.hidden) {
                onActivity();
            }
        },
        false
    );

    schedule();
})();
