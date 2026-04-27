// ===============================================
//  NFCReader – obsługa skanera NFC (HID + Web NFC)
// ===============================================

class NFCReader {
    constructor(inputElementId, onScanCallback) {
        this.input = document.getElementById(inputElementId);
        this.onScanCallback = onScanCallback;
        this._boundKeyHandler = this._handleKey.bind(this);
        this._timeoutId = null;
        this._listening = false;

        this.mode = ("NDEFReader" in window) ? "webnfc" : "hid";
        console.log("[NFCReader] Tryb:", this.mode);
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

            ndef.addEventListener("reading", ({ message }) => {
                if (!this._listening) return;
                for (const record of message.records) {
                    try {
                        const decoder = new TextDecoder(record.encoding || "utf-8");
                        const text = decoder.decode(record.data);
                        const parsed = this._tryParse(text);
                        if (parsed) {
                            clearTimeout(this._timeoutId);
                            this.onScanCallback(parsed);
                            return;
                        }
                    } catch (e) {
                        console.warn("[NFCReader] Błąd rekordu:", e);
                    }
                }
                console.warn("[NFCReader] Brak czytelnego rekordu NFC.");
            });

            ndef.addEventListener("readingerror", () => {
                if (!this._listening) return;
                showNFCError("Błąd odczytu karty NFC. Spróbuj ponownie.");
            });

        } catch (err) {
            console.error("[NFCReader] Web NFC niedostępny, fallback do HID:", err);
            this.mode = "hid";
            this._updateModeLabel();
            this._startHID();
        }
    }

    _startHID() {
        if (!this.input) {
            console.error("[NFCReader] Nie znaleziono elementu input.");
            return;
        }
        this.input.focus();
        this.input.addEventListener("keydown", this._boundKeyHandler);
    }

    _handleKey(e) {
        this._resetTimeout();
        if (e.key !== "Enter") return;

        const raw = this.input.value.trim();
        this.input.value = "";
        this.input.focus();

        const parsed = this._tryParse(raw);
        if (parsed) {
            this.onScanCallback(parsed);
        } else {
            showNFCError("Błąd odczytu karty NFC – nieprawidłowy format danych.");
        }
    }

    _resetTimeout(seconds = 30) {
        clearTimeout(this._timeoutId);
        this._timeoutId = setTimeout(() => {
            document.dispatchEvent(new Event("nfc-timeout"));
        }, seconds * 1000);
    }

    _tryParse(text) {
        try {
            const obj = JSON.parse(text);
            if (obj && obj.userName && obj.hash) return obj;
        } catch (_) {}
        return null;
    }

    _updateModeLabel() {
        const label = document.getElementById("nfc-mode-label");
        if (!label) return;
        const alertEl = label.closest(".alert");
        if (this.mode === "webnfc") {
            label.innerHTML = '<i class="bi bi-phone"></i> Tryb: <strong>NFC tabletu</strong> – przyłóż kartę do tylnej obudowy urządzenia';
            if (alertEl) {
                alertEl.classList.remove("alert-secondary");
                alertEl.classList.add("alert-info");
            }
        } else {
            label.innerHTML = '<i class="bi bi-usb-symbol"></i> Tryb: <strong>Skaner USB</strong> – przyłóż kartę do czytnika';
        }
    }
}

window.NFCReader = NFCReader;


// ===============================================
//  showNFCError – błąd NFC z przyciskiem Zamknij
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
        color: #fff;
        padding: 28px 32px;
        border-radius: 16px;
        box-shadow: 0 8px 32px rgba(0,0,0,0.5);
        z-index: 9999;
        text-align: center;
        min-width: 280px;
        max-width: 90vw;
        font-size: 1.1rem;
    `;
    div.innerHTML = `
        <div style="font-size:2.5rem; margin-bottom:12px;">⚠️</div>
        <div style="margin-bottom:20px; font-weight:600;">${message}</div>
        <button onclick="document.getElementById('nfc-error-toast').remove()"
                style="
                    background:#fff;
                    color:#8b0000;
                    border:none;
                    padding:10px 32px;
                    border-radius:8px;
                    font-size:1rem;
                    font-weight:700;
                    cursor:pointer;
                    min-height:44px;
                ">
            Zamknij
        </button>
    `;
    document.body.appendChild(div);
}

window.showNFCError = showNFCError;


// ===============================================
//  initIssueNFC – helper do wydawania przedmiotu
// ===============================================
function initIssueNFC(apiUrl, onFoundCallback, onNotFoundCallback) {
    const reader = new NFCReader("nfc-input", (data) => {
        fetch(apiUrl + "/" + encodeURIComponent(data.hash))
            .then(res => {
                if (res.status === 200) return res.json();
                if (res.status === 404) return null;
                throw new Error("Błąd serwera: " + res.status);
            })
            .then(json => {
                if (json) {
                    onFoundCallback(json);
                } else {
                    onNotFoundCallback();
                }
            })
            .catch(() => {
                onNotFoundCallback();
            });
    });
    reader.startListening();
    return reader;
}

window.initIssueNFC = initIssueNFC;