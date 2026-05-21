"""
sky_intercept.py — mitmproxy addon untuk intercept Sky session
============================================================
Jalankan di laptop/PC kamu:

  pip install mitmproxy
  mitmproxy -s sky_intercept.py --listen-port 8080

Lalu di HP Android:
  Settings → WiFi → Proxy → Manual → IP laptop, port 8080
  Buka browser → https://mitm.it → install certificate
  Buka game Sky → login → session otomatis ter-intercept!

Session akan disimpan ke: sky_sessions.json
"""

import json
import os
import re
from datetime import datetime
from mitmproxy import http, ctx

TARGET_HOST  = "live.radiance.thatgamecompany.com"
OUTPUT_FILE  = "sky_sessions.json"


class SkySessionInterceptor:
    def __init__(self):
        self.sessions: dict = self._load_existing()
        ctx.log.info(f"🌟 Sky Session Interceptor aktif")
        ctx.log.info(f"📁 Sessions disimpan ke: {os.path.abspath(OUTPUT_FILE)}")

    def _load_existing(self) -> dict:
        if os.path.exists(OUTPUT_FILE):
            with open(OUTPUT_FILE) as f:
                return json.load(f)
        return {}

    def _save(self):
        with open(OUTPUT_FILE, "w") as f:
            json.dump(self.sessions, f, indent=2)

    def request(self, flow: http.HTTPFlow):
        """Intercept semua request ke Sky server."""
        if TARGET_HOST not in flow.request.host:
            return

        hdrs   = dict(flow.request.headers)
        s_val  = hdrs.get("session", hdrs.get("Session", ""))
        u_val  = hdrs.get("user-id", hdrs.get("User-Id", ""))
        path   = flow.request.path

        ctx.log.info(f"→ {flow.request.method} {path}")
        if s_val: ctx.log.info(f"   session : {s_val[:16]}...")
        if u_val: ctx.log.info(f"   user-id : {u_val}")

        if s_val and u_val:
            key = u_val
            if key not in self.sessions or self.sessions[key]["session"] != s_val:
                self.sessions[key] = {
                    "user_id":    u_val,
                    "session":    s_val,
                    "path":       path,
                    "captured_at": datetime.now().isoformat(),
                }
                self._save()
                ctx.log.warn(f"✅ SESSION CAPTURED! user-id={u_val}")
                ctx.log.warn(f"   /session set {u_val} {s_val}")
                ctx.log.warn(f"   Disimpan ke {OUTPUT_FILE}")

    def response(self, flow: http.HTTPFlow):
        """Intercept response dari oauth_redirect — cek session di sini."""
        if TARGET_HOST not in flow.request.host:
            return

        path = flow.request.path
        body = flow.response.text if flow.response else ""

        # oauth_redirect return {id, alias, token}
        if "oauth_redirect" in path and flow.response.status_code == 200:
            ctx.log.warn(f"🎯 oauth_redirect response: {body[:200]}")
            try:
                data = json.loads(body)
                ctx.log.warn(f"   Sky ID : {data.get('id')}")
                ctx.log.warn(f"   Alias  : {data.get('alias')}")
                ctx.log.warn(f"   Token  : {str(data.get('token',''))[:40]}...")
            except Exception:
                pass

        # auth/login response — kalau dapat 200 ada session!
        if "auth/login" in path and flow.response and flow.response.status_code == 200:
            ctx.log.warn(f"🎯 auth/login 200! body: {body[:300]}")


addons = [SkySessionInterceptor()]
