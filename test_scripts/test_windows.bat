@echo off
REM Windows Test Script for Ship Proxy System
REM Tests the proxy system using curl.exe on Windows

set PROXY=http://localhost:8080

echo 🚢 Ship Proxy System - Windows Test Suite
echo ==========================================
echo Proxy: %PROXY%
echo.

REM Check if curl is available
curl --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ❌ ERROR: curl is not installed or not in PATH
    echo Please install curl or use Windows 10/11 built-in curl
    pause
    exit /b 1
)

echo ✅ curl found, starting tests...
echo.

REM Wait for proxy to be ready
echo ⏳ Waiting for proxy to be ready...
for /l %%i in (1,1,30) do (
    curl -s --connect-timeout 2 -x %PROXY% http://httpbin.org/get >nul 2>&1
    if !errorlevel! equ 0 (
        echo ✅ Proxy is ready!
        goto :proxy_ready
    )
    timeout /t 1 >nul
)
echo ❌ Proxy not responding after 30 seconds
pause
exit /b 1

:proxy_ready
echo.

REM Test 1: Basic HTTP GET
echo 🧪 Test 1: Basic HTTP GET
curl -x %PROXY% http://httpforever.com/
if %errorlevel% equ 0 (
    echo ✅ PASS: Basic HTTP GET successful
) else (
    echo ❌ FAIL: Basic HTTP GET failed
)
echo.

REM Test 2: HTTPS GET
echo 🧪 Test 2: HTTPS GET
curl -x %PROXY% https://httpbin.org/get
if %errorlevel% equ 0 (
    echo ✅ PASS: HTTPS GET successful
) else (
    echo ❌ FAIL: HTTPS GET failed
)
echo.

REM Test 3: HTTP POST
echo 🧪 Test 3: HTTP POST
curl -x %PROXY% -X POST -d "test=data" http://httpbin.org/post
if %errorlevel% equ 0 (
    echo ✅ PASS: HTTP POST successful
) else (
    echo ❌ FAIL: HTTP POST failed
)
echo.

REM Test 4: HTTP PUT
echo 🧪 Test 4: HTTP PUT
curl -x %PROXY% -X PUT -d "put data" http://httpbin.org/put
if %errorlevel% equ 0 (
    echo ✅ PASS: HTTP PUT successful
) else (
    echo ❌ FAIL: HTTP PUT failed
)
echo.

REM Test 5: HTTP DELETE
echo 🧪 Test 5: HTTP DELETE
curl -x %PROXY% -X DELETE http://httpbin.org/delete
if %errorlevel% equ 0 (
    echo ✅ PASS: HTTP DELETE successful
) else (
    echo ❌ FAIL: HTTP DELETE failed
)
echo.

REM Test 6: Multiple requests (testing sequential processing)
echo 🧪 Test 6: Multiple concurrent requests
start /B curl -s -x %PROXY% http://httpbin.org/delay/1 -o test1.tmp
start /B curl -s -x %PROXY% http://httpbin.org/get -o test2.tmp
start /B curl -s -x %PROXY% http://httpbin.org/ip -o test3.tmp

REM Wait for all background processes to complete
:wait_loop
tasklist /fi "imagename eq curl.exe" 2>nul | find "curl.exe" >nul
if %errorlevel% equ 0 (
    timeout /t 1 >nul
    goto :wait_loop
)

REM Check if all files were created
if exist test1.tmp if exist test2.tmp if exist test3.tmp (
    echo ✅ PASS: All concurrent requests completed
) else (
    echo ❌ FAIL: Some concurrent requests failed
)

REM Cleanup
del test*.tmp 2>nul

echo.
echo 🎉 Windows Test Suite Complete!
echo ===============================
echo.
echo 💡 Tips for Windows users:
echo    - Use curl.exe for testing (built into Windows 10/11)
echo    - Configure browsers to use http://localhost:8080 as proxy
echo    - Check Windows Firewall if connections fail
echo.
pause
