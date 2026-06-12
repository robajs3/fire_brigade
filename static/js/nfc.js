// ===============================================
// NFCReader – Web NFC + HID Reader
// ===============================================

class NFCReader {
    constructor(inputElementId, onScanCallback) {
        this.input = document.getElementById(inputElementId);
        this.onScanCallback = onScanCallback;

        this._boundKeyHandler = this._handleKey.bind(this);
        this._timeoutId = null;
        this._listening = false;

        this.mode = "NDEFReader" in window ? "webnfc" : "hid";

        console.log("[NFCReader] Mode:", this.mode);

        this._updateModeLabel();
    }

    startListening() {
        this._listening = true;

        if (this.mode === "webnfc") {
            this._startWebNFC();
        } else {
            this._startHID();
        }

        this._resetTimeout();
    }

    stopListening() {
        if (!this._listening) return;

        this._listening = false;

        clearTimeout(this._timeoutId);

        if (this.mode === "hid" && this.input) {
            this.input.removeEventListener("keydown", this._boundKeyHandler);
        }
    }

    async _startWebNFC() {
        try {
            const ndef = new NDEFReader();
            await ndef.scan();

            console.log("[NFCReader] Web NFC started");

            ndef.addEventListener("reading", (event) => {
                if (!this._listening) return;

                console.log("[NFCReader] reading event:", event);

                const serialNumber =
                    event.serialNumber ||
                    event.serialnumber ||
                    "";

                console.log("[NFCReader] serialNumber:", serialNumber);

                // ===================================================
                // PRIORYTET 1 — UID karty z Web NFC
                // ===================================================
                if (typeof serialNumber === "string" && serialNumber.trim() !== "") {
                    clearTimeout(this._timeoutId);

                    const result = { id: serialNumber.trim() };

                    console.log("[NFCReader] callback:", result);
                    this.onScanCallback(result);

                    return;
                }

                // ===================================================
                // PRIORYTET 2 — Rekord NDEF
                // ===================================================
                if (event.message && event.message.records) {
                    for (const record of event.message.records) {
                        try {
                            const decoder = new TextDecoder(record.encoding || "utf-8");
                            const text = decoder.decode(record.data);

                            console.log("[NFCReader] record:", text);

                            const parsed = this._tryParse(text);

                            if (parsed) {
                                clearTimeout(this._timeoutId);

                                console.log("[NFCReader] callback:", parsed);
                                this.onScanCallback(parsed);

                                return;
                            }
                        } catch (err) {
                            console.warn("[NFCReader] Record decode error:", err);
                        }
                    }
                }

                console.warn("[NFCReader] No readable NFC data");
                showNFCError("Nie udało się odczytać danych karty NFC.");
            });

            ndef.addEventListener("readingerror", () => {
                if (!this._listening) return;

                console.error("[NFCReader] readingerror");
                showNFCError("Błąd odczytu karty NFC.");
            });
        } catch (err) {
            console.error("[NFCReader] Web NFC unavailable:", err);

            this.mode = "hid";
            this._updateModeLabel();
            this._startHID();
        }
    }

    _startHID() {
        if (!this.input) {
            console.error("[NFCReader] Input not found");
            return;
        }

        this.input.focus();
        this.input.addEventListener("keydown", this._boundKeyHandler);

        console.log("[NFCReader] HID mode started");
    }

    _handleKey(e) {
        this._resetTimeout();

        if (e.key !== "Enter") return;

        const raw = this.input.value.trim();
        this.input.value = "";
        this.input.focus();

        console.log("[NFCReader] HID raw:", raw);

        const parsed = this._tryParse(raw);

        if (parsed) {
            console.log("[NFCReader] callback:", parsed);
            this.onScanCallback(parsed);
        } else {
            showNFCError("Nieprawidłowy format danych NFC.");
        }
    }

    _tryParse(text) {
        if (!text) return null;

        // Próba parsowania JSON — bierz uid/serialNumber, ignoruj hash
        try {
            const obj = JSON.parse(text);
            if (obj) {
                const uid =
                    obj.uid ||
                    obj.serialNumber ||
                    obj.serial_number ||
                    obj.id;

                if (uid) {
                    return { id: String(uid).trim() };
                }
            }
        } catch (_) {}

        // RAW — surowy tekst (np. czytnik HID wysyła sam UID)
        const value = text.trim();
        if (value.length > 0) {
            return { id: value };
        }

        return null;
    }

    _resetTimeout(seconds = 30) {
        clearTimeout(this._timeoutId);

        this._timeoutId = setTimeout(() => {
            document.dispatchEvent(new Event("nfc-timeout"));
        }, seconds * 1000);
    }

    _updateModeLabel() {
        const label = document.getElementById("nfc-mode-label");
        if (!label) return;

        const alertEl = label.closest(".alert");

        if (this.mode === "webnfc") {
            label.innerHTML = `
                <i class="bi bi-phone"></i>
                Tryb:
                <strong>NFC tabletu</strong>
                – przyłóż kartę do tylnej części urządzenia
            `;

            if (alertEl) {
                alertEl.classList.remove("alert-secondary");
                alertEl.classList.add("alert-info");
            }
        } else {
            label.innerHTML = `
                <i class="bi bi-usb-symbol"></i>
                Tryb:
                <strong>Skaner USB</strong>
                – przyłóż kartę do czytnika
            `;
        }
    }
}

window.NFCReader = NFCReader;

// ===============================================
// Error Toast
// ===============================================

function showNFCError(message) {
    const existing = document.getElementById("nfc-error-toast");
    if (existing) existing.remove();

    const div = document.createElement("div");
    div.id = "nfc-error-toast";

    div.style.cssText = `
        position: fixed;
        top: 50%;
        left: 50%;
        transform: translate(-50%, -50%);
        background: #8b0000;
        color: white;
        padding: 28px;
        border-radius: 16px;
        z-index: 9999;
        text-align: center;
        min-width: 280px;
        box-shadow: 0 8px 32px rgba(0,0,0,.4);
    `;

    div.innerHTML = `
        <div style="font-size:2rem;margin-bottom:10px;">⚠️</div>
        <div style="margin-bottom:20px;">${message}</div>
        <button
            onclick="document.getElementById('nfc-error-toast').remove()"
            style="
                border:none;
                border-radius:8px;
                padding:10px 24px;
                cursor:pointer;
                font-weight:bold;
            "
        >
            Zamknij
        </button>
    `;

    document.body.appendChild(div);
}

window.showNFCError = showNFCError;

// ===============================================
// Helper
// ===============================================

function initIssueNFC(apiUrl, onFoundCallback, onNotFoundCallback) {
    const reader = new NFCReader("nfc-input", (data) => {
        console.log("[NFCReader] scanned:", data);

        if (!data || !data.id) {
            console.error("[NFCReader] invalid data:", data);
            onNotFoundCallback();
            return;
        }

        fetch(apiUrl + "/" + encodeURIComponent(data.id))
            .then((res) => {
                if (res.status === 200) return res.json();
                if (res.status === 404) return null;
                throw new Error("HTTP " + res.status);
            })
            .then((json) => {
                if (json) onFoundCallback(json);
                else onNotFoundCallback();
            })
            .catch((err) => {
                console.error(err);
                onNotFoundCallback();
            });
    });

    reader.startListening();
    return reader;
}

window.initIssueNFC = initIssueNFC;
