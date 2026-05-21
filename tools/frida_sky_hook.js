/**
 * frida_sky_hook.js
 * Hook Sky: Children of the Light untuk extract session + user_id
 *
 * Cara pakai:
 *   frida -U -f com.tgc.sky.android -l frida_sky_hook.js --no-pause
 *   # atau via runner:
 *   python frida_runner.py
 *
 * Target: libBootloader.so (native library Sky)
 * Method: Hook network calls + memory scan untuk cari session header
 */

"use strict";

// ── Warna output ─────────────────────────────────────────────────────────────
const C = {
    ok:   "\x1b[92m[+]\x1b[0m",
    info: "\x1b[96m[*]\x1b[0m",
    warn: "\x1b[93m[!]\x1b[0m",
    err:  "\x1b[91m[-]\x1b[0m",
};

// ── Hasil yang sudah di-capture ───────────────────────────────────────────────
const captured = {
    session: null,
    user_id: null,
};

function emit(data) {
    // Kirim ke Python runner via RPC / console
    console.log("CAPTURED:" + JSON.stringify(data));
    send(data);                       // Frida RPC → frida_runner.py
}

function tryCapture(session, userId) {
    if (session && userId && !captured.session) {
        captured.session = session;
        captured.user_id = userId;
        console.log(C.ok + " SESSION  : " + session.substring(0, 20) + "...");
        console.log(C.ok + " USER_ID  : " + userId);
        emit({ type: "session", session: session, user_id: userId });
    }
}

// ─────────────────────────────────────────────────────────────────────────────
// 1. Hook Java: OkHttp / HttpURLConnection untuk tangkap header request
// ─────────────────────────────────────────────────────────────────────────────
function hookJavaHttp() {
    Java.perform(function () {

        // ── OkHttp3 Request.Builder.header() ─────────────────────────────────
        try {
            const RequestBuilder = Java.use("okhttp3.Request$Builder");
            RequestBuilder.header.overload("java.lang.String", "java.lang.String")
                .implementation = function (name, value) {
                    const n = name.toLowerCase();
                    if (n === "session")  captured._session  = value;
                    if (n === "user-id")  captured._user_id  = value;
                    if (captured._session && captured._user_id)
                        tryCapture(captured._session, captured._user_id);
                    return this.header(name, value);
                };
            console.log(C.info + " Hook OkHttp3 Request.Builder.header OK");
        } catch (e) {
            console.log(C.warn + " OkHttp3: " + e.message);
        }

        // ── OkHttp3 addHeader ─────────────────────────────────────────────────
        try {
            const RequestBuilder = Java.use("okhttp3.Request$Builder");
            RequestBuilder.addHeader.overload("java.lang.String", "java.lang.String")
                .implementation = function (name, value) {
                    const n = name.toLowerCase();
                    if (n === "session")  captured._session  = value;
                    if (n === "user-id")  captured._user_id  = value;
                    if (captured._session && captured._user_id)
                        tryCapture(captured._session, captured._user_id);
                    return this.addHeader(name, value);
                };
            console.log(C.info + " Hook OkHttp3 addHeader OK");
        } catch (e) { /* silent */ }

        // ── HttpURLConnection setRequestProperty ──────────────────────────────
        try {
            const HttpURLConnection = Java.use("java.net.HttpURLConnection");
            HttpURLConnection.setRequestProperty.implementation = function (key, value) {
                const k = key.toLowerCase();
                if (k === "session")  captured._session  = value;
                if (k === "user-id")  captured._user_id  = value;
                if (captured._session && captured._user_id)
                    tryCapture(captured._session, captured._user_id);
                return this.setRequestProperty(key, value);
            };
            console.log(C.info + " Hook HttpURLConnection.setRequestProperty OK");
        } catch (e) {
            console.log(C.warn + " HttpURLConnection: " + e.message);
        }

        // ── Canvas/Sky SystemAccounts — UpdateServerInfo ──────────────────────
        // Dari source Canvas Open Source:
        // UpdateServerInfo(int type, int state, String accountId, String alias)
        try {
            const SystemAccounts = Java.use("com.tgc.sky.SystemAccounts_android");
            SystemAccounts.UpdateServerInfo.implementation = function (i, i2, accountId, alias) {
                console.log(C.ok + " UpdateServerInfo: accountId=" + accountId + " alias=" + alias);
                // accountId di sini adalah Sky UUID (user_id)
                if (accountId && accountId.length > 8)
                    captured._user_id = accountId;
                emit({ type: "server_info", user_id: accountId, alias: alias });
                return this.UpdateServerInfo(i, i2, accountId, alias);
            };
            console.log(C.info + " Hook SystemAccounts.UpdateServerInfo OK");
        } catch (e) {
            console.log(C.warn + " SystemAccounts: " + e.message);
        }

        // ── Canvas WebLogin.submitSignInState ─────────────────────────────────
        // submitSignInState(String id, String alias, String signature/token)
        try {
            const WebLogin = Java.use("git.artdeell.skymodloader.auth.WebLogin");
            // method private — harus akses via reflection
            const cls = WebLogin.class;
            const method = cls.getDeclaredMethod("submitSignInState",
                Java.use("java.lang.String").class,
                Java.use("java.lang.String").class,
                Java.use("java.lang.String").class
            );
            method.setAccessible(true);
            WebLogin.submitSignInState = method;

            WebLogin.submitSignInState.implementation = function (id, alias, signature) {
                console.log(C.ok + " WebLogin.submitSignInState:");
                console.log("   id       : " + id);
                console.log("   alias    : " + alias);
                console.log("   signature: " + signature.substring(0, 40) + "...");
                emit({ type: "web_login", id: id, alias: alias, token: signature });
                return this.submitSignInState(id, alias, signature);
            };
            console.log(C.info + " Hook WebLogin.submitSignInState OK");
        } catch (e) {
            console.log(C.warn + " WebLogin: " + e.message);
        }

        // ── OnSystemAccount (JNI callback) ────────────────────────────────────
        try {
            const SystemAccounts = Java.use("com.tgc.sky.SystemAccounts_android");
            SystemAccounts.UpdateClientInfo.implementation = function (clientInfo) {
                try {
                    const state = clientInfo.state.toString();
                    const id    = clientInfo.accountId ? clientInfo.accountId.toString() : "";
                    const alias = clientInfo.alias     ? clientInfo.alias.toString()     : "";
                    const sig   = clientInfo.signature ? clientInfo.signature.toString() : "";
                    if (id || sig) {
                        console.log(C.ok + " UpdateClientInfo: state=" + state +
                            " id=" + id + " alias=" + alias);
                        if (id) captured._user_id = id;
                        if (sig && sig.startsWith("eyJ")) {
                            // signature adalah JWT token
                            emit({ type: "client_info", user_id: id, alias: alias, token: sig });
                        }
                    }
                } catch (_) {}
                return this.UpdateClientInfo(clientInfo);
            };
            console.log(C.info + " Hook SystemAccounts.UpdateClientInfo OK");
        } catch (e) {
            console.log(C.warn + " UpdateClientInfo: " + e.message);
        }
    });
}

// ─────────────────────────────────────────────────────────────────────────────
// 2. Hook Native: libssl — SSL_write untuk tangkap plaintext sebelum encrypt
// ─────────────────────────────────────────────────────────────────────────────
function hookSSLWrite() {
    // Cari libssl di memory
    const sslModules = ["libssl.so", "libssl_3.so", "libboringssl.so"];
    let sslMod = null;
    for (const name of sslModules) {
        sslMod = Process.findModuleByName(name);
        if (sslMod) { console.log(C.info + " Found SSL: " + name); break; }
    }
    if (!sslMod) { console.log(C.warn + " libssl tidak ditemukan"); return; }

    const SSL_write = Module.findExportByName(sslMod.name, "SSL_write");
    if (!SSL_write) { console.log(C.warn + " SSL_write export tidak ditemukan"); return; }

    Interceptor.attach(SSL_write, {
        onEnter: function (args) {
            // args[1] = buf, args[2] = num
            const buf = args[1];
            const num = args[2].toInt32();
            if (num <= 0 || num > 16384) return;

            try {
                const data = buf.readUtf8String(num);
                if (!data) return;

                // Hanya proses request ke Sky server
                if (!data.includes("radiance.thatgamecompany.com") &&
                    !data.includes("session") && !data.includes("user-id"))
                    return;

                console.log(C.info + " SSL_write (" + num + " bytes):");

                // Extract header session
                const sessMatch = data.match(/session:\s*([0-9a-f]{16,64})/i);
                const userMatch = data.match(/user-id:\s*([0-9a-f\-]{8,})/i);

                if (sessMatch) {
                    captured._session = sessMatch[1];
                    console.log(C.ok + " [SSL] session: " + sessMatch[1].substring(0, 20) + "...");
                }
                if (userMatch) {
                    captured._user_id = userMatch[1];
                    console.log(C.ok + " [SSL] user-id: " + userMatch[1]);
                }
                if (captured._session && captured._user_id)
                    tryCapture(captured._session, captured._user_id);

            } catch (_) {}
        }
    });
    console.log(C.info + " Hook SSL_write OK");
}

// ─────────────────────────────────────────────────────────────────────────────
// 3. Hook Native: libBootloader.so — Cari fungsi session di Sky binary
// ─────────────────────────────────────────────────────────────────────────────
function hookBootloader() {
    const bootMod = Process.findModuleByName("libBootloader.so");
    if (!bootMod) {
        console.log(C.warn + " libBootloader.so belum dimuat, akan retry...");
        // Retry saat module load
        Module.load("libBootloader.so");
        return;
    }

    console.log(C.info + " libBootloader.so @ " + bootMod.base + " size=" + bootMod.size);

    // Scan exports untuk cari fungsi yang berhubungan dengan session/account
    const exports = bootMod.enumerateExports();
    const interesting = exports.filter(e =>
        /session|account|auth|login|user/i.test(e.name)
    );

    if (interesting.length > 0) {
        console.log(C.info + " Interesting exports (" + interesting.length + "):");
        interesting.slice(0, 10).forEach(e =>
            console.log("   " + e.name + " @ " + e.address)
        );
    }

    // ── Scan memory untuk string "session" ───────────────────────────────────
    // Cari di region .data / .bss libBootloader.so
    try {
        Memory.scan(bootMod.base, bootMod.size,
            // Pattern: hex string 32 chars (session format)
            "00 [0-9a-f]{32} 00",
            {
                onMatch: function (address, size) {
                    try {
                        const val = address.readUtf8String(size).trim();
                        if (/^[0-9a-f]{32,64}$/.test(val)) {
                            console.log(C.info + " Memory session candidate @ " +
                                address + ": " + val.substring(0, 20) + "...");
                        }
                    } catch (_) {}
                },
                onComplete: function () {}
            }
        );
    } catch (_) {}

    // ── Hook fungsi get_Auth pattern (dari AutoWax4C analysis) ───────────────
    // Di binary Sky: AccountServerClient object ada di game[58]
    // offset +702 = user_id (UUID, 16 bytes)
    // offset +718 = session_id (16 bytes → 32 hex chars)
    //
    // Cari fungsi yang return 2 pointer dari object game
    hookGetAuthPattern(bootMod);
}

function hookGetAuthPattern(bootMod) {
    // Cari pattern JNI function yang match "GetAuth" atau "getSession"
    const jniPattern = [
        "Java_com_tgc_sky_SystemAccounts",
        "getSession",
        "getAuth",
        "createSession",
    ];

    const exports = bootMod.enumerateExports();
    for (const exp of exports) {
        for (const pat of jniPattern) {
            if (exp.name.toLowerCase().includes(pat.toLowerCase())) {
                console.log(C.info + " Hooking: " + exp.name);
                try {
                    Interceptor.attach(exp.address, {
                        onLeave: function (retval) {
                            try {
                                // Coba baca return value sebagai string
                                const val = retval.readUtf8String();
                                if (val && val.length > 8)
                                    console.log(C.ok + " " + exp.name + " → " + val.substring(0, 40));
                            } catch (_) {}
                        }
                    });
                } catch (_) {}
            }
        }
    }
}

// ─────────────────────────────────────────────────────────────────────────────
// 4. Scan memory process untuk cari session yang sudah ada
// ─────────────────────────────────────────────────────────────────────────────
function scanMemoryForSession() {
    console.log(C.info + " Scanning process memory untuk session...");

    const SESSION_PATTERN = /[0-9a-f]{32,64}/;
    const UUID_PATTERN    = /[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/;

    let found_sessions = [];
    let found_uuids    = [];

    Process.enumerateRanges("rw-").forEach(function (range) {
        if (range.size > 8 * 1024 * 1024) return; // skip > 8MB
        if (range.file && (
            range.file.path.includes("/system/") ||
            range.file.path.includes("/vendor/")
        )) return;

        try {
            Memory.scanSync(range.base, range.size,
                // Cari null-terminated string pola session hex 32
                "00 [0-9a-f]{2} [0-9a-f]{2} [0-9a-f]{2} [0-9a-f]{2}" +
                " [0-9a-f]{2} [0-9a-f]{2} [0-9a-f]{2} [0-9a-f]{2}" +
                " [0-9a-f]{2} [0-9a-f]{2} [0-9a-f]{2} [0-9a-f]{2}" +
                " [0-9a-f]{2} [0-9a-f]{2} [0-9a-f]{2} [0-9a-f]{2}"
            ).forEach(function (match) {
                try {
                    const s = match.address.readUtf8String(32);
                    if (s && SESSION_PATTERN.test(s))
                        found_sessions.push(s);
                } catch (_) {}
            });
        } catch (_) {}
    });

    if (found_sessions.length > 0) {
        console.log(C.ok + " Memory session candidates: " + found_sessions.length);
        found_sessions.slice(0, 5).forEach(s =>
            console.log("   " + s)
        );
        emit({ type: "memory_scan", candidates: found_sessions.slice(0, 10) });
    } else {
        console.log(C.warn + " Tidak ada session candidate di memory (Sky belum login?)");
    }
}

// ─────────────────────────────────────────────────────────────────────────────
// 5. RPC exports untuk Python runner
// ─────────────────────────────────────────────────────────────────────────────
rpc.exports = {
    getCaptured: function () {
        return captured;
    },
    scanMemory: function () {
        scanMemoryForSession();
        return captured;
    },
    getSession: function () {
        return {
            session: captured._session || captured.session || null,
            user_id: captured._user_id || captured.user_id || null,
        };
    }
};

// ─────────────────────────────────────────────────────────────────────────────
// MAIN — Jalankan semua hook
// ─────────────────────────────────────────────────────────────────────────────
console.log("\n" + C.info + " Sky CoTL Frida Hook v1.0");
console.log(C.info + " Target: com.tgc.sky.android");
console.log(C.info + " ─────────────────────────────────");

// Hook Java layer
hookJavaHttp();

// Hook SSL (network layer)
try { hookSSLWrite(); } catch (e) {
    console.log(C.warn + " SSL hook skip: " + e.message);
}

// Hook libBootloader native (tunggu sampai dimuat)
Java.perform(function () {
    Java.use("android.os.Process");
    setTimeout(function () {
        try { hookBootloader(); } catch (e) {
            console.log(C.warn + " Bootloader hook: " + e.message);
        }
    }, 3000);
});

console.log(C.info + " Semua hook aktif! Buka Sky dan login...");
console.log(C.info + " ─────────────────────────────────\n");
