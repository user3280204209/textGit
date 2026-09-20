# ============================================================
# 同时启动后端 + 前端（开发模式）
# ============================================================
# 用法：在仓库根目录执行
#     pwsh -File scripts/dev.ps1
#
# 会打开两个新窗口分别跑后端和前端，Ctrl+C 各自停止。
# 后端: http://127.0.0.1:8000/docs
# 前端: http://127.0.0.1:5173
# ============================================================

[CmdletBinding()]
param(
    [string]$EnvName = "learnagent",
    [int]$BackendPort = 8000,
    [switch]$BackendOnly
)

$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
$backendDir = Join-Path $repoRoot "backend"
$frontendDir = Join-Path $repoRoot "frontend"

Write-Host "启动后端 (端口 $BackendPort)..." -ForegroundColor Cyan

# 用独立窗口起后端，这样日志和前端分开，排错更容易
Start-Process pwsh -ArgumentList @(
    "-NoExit",
    "-Command",
    "conda activate $EnvName; Set-Location '$backendDir'; Write-Host '后端启动中 (http://127.0.0.1:$BackendPort/docs)' -ForegroundColor Green; uvicorn app.main:app --reload --port $BackendPort"
)

if (-not $BackendOnly) {
    Start-Sleep -Seconds 3
    Write-Host "启动前端 (端口 5173)..." -ForegroundColor Cyan
    Start-Process pwsh -ArgumentList @(
        "-NoExit",
        "-Command",
        "Set-Location '$frontendDir'; Write-Host '前端启动中 (http://127.0.0.1:5173)' -ForegroundColor Green; pnpm dev"
    )
}

Write-Host ""
Write-Host "已在独立窗口启动。" -ForegroundColor Green
Write-Host "  后端文档: http://127.0.0.1:$BackendPort/docs"
if (-not $BackendOnly) {
    Write-Host "  前端页面: http://127.0.0.1:5173"
}
Write-Host ""
Write-Host "关闭服务：直接关掉对应窗口，或在该窗口按 Ctrl+C" -ForegroundColor Yellow
