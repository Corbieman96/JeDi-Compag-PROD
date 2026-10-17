(function (global) {

    "use strict";



    const SERIES_PAUSE_MS = 2500;

    const PRINT_DIALOG_FALLBACK_MS = 8000;

    const PRINT_FINISH_DELAY_MS = 300;

    /** Poslední úklid blob/iframe, pokud afterprint vůbec nepřijde (paměť). */
    const PRINT_BLOB_SAFETY_CLEANUP_MS = 30 * 60 * 1000;

    const NO_PRINT_MESSAGE = "Není nic k tisku.";



    function sleep(ms) {

        return new Promise(function (resolve) {

            setTimeout(resolve, ms);

        });

    }



    function rowKind(row) {

        return ((row && row.kind) || "").toLowerCase();

    }



    function printTargetUrl(row) {

        if (!row) {

            return "";

        }

        return row.print_url || row.url || "";

    }



    function isPdfUrl(url) {

        return (url || "").toLowerCase().indexOf(".pdf") !== -1;

    }



    function isPrintableRow(row) {

        const url = printTargetUrl(row);

        if (!url || row.warning) {

            return false;

        }

        const kind = rowKind(row);

        if (kind === "zpo" || kind === "pio" || kind === "pdf" || kind === "protocol_notes") {

            return true;

        }

        if (kind === "xlsx" || kind === "protocol") {

            return Boolean(row.print_url);

        }

        return isPdfUrl(url);

    }



    const EXCLUDED_FROM_ALL_KINDS = ["protocol", "protocol_notes", "pio"];

    const EXCLUDED_FROM_ALL_WITH_PROTOCOL_KINDS = ["protocol_notes", "pio"];



    function isExcludedFromAll(row) {

        return EXCLUDED_FROM_ALL_KINDS.indexOf(rowKind(row)) !== -1;

    }



    function filterRows(rows, printKind) {

        const kind = (printKind || "all").toLowerCase();

        const withUrl = (rows || []).filter(function (row) {

            return printTargetUrl(row);

        });

        if (!kind || kind === "all") {

            return withUrl.filter(isPrintableRow).filter(function (row) {

                return !isExcludedFromAll(row);

            });

        }

        if (kind === "all_with_protocol") {

            return withUrl.filter(isPrintableRow).filter(function (row) {

                return EXCLUDED_FROM_ALL_WITH_PROTOCOL_KINDS.indexOf(rowKind(row)) === -1;

            });

        }

        return withUrl.filter(function (row) {

            return rowKind(row) === kind;

        }).filter(isPrintableRow);

    }



    function humanizeMergeError(detail, status) {

        const text = (detail || "").trim();

        if (!text) {

            if (status === 400 || status === 404) {

                return NO_PRINT_MESSAGE;

            }

            return "";

        }

        if (text.indexOf("<") !== -1) {

            const match = text.match(/class="exception_value">([^<]+)</);

            if (match && match[1]) {

                return match[1].trim();

            }

            return NO_PRINT_MESSAGE;

        }

        if (text.length > 240) {

            return text.slice(0, 240) + "…";

        }

        return text;

    }



    function printBlobUrlDirect(blobUrl, revokeOnFinish) {

        return new Promise(function (resolve, reject) {

            const iframe = document.createElement("iframe");

                iframe.setAttribute("aria-hidden", "true");

                iframe.style.cssText = "position:fixed;width:0;height:0;border:0;opacity:0;pointer-events:none;";

            iframe.src = blobUrl;

            let promiseSettled = false;

            let cleaned = false;

            let fallbackTimer = null;

            let safetyTimer = null;

            let sawPrintMode = false;

            const printMql = typeof window.matchMedia === "function"

                ? window.matchMedia("print")

                : null;



            function teardownListeners(frameWin) {

                if (frameWin) {

                    frameWin.removeEventListener("afterprint", onFrameAfterPrint);

                }

                window.removeEventListener("afterprint", onParentAfterPrint);

                if (printMql) {

                    if (printMql.removeEventListener) {

                        printMql.removeEventListener("change", onPrintMediaChange);

                    } else if (printMql.removeListener) {

                        printMql.removeListener(onPrintMediaChange);

                    }

                }

                if (fallbackTimer !== null) {

                    clearTimeout(fallbackTimer);

                    fallbackTimer = null;

                }

                if (safetyTimer !== null) {

                    clearTimeout(safetyTimer);

                    safetyTimer = null;

                }

            }



            function resolveOnce() {

                if (promiseSettled) {

                    return;

                }

                promiseSettled = true;

                setTimeout(resolve, PRINT_FINISH_DELAY_MS);

            }



            function finish() {

                if (cleaned) {

                    return;

                }

                cleaned = true;

                const frameWin = iframe.contentWindow;

                teardownListeners(frameWin);

                if (revokeOnFinish !== false) {

                    URL.revokeObjectURL(blobUrl);

                }

                iframe.remove();

                resolveOnce();

            }



            function onFrameAfterPrint() {

                finish();

            }



            function onParentAfterPrint() {

                finish();

            }



            function onPrintMediaChange(mql) {

                const matches = mql && typeof mql.matches === "boolean" ? mql.matches : false;

                if (matches) {

                    sawPrintMode = true;

                    return;

                }

                if (sawPrintMode) {

                    finish();

                }

            }



            iframe.onload = function () {

                try {

                    const win = iframe.contentWindow;

                    if (!win) {

                        finish();

                        return;

                    }

                    win.addEventListener("afterprint", onFrameAfterPrint);

                    window.addEventListener("afterprint", onParentAfterPrint);

                    if (printMql) {

                        if (printMql.addEventListener) {

                            printMql.addEventListener("change", onPrintMediaChange);

                        } else if (printMql.addListener) {

                            printMql.addListener(onPrintMediaChange);

                        }

                    }

                    win.focus();

                    win.print();

                    // Po 8 s jen odblokovat UI — blob/iframe zrušit až po afterprint (ne dřív).
                    fallbackTimer = setTimeout(function () {

                        fallbackTimer = null;

                        resolveOnce();

                    }, PRINT_DIALOG_FALLBACK_MS);

                    safetyTimer = setTimeout(finish, PRINT_BLOB_SAFETY_CLEANUP_MS);

                } catch (err) {

                    teardownListeners(iframe.contentWindow);

                    if (revokeOnFinish !== false) {

                        URL.revokeObjectURL(blobUrl);

                    }

                    iframe.remove();

                    cleaned = true;

                    promiseSettled = true;

                    reject(err);

                }

            };



            iframe.onerror = function () {

                teardownListeners(iframe.contentWindow);

                if (revokeOnFinish !== false) {

                    URL.revokeObjectURL(blobUrl);

                }

                iframe.remove();

                cleaned = true;

                promiseSettled = true;

                reject(new Error("Nelze načíst PDF pro tisk."));

            };



            document.body.appendChild(iframe);

        });

    }



    function printBlob(blob) {

        const blobUrl = URL.createObjectURL(blob);

        return printBlobUrlDirect(blobUrl, true);

    }



    function printPdfUrl(url) {

        if ((url || "").indexOf("blob:") === 0) {

            return printBlobUrlDirect(url, true);

        }

        return fetch(url, { credentials: "same-origin" }).then(function (resp) {

            if (!resp.ok) {

                return resp.text().then(function (body) {

                    const detail = (body || "").trim();

                    throw new Error(detail || ("HTTP " + resp.status));

                });

            }

            return resp.blob();

        }).then(function (blob) {

            const blobUrl = URL.createObjectURL(blob);

            return printBlobUrlDirect(blobUrl, true);

        });

    }



    function runClientBulkPrint(rows, printKind, onStatus, onRowPrinted) {

        const filtered = filterRows(rows, printKind);

        if (!filtered.length) {

            onStatus("Nebyly nalezeny soubory k tisku pro vybranou volbu.", true);

            return Promise.resolve({ printed: 0, skipped: 0 });

        }



        const total = filtered.length;

        let chain = Promise.resolve();

        let printed = 0;

        let failed = 0;



        filtered.forEach(function (row, idx) {

            chain = chain.then(function () {

                if (idx > 0) {

                    return sleep(SERIES_PAUSE_MS);

                }

                return undefined;

            }).then(function () {

                const url = printTargetUrl(row);

                const label = row.label || url || "soubor";

                onStatus("Tisk " + (idx + 1) + " / " + total + ": " + label, false);

                return printPdfUrl(url).then(function () {

                    printed += 1;

                    if (typeof onRowPrinted === "function") {

                        onRowPrinted(row);

                    }

                }).catch(function (err) {

                    failed += 1;

                    const msg = (err && err.message) ? err.message : "";

                    onStatus(

                        "Tisk selhal u: " + label

                        + (msg ? " — " + msg : ""),

                        true

                    );

                });

            });

        });



        return chain.then(function () {

            if (printed) {

                onStatus("Odesláno na tiskárnu tohoto PC: " + printed + " souborů.", false);

            } else if (failed) {

                onStatus("Žádný soubor se nepodařilo vytisknout.", true);

            }

            return { printed: printed, skipped: failed };

        });

    }



    const STREAM_PDF_MARKER = new TextEncoder().encode("---PDF---\n");



    function findMarkerIndex(buffer, marker) {

        for (let i = 0; i <= buffer.length - marker.length; i += 1) {

            let matched = true;

            for (let j = 0; j < marker.length; j += 1) {

                if (buffer[i + j] !== marker[j]) {

                    matched = false;

                    break;

                }

            }

            if (matched) {

                return i;

            }

        }

        return -1;

    }



    function readMergedPdfStream(response, onProgress, onReady) {

        const reader = response.body && response.body.getReader ? response.body.getReader() : null;

        if (!reader) {

            return response.blob().then(function (blob) {

                return { blob: blob, downloadUrl: "" };

            });

        }

        const decoder = new TextDecoder();

        let pending = new Uint8Array(0);

        const pdfChunks = [];

        let inPdf = false;

        let downloadUrl = "";



        function appendPending(chunk) {

            const merged = new Uint8Array(pending.length + chunk.length);

            merged.set(pending);

            merged.set(chunk, pending.length);

            pending = merged;

        }



        function processTextLines(text) {

            const lines = text.split("\n");

            for (let i = 0; i < lines.length; i += 1) {

                const line = lines[i];

                if (!line) {

                    continue;

                }

                let payload;

                try {

                    payload = JSON.parse(line);

                } catch (err) {

                    continue;

                }

                if (payload.type === "error") {

                    throw new Error(payload.message || "Sloučený tisk selhal.");

                }

                if (payload.type === "ready") {

                    downloadUrl = payload.download_url || "";

                    if (typeof onReady === "function") {

                        onReady(payload);

                    }

                    continue;

                }

                if (payload.type === "progress" && typeof onProgress === "function") {

                    onProgress(payload);

                }

            }

        }



        function pump() {

            return reader.read().then(function (result) {

                if (result.value) {

                    if (inPdf) {

                        pdfChunks.push(result.value);

                    } else {

                        appendPending(result.value);

                        const markerAt = findMarkerIndex(pending, STREAM_PDF_MARKER);

                        if (markerAt !== -1) {

                            const textPart = decoder.decode(pending.slice(0, markerAt));

                            processTextLines(textPart);

                            const pdfStart = markerAt + STREAM_PDF_MARKER.length;

                            if (pdfStart < pending.length) {

                                pdfChunks.push(pending.slice(pdfStart));

                            }

                            pending = new Uint8Array(0);

                            inPdf = true;

                        } else if (pending.length > STREAM_PDF_MARKER.length) {

                            const safeLen = pending.length - STREAM_PDF_MARKER.length;

                            const textPart = decoder.decode(pending.slice(0, safeLen));

                            processTextLines(textPart);

                            pending = pending.slice(safeLen);

                        }

                    }

                }

                if (result.done) {

                    if (!inPdf) {

                        processTextLines(decoder.decode(pending));

                        if (downloadUrl) {

                            return fetch(downloadUrl, { credentials: "same-origin" }).then(function (resp) {

                                if (!resp.ok) {

                                    throw new Error("Sloučené PDF nebylo dokončeno.");

                                }

                                return resp.blob().then(function (blob) {

                                    return { blob: blob, downloadUrl: downloadUrl };

                                });

                            });

                        }

                        throw new Error("Sloučené PDF nebylo dokončeno.");

                    }

                    return {
                        blob: new Blob(pdfChunks, { type: "application/pdf" }),
                        downloadUrl: downloadUrl,
                    };

                }

                return pump();

            });

        }



        return pump();

    }



    function mergedDownloadFilename(driveDate, printKind) {

        const datePart = (driveDate || "den").trim();

        const kindPart = (printKind || "all").trim().toLowerCase() || "all";

        return "tisk_" + datePart + "_" + kindPart + ".pdf";

    }



    function triggerFileDownload(url, filename) {

        if (!url) {

            return;

        }

        const link = document.createElement("a");

        link.href = url;

        link.download = filename || "tisk_slouceny.pdf";

        link.rel = "noopener";

        document.body.appendChild(link);

        link.click();

        link.remove();

    }



    function downloadBlob(blob, filename) {

        if (!blob) {

            return;

        }

        const url = URL.createObjectURL(blob);

        triggerFileDownload(url, filename);

        window.setTimeout(function () {

            URL.revokeObjectURL(url);

        }, 1000);

    }



    function runMergedBulkPrint(opts) {
        const mergeUrl = opts && opts.mergeUrl;
        const driveDate = opts && opts.date;
        const printKind = (opts && opts.printKind) || "all";
        const vehicleRzId = Number((opts && opts.vehicleRzId) || 0) || 0;
        const driverId = (opts && opts.driverId) || "";
        const filterPks = (opts && opts.filterPks) || "";
        const csrfToken = opts && opts.csrfToken;
        const rows = (opts && opts.rows) || [];
        const onStatus = opts && opts.onStatus;
        const onRowPrinted = opts && opts.onRowPrinted;
        const onProgress = opts && opts.onProgress;
        const onProgressStart = opts && opts.onProgressStart;
        const onProgressEnd = opts && opts.onProgressEnd;
        const onMergedReady = opts && opts.onMergedReady;
        if (!mergeUrl || !driveDate || !csrfToken) {
            if (onStatus) {
                onStatus("Chybí konfigurace sloučeného tisku.", true);
            }
            return Promise.resolve({ printed: 0, skipped: 0 });
        }
        const filteredEarly = filterRows(rows, printKind);
        if (!filteredEarly.length) {
            if (typeof onProgressEnd === "function") {
                onProgressEnd();
            }
            if (onStatus) {
                onStatus(NO_PRINT_MESSAGE, true);
            }
            return Promise.resolve({ printed: 0, skipped: 0 });
        }
        if (typeof onProgressStart === "function") {
            onProgressStart();
        }
        if (onStatus) {
            onStatus("Připravuji sloučené PDF…", false);
        }
        const body = new FormData();
        body.append("date", driveDate);
        body.append("print_kind", printKind);
        if (vehicleRzId > 0) {
            body.append("vehicle_rz_id", String(vehicleRzId));
        }
        if (filterPks) {
            body.append("pks", filterPks);
        }
        if (driverId !== "" && driverId !== null && driverId !== undefined) {
            body.append("driver_id", String(driverId));
        }
        body.append("stream", "1");
        return fetch(mergeUrl, {
            method: "POST",
            credentials: "same-origin",
            headers: { "X-CSRFToken": csrfToken },
            body: body,
        }).then(function (resp) {
            if (!resp.ok) {
                return resp.text().then(function (detail) {
                    throw new Error(humanizeMergeError(detail, resp.status) || ("HTTP " + resp.status));
                });
            }
            return readMergedPdfStream(resp, onProgress, function (readyPayload) {
                const filteredEarly = filterRows(rows, printKind);
                const earlyResult = {
                    printed: filteredEarly.length,
                    skipped: 0,
                    blob: null,
                    downloadUrl: readyPayload.download_url || "",
                    downloadFilename: mergedDownloadFilename(driveDate, printKind),
                };
                if (typeof onMergedReady === "function") {
                    onMergedReady(earlyResult);
                }
            });
        }).then(function (streamResult) {
            const blob = streamResult.blob;
            const downloadUrl = streamResult.downloadUrl || "";
            const filtered = filterRows(rows, printKind);
            const downloadFilename = mergedDownloadFilename(driveDate, printKind);
            const readyResult = {
                printed: filtered.length,
                skipped: 0,
                blob: blob,
                downloadUrl: downloadUrl,
                downloadFilename: downloadFilename,
            };
            if (typeof onMergedReady === "function") {
                onMergedReady(readyResult);
            }
            return printBlob(blob).then(function () {
                filtered.forEach(function (row) {
                    if (typeof onRowPrinted === "function") {
                        onRowPrinted(row);
                    }
                });
                if (onStatus) {
                    onStatus(
                        "Odesláno na tiskárnu: 1 sloučený PDF (" + filtered.length + " souborů). PDF lze stáhnout v dialogu.",
                        false
                    );
                }
                return readyResult;
            });
        }).catch(function (err) {
            const msg = (err && err.message) ? err.message : "";
            if (onStatus) {
                if (msg === NO_PRINT_MESSAGE) {
                    onStatus(NO_PRINT_MESSAGE, true);
                } else {
                    onStatus("Sloučený tisk selhal" + (msg ? " — " + msg : ""), true);
                }
            }
            return { printed: 0, skipped: 1 };
        }).finally(function () {
            if (typeof onProgressEnd === "function") {
                onProgressEnd();
            }
        });
    }

    global.JedisClientBulkPrint = {

        runClientBulkPrint: runClientBulkPrint,

        runMergedBulkPrint: runMergedBulkPrint,

        filterRows: filterRows,

        printPdfUrl: printPdfUrl,

        printTargetUrl: printTargetUrl,

        isPrintableRow: isPrintableRow,

        downloadBlob: downloadBlob,

        triggerFileDownload: triggerFileDownload,

        mergedDownloadFilename: mergedDownloadFilename,

    };

}(window));

