@echo off
REM ============================================================
REM 双击即可运行的初始化入口（给不熟悉 PowerShell 的组员）
REM 实际逻辑在 scripts\setup.ps1
REM ============================================================

setlocal
cd /d "%~dp0.."

echo.
echo 正在初始化项目环境...
echo.

where pwsh >nul 2>nul
if %ERRORLEVEL% EQU 0 (
    pwsh -NoProfile -ExecutionPolicy Bypass -File "scripts\setup.ps1" %*
) else (
    echo [提示] 未找到 pwsh，尝试使用 Windows PowerShell...
    powershell -NoProfile -ExecutionPolicy Bypass -File "scripts\setup.ps1" %*
)

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [失败] 初始化未完成，请把上方错误信息发给技术负责人。
)

echo.
pause
endlocal
