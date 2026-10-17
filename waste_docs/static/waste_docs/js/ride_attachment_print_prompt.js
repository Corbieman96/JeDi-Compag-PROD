(function () {
    "use strict";

    function attachmentPrintItems() {
        const items = window.__JEDIS_RIDE_ATTACHMENT_PRINT__;
        return Array.isArray(items)
            ? items.filter(function (item) {
                  return item && item.printUrl;
              })
            : [];
    }

    function ridePkFromItems(items) {
        const btn = document.getElementById("ride-attachment-print-open");
        if (btn) {
            const fromBtn = (btn.getAttribute("data-ride-pk") || "").trim();
            if (fromBtn) {
                return fromBtn;
            }
        }
        const first = items[0];
        if (!first || !first.printUrl) {
            return "";
        }
        const match = String(first.printUrl).match(/\/waste-docs\/(\d+)\/attachments\//);
        return match ? match[1] : "";
    }

    function sessionKey(ridePk, items) {
        const ids = items
            .map(function (item) {
                return String(item.id || "");
            })
            .filter(Boolean)
            .sort()
            .join(",");
        return "jedis-att-print:" + ridePk + ":" + ids;
    }

    function alreadyOffered(key) {
        try {
            return window.sessionStorage.getItem(key) === "1";
        } catch (e) {
            return false;
        }
    }

    function markOffered(key) {
        try {
            window.sessionStorage.setItem(key, "1");
        } catch (e) {
            /* ignore quota / private mode */
        }
    }

    function confirmMessage(items) {
        return items.length === 1
            ? "Jízda má přílohu. Chcete ji vytisknout s číslem jízdy a datem?"
            : "Jízda má přílohy (" +
                  items.length +
                  "). Chcete je vytisknout s číslem jízdy a datem?";
    }

    function openStampedPdfs(items) {
        items.forEach(function (item) {
            window.open(item.printUrl, "_blank", "noopener,noreferrer");
        });
    }

    function offerAttachmentPrint(options) {
        const opts = options || {};
        const force = Boolean(opts.force);
        const items = attachmentPrintItems();
        if (!items.length) {
            return;
        }
        const ridePk = ridePkFromItems(items);
        const key = ridePk ? sessionKey(ridePk, items) : "";
        if (!force && key && alreadyOffered(key)) {
            return;
        }
        if (!window.confirm(confirmMessage(items))) {
            if (key) {
                markOffered(key);
            }
            return;
        }
        if (key) {
            markOffered(key);
        }
        openStampedPdfs(items);
    }

    const manualBtn = document.getElementById("ride-attachment-print-open");
    if (manualBtn) {
        manualBtn.addEventListener("click", function () {
            offerAttachmentPrint({ force: true });
        });
    }

    if (attachmentPrintItems().length) {
        window.setTimeout(function () {
            offerAttachmentPrint({ force: false });
        }, 0);
    }
})();
