# ============================================================
# 初始化本地 Git 仓库并准备首次提交
# ============================================================
# 用法（在仓库根目录执行）：
#     pwsh -File scripts/init-git.ps1
#
# 本脚本只做本地操作，不会推送。
# 推送前请确认：
#   1. git 已安装
#   2. git config user.name / user.email 已配置
#   3. hosts 文件没有把 github.com 指向 127.0.0.1
# ============================================================

[CmdletBinding()]
param(
    [string]$RemoteUrl = "https://github.com/user3280204209/textGit.git",
    [string]$Branch = "main",
    [switch]$Force
)

$ErrorActionPreference = "Stop"

function Write-Step($m) { Write-Host "`n==== $m ====" -ForegroundColor Cyan }
function Write-Ok($m) { Write-Host "  [OK]   $m" -ForegroundColor Green }
function Write-Warn2($m) { Write-Host "  [WARN] $m" -ForegroundColor Yellow }
function Write-Err2($m) { Write-Host "  [FAIL] $m" -ForegroundColor Red }

$repoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $repoRoot

# ------------------------------------------------------------
Write-Step "1/6 检查 git"
if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
    Write-Err2 "git 未安装。请先安装：winget install --id Git.Git -e"
    exit 1
}
Write-Ok (git --version)

# ------------------------------------------------------------
Write-Step "2/6 检查 git 身份配置"
$name = git config --global user.name
$email = git config --global user.email
if (-not $name) {
    Write-Err2 "未配置 user.name"
    Write-Host "  请执行：git config --global user.name `"你的姓名`"" -ForegroundColor Yellow
    exit 1
}
if (-not $email) {
    Write-Err2 "未配置 user.email"
    Write-Host "  请执行：git config --global user.email `"你的邮箱`"" -ForegroundColor Yellow
    exit 1
}
Write-Ok "身份: $name <$email>"

# ------------------------------------------------------------
Write-Step "3/6 检查 hosts 是否劫持 github"
$hostsFile = "$env:SystemRoot\System32\drivers\etc\hosts"
$hijacked = @()
if (Test-Path $hostsFile) {
    $hijacked = Get-Content $hostsFile -ErrorAction SilentlyContinue |
        Where-Object { $_ -match '^\s*127\.0\.0\.1\s+.*github' }
}
if ($hijacked.Count -gt 0) {
    Write-Err2 "hosts 把 github 域名指向了 127.0.0.1，clone/push 会失败"
    Write-Host "  受影响条目（共 $($hijacked.Count) 条）：" -ForegroundColor Yellow
    $hijacked | Select-Object -First 5 | ForEach-Object { Write-Host "    $_" -ForegroundColor DarkGray }
    Write-Host "  处理：用管理员权限编辑 hosts，注释或删除上述行，然后执行 ipconfig /flushdns" -ForegroundColor Yellow
    Write-Host "  文件位置: $hostsFile" -ForegroundColor Yellow
    if (-not $Force) {
        Write-Host "`n  如确认已处理，可加 -Force 跳过此检查。" -ForegroundColor Yellow
        exit 1
    }
} else {
    Write-Ok "hosts 未劫持 github"
}

# ------------------------------------------------------------
Write-Step "4/6 初始化仓库"
if (Test-Path (Join-Path $repoRoot ".git")) {
    Write-Warn2 "已存在 .git，跳过 init"
} else {
    git init -b $Branch
    Write-Ok "已初始化，分支 $Branch"
}

# ------------------------------------------------------------
Write-Step "5/6 配置远端"
$existing = git remote get-url origin 2>$null
if ($existing) {
    Write-Warn2 "origin 已存在：$existing"
    git remote set-url origin $RemoteUrl
    Write-Ok "已更新 origin -> $RemoteUrl"
} else {
    git remote add origin $RemoteUrl
    Write-Ok "已添加 origin -> $RemoteUrl"
}

# ------------------------------------------------------------
Write-Step "6/6 暂存并检查"
git add -A

Write-Host "`n  ---- 将要提交的文件（前 60 个）----" -ForegroundColor DarkGray
git diff --cached --name-only | Select-Object -First 60 | ForEach-Object {
    Write-Host "    $_" -ForegroundColor DarkGray
}
$count = (git diff --cached --name-only | Measure-Object).Count
Write-Host "  ---- 共 $count 个文件 ----" -ForegroundColor DarkGray

# 安全检查：绝不能提交 .env
$bad = git diff --cached --name-only | Where-Object { $_ -match '(^|/)\.env$' }
if ($bad) {
    Write-Err2 "检测到 .env 被暂存！这会导致 API Key 泄露！"
    $bad | ForEach-Object { Write-Host "    $_" -ForegroundColor Red }
    Write-Host "`n  已中止。请执行：git reset HEAD <上述文件>" -ForegroundColor Yellow
    exit 1
}
Write-Ok "安全检查通过：未暂存 .env"

# 安全检查：不应提交缓存与构建产物
$junk = git diff --cached --name-only |
    Where-Object { $_ -match '__pycache__|node_modules|\.pytest_cache|\.ruff_cache|tsbuildinfo|/dist/' }
if ($junk) {
    Write-Err2 "检测到缓存/构建产物被暂存，说明 .gitignore 未生效："
    $junk | Select-Object -First 10 | ForEach-Object { Write-Host "    $_" -ForegroundColor Red }
    exit 1
}
Write-Ok "安全检查通过：无缓存与构建产物"

# ------------------------------------------------------------
Write-Host ""
Write-Host "==================== 准备就绪 ====================" -ForegroundColor Green
Write-Host ""
Write-Host "下一步（确认文件列表无误后执行）：" -ForegroundColor Yellow
Write-Host ""
Write-Host "  git commit -m `"chore: 初始化项目脚手架`""
Write-Host ""
Write-Host "推送到 GitHub 前请注意：" -ForegroundColor Yellow
Write-Host "  1. 远端仓库可能含旧测试文件，直接 push 可能被拒（non-fast-forward）"
Write-Host "     若确认要用本地内容覆盖远端："
Write-Host "       git push -u origin $Branch --force-with-lease"
Write-Host "     或者先拉取再合并："
Write-Host "       git pull origin $Branch --allow-unrelated-histories"
Write-Host "  2. 首次推送会要求认证，用户名填 GitHub 用户名，密码填 PAT（不是账号密码）"
Write-Host ""
