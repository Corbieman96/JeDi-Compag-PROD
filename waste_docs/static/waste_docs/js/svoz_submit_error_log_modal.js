(function () {
    var modal = document.getElementById("dash-svoz-error-log-modal");
    var openBtn = document.getElementById("dash-svoz-error-log-open");
    if (!modal || !openBtn) return;
    if (modal.parentElement !== document.body) {
        document.body.appendChild(modal);
    }
    var body = document.getElementById("dash-svoz-error-log-body");
    var prevOverflow = "";
    var acked = false;
    var loaded = false;
    var loading = false;

    function csrfToken() {
        var m = document.cookie.match(/(?:^|; )csrftoken=([^;]+)/);
        if (m) return decodeURIComponent(m[1]);
        var el = document.querySelector("[name=csrfmiddlewaretoken]");
        return el ? el.value : "";
    }

    function acknowledge() {
        if (acked) return;
        acked = true;
        var url = modal.getAttribute("data-ack-url");
        if (!url) return;
        fetch(url, {
            method: "POST",
            headers: {
                "X-Requested-With": "XMLHttpRequest",
                "X-CSRFToken": csrfToken()
            },
            credentials: "same-origin"
        }).catch(function () {});
    }

    function loadBody() {
        if (!body || loaded || loading) return;
        var url = modal.getAttribute("data-fetch-url");
        if (!url) return;
        loading = true;
        body.innerHTML = '<p class="dash-muted" style="margin:0;">Načítám log…</p>';
        fetch(url, {
            method: "GET",
            headers: { "X-Requested-With": "XMLHttpRequest" },
            credentials: "same-origin"
        })
            .then(function (r) {
                if (!r.ok) throw new Error("load failed");
                return r.text();
            })
            .then(function (html) {
                body.innerHTML = html || '<p class="dash-muted" style="margin:0;">Žádné záznamy.</p>';
                loaded = true;
            })
            .catch(function () {
                body.innerHTML =
                    '<p class="dash-muted" style="margin:0;color:#b42318;">Nepodařilo se načíst log.</p>';
            })
            .finally(function () {
                loading = false;
            });
    }

    function openModal() {
        modal.removeAttribute("hidden");
        modal.hidden = false;
        modal.setAttribute("aria-hidden", "false");
        openBtn.setAttribute("aria-expanded", "true");
        prevOverflow = document.body.style.overflow;
        document.body.style.overflow = "hidden";
        loadBody();
        acknowledge();
    }

    function closeModal() {
        modal.hidden = true;
        modal.setAttribute("hidden", "");
        modal.setAttribute("aria-hidden", "true");
        openBtn.setAttribute("aria-expanded", "false");
        document.body.style.overflow = prevOverflow;
        openBtn.focus();
    }

    openBtn.addEventListener("click", function (e) {
        e.preventDefault();
        e.stopPropagation();
        openModal();
    });
    modal.querySelectorAll("[data-dash-svoz-error-log-close]").forEach(function (el) {
        el.addEventListener("click", function (e) {
            e.preventDefault();
            closeModal();
        });
    });
    document.addEventListener("keydown", function (e) {
        if (e.key === "Escape" && !modal.hidden) closeModal();
    });
    if (modal.getAttribute("data-auto-open") === "1") {
        openModal();
    }
})();
