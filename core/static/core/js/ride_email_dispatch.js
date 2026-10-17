(function () {
    function getCookie(name) {
        var parts = document.cookie ? document.cookie.split(";") : [];
        for (var i = 0; i < parts.length; i++) {
            var part = parts[i].trim();
            if (part.indexOf(name + "=") === 0) {
                return decodeURIComponent(part.substring(name.length + 1));
            }
        }
        return "";
    }

    function csrfToken() {
        var input = document.querySelector("[name=csrfmiddlewaretoken]");
        return (input && input.value) || getCookie("csrftoken") || "";
    }

    function downloadBlob(blob, filename) {
        var url = URL.createObjectURL(blob);
        var link = document.createElement("a");
        link.href = url;
        link.download = filename;
        document.body.appendChild(link);
        link.click();
        link.remove();
        setTimeout(function () { URL.revokeObjectURL(url); }, 1000);
    }

    function openEmlBlob(blob, filename) {
        var typedBlob = blob.type === "message/rfc822"
            ? blob
            : new Blob([blob], { type: "message/rfc822" });
        var url = URL.createObjectURL(typedBlob);
        var link = document.createElement("a");
        link.href = url;
        link.style.display = "none";
        document.body.appendChild(link);
        link.click();
        link.remove();
        setTimeout(function () {
            URL.revokeObjectURL(url);
            downloadBlob(typedBlob, filename);
            window.alert(
                "Pokud se Outlook neotevřel automaticky, otevřete stažený soubor "
                + filename
                + " dvojklikem. Zkontrolujte příjemce a klikněte Odeslat."
            );
        }, 2000);
    }

    function parseFilename(disposition, fallback) {
        if (!disposition) return fallback;
        var match = /filename="([^"]+)"/i.exec(disposition);
        return match ? match[1] : fallback;
    }

    function deleteUrlFor(modal, pk) {
        var pattern = modal.getAttribute("data-recipients-delete-url-pattern") || "";
        return pattern.replace("/0/", "/" + String(pk) + "/");
    }

    function renderRecipients(modal, recipients) {
        var select = modal.querySelector("#dash-ride-email-recipient-preset");
        var listWrap = modal.querySelector("#dash-ride-email-saved-list");
        var list = modal.querySelector("#dash-ride-email-saved-items");
        var recipientInput = modal.querySelector("#dash-ride-email-recipient");
        if (!select || !list) return;

        var currentValue = recipientInput ? recipientInput.value.trim().toLowerCase() : "";
        select.innerHTML = "";
        var emptyOpt = document.createElement("option");
        emptyOpt.value = "";
        emptyOpt.textContent = "— vyberte nebo napište novou —";
        select.appendChild(emptyOpt);

        list.innerHTML = "";
        (recipients || []).forEach(function (item) {
            var opt = document.createElement("option");
            opt.value = item.email;
            opt.textContent = item.display || item.email;
            if (currentValue && item.email === currentValue) {
                opt.selected = true;
            }
            select.appendChild(opt);

            var li = document.createElement("li");
            li.className = "dash-ride-email-saved-item";

            var pickBtn = document.createElement("button");
            pickBtn.type = "button";
            pickBtn.className = "dash-ride-email-saved-item__pick";
            pickBtn.textContent = item.display || item.email;
            pickBtn.title = item.email;
            pickBtn.addEventListener("click", function () {
                if (recipientInput) recipientInput.value = item.email;
                select.value = item.email;
            });

            var delBtn = document.createElement("button");
            delBtn.type = "button";
            delBtn.className = "dash-ride-email-saved-item__delete";
            delBtn.textContent = "×";
            delBtn.title = "Odstranit z uložených adres";
            delBtn.setAttribute("aria-label", "Odstranit " + item.email);
            delBtn.addEventListener("click", function (e) {
                e.preventDefault();
                e.stopPropagation();
                if (!window.confirm("Odstranit adresu " + item.email + " ze seznamu?")) return;
                fetch(deleteUrlFor(modal, item.id), {
                    method: "POST",
                    credentials: "same-origin",
                    headers: {
                        "X-CSRFToken": csrfToken(),
                    },
                }).then(function (resp) {
                    if (!resp.ok) throw new Error("Odstranění se nepodařilo.");
                    return resp.json();
                }).then(function (data) {
                    renderRecipients(modal, data.recipients || []);
                }).catch(function (err) {
                    window.alert(err.message || "Chyba při mazání adresy.");
                });
            });

            li.appendChild(pickBtn);
            li.appendChild(delBtn);
            list.appendChild(li);
        });

        if (listWrap) {
            listWrap.hidden = !(recipients && recipients.length);
        }

        if (!currentValue && recipients && recipients.length) {
            var lastUsed = recipients[0];
            if (recipientInput && lastUsed && lastUsed.email) {
                recipientInput.value = lastUsed.email;
                select.value = lastUsed.email;
            }
        }
    }

    function loadRecipients(modal) {
        var url = modal.getAttribute("data-recipients-url");
        if (!url) return Promise.resolve();
        return fetch(url, { credentials: "same-origin" })
            .then(function (resp) {
                if (!resp.ok) throw new Error("Načtení uložených adres selhalo.");
                return resp.json();
            })
            .then(function (data) {
                renderRecipients(modal, data.recipients || []);
            })
            .catch(function () {
                renderRecipients(modal, []);
            });
    }

    function saveRecipient(modal) {
        var recipient = modal.querySelector("#dash-ride-email-recipient");
        var errEl = modal.querySelector("#dash-ride-email-error");
        var addUrl = modal.getAttribute("data-recipients-add-url");
        if (!recipient || !addUrl) return;
        var email = recipient.value.trim();
        if (!email) {
            if (errEl) {
                errEl.textContent = "Nejdříve zadejte e-mailovou adresu.";
                errEl.hidden = false;
            }
            return;
        }
        if (errEl) {
            errEl.hidden = true;
            errEl.textContent = "";
        }
        fetch(addUrl, {
            method: "POST",
            credentials: "same-origin",
            headers: {
                "Content-Type": "application/json",
                "X-CSRFToken": csrfToken(),
            },
            body: JSON.stringify({ email: email }),
        }).then(function (resp) {
            return resp.json().then(function (data) {
                if (!resp.ok) throw new Error((data && data.error) || "Uložení adresy selhalo.");
                return data;
            });
        }).then(function (data) {
            renderRecipients(modal, data.recipients || []);
        }).catch(function (err) {
            if (errEl) {
                errEl.textContent = err.message || "Uložení adresy selhalo.";
                errEl.hidden = false;
            }
        });
    }

    function openModal(modal) {
        modal.removeAttribute("hidden");
        modal.hidden = false;
        modal.setAttribute("aria-hidden", "false");
        document.body.style.overflow = "hidden";
        loadRecipients(modal).then(function () {
            var recipient = modal.querySelector("#dash-ride-email-recipient");
            if (recipient) recipient.focus();
        });
    }

    function closeModal(modal) {
        modal.hidden = true;
        modal.setAttribute("hidden", "");
        modal.setAttribute("aria-hidden", "true");
        document.body.style.overflow = "";
        var err = modal.querySelector("#dash-ride-email-error");
        if (err) {
            err.hidden = true;
            err.textContent = "";
        }
    }

    function bindOpenButtons(modal) {
        document.querySelectorAll("[data-dash-ride-email-open]").forEach(function (btn) {
            btn.addEventListener("click", function (e) {
                e.preventDefault();
                e.stopPropagation();
                var dateInput = modal.querySelector("#dash-ride-email-date");
                var rzInput = modal.querySelector("#dash-ride-email-rz-id");
                var driverInput = modal.querySelector("#dash-ride-email-driver-id");
                var pksInput = modal.querySelector("#dash-ride-email-filter-pks");
                var summary = modal.querySelector("#dash-ride-email-summary");
                var subjectPreview = modal.querySelector("#dash-ride-email-subject-preview");
                var recipient = modal.querySelector("#dash-ride-email-recipient");
                var preset = modal.querySelector("#dash-ride-email-recipient-preset");
                if (dateInput) dateInput.value = btn.getAttribute("data-drive-date") || "";
                if (rzInput) rzInput.value = btn.getAttribute("data-vehicle-rz-id") || "";
                if (driverInput) driverInput.value = btn.getAttribute("data-driver-id") || "";
                if (pksInput) pksInput.value = btn.getAttribute("data-filter-pks") || "";
                if (summary) summary.textContent = btn.getAttribute("data-email-summary") || "";
                if (subjectPreview) subjectPreview.value = btn.getAttribute("data-email-subject") || "";
                if (recipient) recipient.value = "";
                if (preset) preset.value = "";
                openModal(modal);
            });
        });
    }

    function bindPresetSelect(modal) {
        var preset = modal.querySelector("#dash-ride-email-recipient-preset");
        var recipient = modal.querySelector("#dash-ride-email-recipient");
        if (!preset || !recipient) return;
        preset.addEventListener("change", function () {
            if (preset.value) recipient.value = preset.value;
        });
    }

    function bindSavePreset(modal) {
        var saveBtn = modal.querySelector("#dash-ride-email-save-preset");
        if (!saveBtn) return;
        saveBtn.addEventListener("click", function (e) {
            e.preventDefault();
            saveRecipient(modal);
        });
    }

    function bindCancelButtons(modal) {
        document.querySelectorAll("[data-dash-ride-email-cancel]").forEach(function (btn) {
            btn.addEventListener("click", function (e) {
                e.preventDefault();
                e.stopPropagation();
                if (!window.confirm("Zrušit označení „odesláno e-mailem“ pro tuto skupinu?")) return;
                var cancelUrl = modal.getAttribute("data-cancel-url");
                var payload = {
                    date: btn.getAttribute("data-drive-date") || "",
                    vehicle_rz_id: btn.getAttribute("data-vehicle-rz-id") || "",
                    driver_id: btn.getAttribute("data-driver-id") || "",
                    filter_pks: btn.getAttribute("data-filter-pks") || "",
                };
                fetch(cancelUrl, {
                    method: "POST",
                    credentials: "same-origin",
                    headers: {
                        "Content-Type": "application/json",
                        "X-CSRFToken": csrfToken(),
                    },
                    body: JSON.stringify(payload),
                }).then(function (resp) {
                    if (!resp.ok) throw new Error("Zrušení se nepodařilo.");
                    window.location.reload();
                }).catch(function (err) {
                    window.alert(err.message || "Chyba při zrušení.");
                });
            });
        });
    }

    function bindForm(modal) {
        var form = modal.querySelector("#dash-ride-email-form");
        if (!form) return;
        form.addEventListener("submit", function (e) {
            e.preventDefault();
            var errEl = modal.querySelector("#dash-ride-email-error");
            var submitBtn = modal.querySelector("#dash-ride-email-submit");
            var recipient = modal.querySelector("#dash-ride-email-recipient");
            var dateInput = modal.querySelector("#dash-ride-email-date");
            var rzInput = modal.querySelector("#dash-ride-email-rz-id");
            var driverInput = modal.querySelector("#dash-ride-email-driver-id");
            var pksInput = modal.querySelector("#dash-ride-email-filter-pks");
            if (errEl) {
                errEl.hidden = true;
                errEl.textContent = "";
            }
            if (submitBtn) {
                submitBtn.disabled = true;
                submitBtn.dataset.prevLabel = submitBtn.textContent || "";
                submitBtn.textContent = "Připravuji PDF přílohy…";
            }
            var globalBusy = document.getElementById("jedis-global-busy");
            if (globalBusy) {
                var busyLabel = globalBusy.querySelector(".jedis-busy-overlay__label");
                if (busyLabel) busyLabel.textContent = "Připravuji PDF přílohy e-mailu…";
                globalBusy.classList.add("is-active");
            }
            var payload = {
                date: dateInput ? dateInput.value : "",
                vehicle_rz_id: rzInput ? rzInput.value : "",
                driver_id: driverInput ? driverInput.value : "",
                filter_pks: pksInput ? pksInput.value : "",
                recipient_email: recipient ? recipient.value.trim() : "",
            };
            fetch(modal.getAttribute("data-prepare-url"), {
                method: "POST",
                credentials: "same-origin",
                headers: {
                    "Content-Type": "application/json",
                    "X-CSRFToken": csrfToken(),
                },
                body: JSON.stringify(payload),
            }).then(function (resp) {
                if (resp.status === 400 || resp.status === 503) {
                    return resp.json().then(function (data) {
                        throw new Error((data && data.error) || "Příprava e-mailu selhala.");
                    }).catch(function (jsonErr) {
                        if (jsonErr instanceof Error && jsonErr.message) {
                            throw jsonErr;
                        }
                        return resp.text().then(function (text) {
                            throw new Error(text || "Příprava e-mailu selhala.");
                        });
                    });
                }
                if (!resp.ok) {
                    return resp.text().then(function (text) {
                        throw new Error(text || "Příprava e-mailu selhala.");
                    });
                }
                return resp.blob().then(function (blob) {
                    var filename = parseFilename(
                        resp.headers.get("Content-Disposition"),
                        "jizda.eml"
                    );
                    openEmlBlob(blob, filename);
                    closeModal(modal);
                    window.setTimeout(function () {
                        window.location.reload();
                    }, 2500);
                });
            }).catch(function (err) {
                if (errEl) {
                    errEl.textContent = err.message || "Chyba při přípravě e-mailu.";
                    errEl.hidden = false;
                }
            }).finally(function () {
                if (submitBtn) {
                    submitBtn.disabled = false;
                    if (submitBtn.dataset.prevLabel) {
                        submitBtn.textContent = submitBtn.dataset.prevLabel;
                    }
                }
                var globalBusy = document.getElementById("jedis-global-busy");
                if (globalBusy) globalBusy.classList.remove("is-active");
            });
        });
    }

    function init() {
        var modal = document.getElementById("dash-ride-email-modal");
        if (!modal) return;
        if (modal.parentElement !== document.body) {
            document.body.appendChild(modal);
        }
        bindOpenButtons(modal);
        bindPresetSelect(modal);
        bindSavePreset(modal);
        bindCancelButtons(modal);
        bindForm(modal);
        modal.querySelectorAll("[data-dash-ride-email-modal-close]").forEach(function (el) {
            el.addEventListener("click", function (e) {
                e.preventDefault();
                closeModal(modal);
            });
        });
        document.addEventListener("keydown", function (e) {
            if (e.key === "Escape" && !modal.hidden) closeModal(modal);
        });
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", init);
    } else {
        init();
    }
})();
