# ============================================================
# 一键初始化脚手架环境（Windows / PowerShell）
# ============================================================
# 用法：在仓库根目录执行
#     pwsh -File scripts/setup.ps1
# 或只做后端：
#     pwsh -File scripts/setup.ps1 -BackendOnly
#
# 脚本做四件事：
#   1. 检查必需工具是否安装（缺失就明确报出来，不继续往下跑）
#   2. 创建 conda 环境并安装后端依赖
#   3. 生成 .env（从 .env.example 复制，不覆盖已有文件）
#   4. 安装前端依赖（pnpm）
# ============================================================

[CmdletBinding()]
param(
    [switch]$BackendOnly,
    [switch]$SkipFrontend,
    [string]$EnvName = "learnagent",
    [string]$PythonVersion = "3.13"
)

$ErrorActionPreference = "Stop"

function Write-Step($message) {
    Write-Host ""
    Write-Host "==== $message ====" -ForegroundColor Cyan
}

function Write-Ok($message) { Write-Host "  [OK]   $message" -ForegroundColor Green }
function Write-Warn2($message) { Write-Host "  [WARN] $message" -ForegroundColor Yellow }
function Write-Err($message) { Write-Host "  [FAIL] $message" -ForegroundColor Red }

function Test-Command($name) {
    return [bool](Get-Command $name -ErrorAction SilentlyContinue)
}

$repoRoot = Split-Path -Parent $PSScriptRoot
$backendDir = Join-Path $repoRoot "backend"
$frontendDir = Join-Path $repoRoot "frontend"

Write-Host ""
Write-Host "个性化资源生成与学习多智能体系统 - 环境初始化" -ForegroundColor Magenta
Write-Host "仓库根目录: $repoRoot"

# ------------------------------------------------------------
# 1. 前置检查
# ------------------------------------------------------------
Write-Step "1/5 检查必需工具"

$missing = @()

if (Test-Command "conda") {
    Write-Ok "conda 已安装"
} else {
    Write-Err "conda 未安装 -> 需安装 Miniconda: https://docs.conda.io/en/latest/miniconda.html"
    $missing += "conda"
}

if (Test-Command "git") {
    Write-Ok "git 已安装"
} else {
    Write-Err "git 未安装 -> 多人协作必需，下载: https://git-scm.com/download/win"
    $missing += "git"
}

if (-not $SkipFrontend -and -not $BackendOnly) {
    if (Test-Command "node") {
        Write-Ok "node 已安装"
    } else {
        Write-Err "node 未安装 -> 前端必需，下载 LTS 版: https://nodejs.org/"
        $missing += "node"
    }

    if (Test-Command "pnpm") {
        Write-Ok "pnpm 已安装"
    } else {
        Write-Warn2 "pnpm 未安装，稍后会用 npm 自动安装"
    }
}

if ($missing.Count -gt 0) {
    Write-Host ""
    Write-Err "缺少必需工具：$($missing -join ', ')"
    Write-Host "请先安装上述工具，然后重新运行本脚本。" -ForegroundColor Yellow
    Write-Host "详细安装步骤见 docs/组员环境安装手册.md" -ForegroundColor Yellow
    exit 1
}

# ------------------------------------------------------------
# 2. 创建 conda 环境
# ------------------------------------------------------------
Write-Step "2/5 准备 Python 环境 ($EnvName, Python $PythonVersion)"

$envExists = $false
try {
    $envList = & conda env list 2>&1 | Out-String
    if ($envList -match "(?m)^\s*$([regex]::Escape($EnvName))\s") {
        $envExists = $true
    }
} catch {
    Write-Warn2 "无法读取 conda 环境列表，将直接尝试创建"
}

if ($envExists) {
    Write-Ok "环境 $EnvName 已存在，跳过创建"
} else {
    Write-Host "  正在创建环境（首次约需 1-3 分钟）..."
    & conda create -n $EnvName "python=$PythonVersion" -y
    if ($LASTEXITCODE -ne 0) {
        Write-Err "conda 环境创建失败"
        exit 1
    }
    Write-Ok "环境 $EnvName 创建完成"
}

# ------------------------------------------------------------
# 3. 安装后端依赖
# ------------------------------------------------------------
Write-Step "3/5 安装后端依赖"

$reqFile = Join-Path $backendDir "requirements.txt"
if (-not (Test-Path $reqFile)) {
    Write-Err "找不到 $reqFile"
    exit 1
}

Write-Host "  正在安装（首次约需 2-5 分钟，取决于网速）..."

# ⚠️ 中文 Windows 上必加这一行。
# requirements.txt 是 UTF-8 编码且含中文注释，而 pip 用系统区域编码
# （简体中文 Windows = GBK）去读它，会直接抛：
#     UnicodeDecodeError: 'gbk' codec can't decode byte 0xab
# 开启 Python 的 UTF-8 模式后，locale.getpreferredencoding() 返回 utf-8，
# 该问题根治。少了这一行，每个中文 Windows 组员都会卡在这一步。
$env:PYTHONUTF8 = "1"

& conda run -n $EnvName --no-capture-output python -m pip install --upgrade pip
& conda run -n $EnvName --no-capture-output python -m pip install -r $reqFile

if ($LASTEXITCODE -ne 0) {
    Write-Err "后端依赖安装失败"
    Write-Host "  常见原因与处理：" -ForegroundColor Yellow
    Write-Host "    - 网络超时：换国内镜像重试" -ForegroundColor Yellow
    Write-Host "      pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple" -ForegroundColor Yellow
    Write-Host "    - 编译报错：确认用的是 Python 3.13，不要用 3.14" -ForegroundColor Yellow
    Write-Host "    - UnicodeDecodeError 'gbk'：先在当前窗口执行 `$env:PYTHONUTF8 = '1'` 再重试" -ForegroundColor Yellow
    exit 1
}
Write-Ok "后端依赖安装完成"

# ------------------------------------------------------------
# 4. 生成 .env
# ------------------------------------------------------------
Write-Step "4/5 生成配置文件"

$envExample = Join-Path $backendDir ".env.example"
$envFile = Join-Path $backendDir ".env"

if (Test-Path $envFile) {
    Write-Warn2 ".env 已存在，不覆盖（保护你已填的 API Key）"
} else {
    Copy-Item $envExample $envFile
    Write-Ok "已从 .env.example 生成 backend/.env"
    Write-Warn2 "还需要手动填入 LLM_API_KEY，否则生成类接口会返回 503"
}

# ------------------------------------------------------------
# 5. 前端依赖
# ------------------------------------------------------------
if ($BackendOnly -or $SkipFrontend) {
    Write-Step "5/5 跳过前端依赖（按参数要求）"
} else {
    Write-Step "5/5 安装前端依赖"

    if (-not (Test-Command "pnpm")) {
        Write-Host "  正在通过 corepack 启用 pnpm..."
        & corepack enable
        & corepack prepare pnpm@9.15.0 --activate
    }

    Push-Location $frontendDir
    try {
        & pnpm install
        if ($LASTEXITCODE -ne 0) {
            Write-Err "前端依赖安装失败"
            exit 1
        }
        Write-Ok "前端依赖安装完成"
    } finally {
        Pop-Location
    }
}

# ------------------------------------------------------------
# 完成
# ------------------------------------------------------------
Write-Host ""
Write-Host "==================== 初始化完成 ====================" -ForegroundColor Green
Write-Host ""
Write-Host "接下来手动做两件事：" -ForegroundColor Yellow
Write-Host "  1. 编辑 backend/.env，填入 LLM_API_KEY"
Write-Host "  2. 启动服务：pwsh -File scripts/dev.ps1"
Write-Host ""
Write-Host "或者分别启动：" -ForegroundColor Yellow
Write-Host "  后端: conda activate $EnvName; cd backend; uvicorn app.main:app --reload --port 8000"
Write-Host "  前端: cd frontend; pnpm dev"
Write-Host ""
Write-Host "验证环境: conda activate $EnvName; cd backend; pytest"
Write-Host ""
