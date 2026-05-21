@echo off
title Sky CoTL - ADB Fix & Session Grabber
color 0A
cls

echo.
echo ============================================================
echo    Sky CoTL - ADB Diagnosa ^& Fix (Windows)
echo ============================================================
echo.

:: ── Step 1: Cek ADB ──────────────────────────────────────────
echo [1/6] Cek ADB...
adb version >nul 2>&1
if %errorlevel% neq 0 (
    echo  [!] ADB tidak ditemukan di PATH
    echo.
    echo  Download ADB platform-tools:
    echo  https://developer.android.com/tools/releases/platform-tools
    echo.
    echo  Setelah download:
    echo  1. Extract ke C:\platform-tools\
    echo  2. Tambah C:\platform-tools ke PATH
    echo     atau copy adb.exe ke folder ini
    echo.
    pause
    start https://developer.android.com/tools/releases/platform-tools
    goto :end
)
for /f "tokens=*" %%i in ('adb version 2^>^&1') do echo  OK: %%i
echo.

:: ── Step 2: Kill dan restart ADB server ──────────────────────
echo [2/6] Restart ADB server...
adb kill-server >nul 2>&1
timeout /t 2 /nobreak >nul
adb start-server >nul 2>&1
echo  OK: ADB server restarted
echo.

:: ── Step 3: Cek devices ───────────────────────────────────────
echo [3/6] Cek device terhubung...
adb devices -l
echo.

:: Hitung device
set DEVICE_COUNT=0
for /f "skip=1 tokens=1,2" %%a in ('adb devices') do (
    if "%%b"=="device" set /a DEVICE_COUNT+=1
    if "%%b"=="unauthorized" (
        echo  [!] Device UNAUTHORIZED - tap Allow di HP!
        echo      Tunggu 10 detik lalu coba lagi...
        timeout /t 10 /nobreak >nul
        adb devices
    )
    if "%%b"=="offline" echo  [!] Device OFFLINE - cabut dan colok ulang USB
)

if %DEVICE_COUNT% gtr 0 (
    echo  [OK] %DEVICE_COUNT% device terdeteksi!
    goto :device_found
)

:: ── Device tidak ketemu ───────────────────────────────────────
echo  [!] Tidak ada device terdeteksi. Kemungkinan penyebab:
echo.
echo  PENYEBAB 1: USB Debugging belum aktif di HP
echo  ─────────────────────────────────────────────
echo  1. Settings ^> About Phone
echo  2. Tap "Build Number" 7x cepat
echo     (muncul "You are a developer!")
echo  3. Settings ^> Developer Options
echo  4. Aktifkan "USB Debugging"
echo  5. Colok ulang USB
echo.
echo  PENYEBAB 2: Mode USB salah
echo  ──────────────────────────
echo  Setelah colok USB, muncul notifikasi di HP
echo  Tap notifikasi → pilih "File Transfer" atau "MTP"
echo  BUKAN "Charge Only"!
echo.
echo  PENYEBAB 3: Driver ADB belum terinstall (Windows)
echo  ──────────────────────────────────────────────────
echo  Buka: Device Manager (Win+X ^> Device Manager)
echo  Cari device dengan tanda seru kuning (Unknown Device)
echo  Klik kanan ^> Update Driver
echo.
echo  Atau install Universal ADB Driver:
echo  https://adb.clockworkmod.com/
echo.

set /p FIX="Mau buka link Universal ADB Driver? [y/n]: "
if /i "%FIX%"=="y" start https://adb.clockworkmod.com/

echo.
echo  Setelah fix, tekan ENTER untuk coba lagi...
pause >nul
adb kill-server >nul 2>&1
timeout /t 1 /nobreak >nul
adb start-server >nul 2>&1
adb devices
echo.
goto :end

:device_found
:: ── Step 4: Cek Sky terinstall ────────────────────────────────
echo [4/6] Cek Sky terinstall...
adb shell pm list packages com.tgc.sky 2>nul | findstr "sky" >nul
if %errorlevel% equ 0 (
    for /f "tokens=*" %%p in ('adb shell pm list packages ^| findstr "sky"') do echo  Ditemukan: %%p
) else (
    echo  [!] Sky belum terinstall
    echo  Install dari Play Store: Sky: Children of the Light
    echo  Atau download APK: https://apkpure.com/sky-children-of-the-light
)
echo.

:: ── Step 5: Grab session via logcat ──────────────────────────
echo [5/6] Pilih metode grab session:
echo.
echo  [1] Logcat Monitor - Buka Sky ^& login saat monitoring
echo  [2] ADB over WiFi  - Tanpa kabel (perlu setup dulu)
echo  [3] HTTP Toolkit   - Buka panduan setup
echo  [4] Skip
echo.
set /p METHOD="Pilih [1-4]: "

if "%METHOD%"=="1" goto :logcat
if "%METHOD%"=="2" goto :wifi
if "%METHOD%"=="3" goto :httptoolkit
goto :end

:logcat
echo.
echo ============================================================
echo  LOGCAT MONITOR - Buka Sky dan Login Facebook sekarang!
echo ============================================================
echo.
echo  Script memantau log HP kamu...
echo  Segera: Buka Sky ^> tap Login ^> pilih Facebook ^> login
echo.
echo  Tekan Ctrl+C untuk berhenti
echo.
adb logcat -c >nul 2>&1
echo  Menunggu session... (Buka Sky sekarang!)
echo.

:: Monitor logcat dan cari session pattern
adb logcat -v tag *:S Sky:V tgc:V | findstr /i "session user_id userid login auth account"
goto :end

:wifi
echo.
echo ============================================================
echo  ADB over WiFi Setup
echo ============================================================
echo.
echo  SYARAT: HP dan laptop harus di WiFi yang SAMA
echo.
echo  Langkah otomatis:
:: Ambil IP HP
for /f "tokens=*" %%i in ('adb shell ip route ^| findstr "src"') do (
    echo  %%i
)
echo.
set /p HP_IP="Masukkan IP HP kamu (cek di Settings^>WiFi^>Details): "
if "%HP_IP%"=="" goto :end

:: Enable TCP/IP mode (butuh USB dulu)
echo  Mengaktifkan TCP/IP mode...
adb tcpip 5555
timeout /t 3 /nobreak >nul
echo  Connecting via WiFi ke %HP_IP%...
adb connect %HP_IP%:5555
timeout /t 2 /nobreak >nul
adb devices
echo.
echo  Kalau sudah terconnect, CABUT kabel USB
echo  ADB sekarang jalan via WiFi!
goto :end

:httptoolkit
echo.
start https://httptoolkit.com
echo  Browser dibuka ke httptoolkit.com
echo.
echo  Cara pakai HTTP Toolkit dengan ADB:
echo  1. Install HTTP Toolkit
echo  2. Buka ^> klik "Android Device via ADB"
echo  3. Klik "Setup Device" - otomatis install certificate
echo  4. Buka Sky ^> Login
echo  5. Di HTTP Toolkit, filter: live.radiance.thatgamecompany.com
echo  6. Lihat request, copy header "session" dan "user-id"
echo  7. Kirim ke bot: /session set ^<user-id^> ^<session^>
goto :end

:end
echo.
echo ============================================================
echo  Setelah dapat session, kirim ke bot Telegram:
echo  /session set ^<user-id^> ^<session^>
echo ============================================================
echo.
pause
