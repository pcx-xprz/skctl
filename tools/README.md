# Sky CoTL Session Tools

Tools untuk mendapatkan session Sky: Children of the Light.

## Install

```bash
pip install requests mitmproxy
```

## Cara Cepat

```bash
python session_grabber.py
```

Pilih mode dari menu interaktif.

---

## Mode 1 — mitmproxy Interceptor (Paling Andal)

Jalankan proxy di laptop, arahkan HP/emulator melewatinya.
Game Sky akan otomatis ter-intercept saat login.

```bash
python session_grabber.py --mode 1
```

**Atau manual:**
```bash
mitmproxy -s sky_intercept.py --listen-port 8080
```

Setup HP:
1. Settings → WiFi → Proxy → Manual → `[IP laptop]:8080`
2. Buka `http://mitm.it` di HP → install certificate
3. Buka Sky → login → session ter-capture!

---

## Mode 2 — Auto FB Cookie OAuth

Export cookies Facebook dari browser → script otomasi full OAuth flow.

```bash
# Dari file JSON (export pakai Cookie-Editor extension)
python session_grabber.py --mode 2

# Atau langsung pakai fb_oauth_auto.py
python fb_oauth_auto.py --cookies cookies.json
python fb_oauth_auto.py --cookie-string "c_user=...; xs=...; fr=..."
```

**Cara export cookies:**
1. Install ekstensi [Cookie-Editor](https://chrome.google.com/webstore/detail/cookie-editor) di Chrome
2. Buka `web.facebook.com` (sudah login)
3. Klik icon ekstensi → Export → Copy as JSON
4. Simpan ke `cookies.json`

---

## Mode 3 — Manual Input

Paling simpel — buka link, login FB, paste JSON yang muncul.

```bash
python session_grabber.py --mode 3
```

---

## Mode 4 — Panduan Emulator

Panduan setup BlueStacks / WSA / VirtualBox + HTTP Toolkit.

```bash
python session_grabber.py --mode 4
```

---

## Output

Semua mode menyimpan hasil ke `sky_session_result.json`:

```json
{
  "user_id": "d7cf185e-a94c-43e4-b6c1-522fb541e65f",
  "session": "a1b2c3d4e5f6...",
  "captured_at": "2026-05-21T10:00:00"
}
```

Lalu kirim ke bot Telegram:
```
/session set d7cf185e-a94c-43e4-b6c1-522fb541e65f a1b2c3d4e5f6...
```
