<#
发布到 GitHub（需先完成 gh 登录）

用法：
  .\scripts\publish.ps1                      # 公开仓库，名字 devin-desktop-patchkit
  .\scripts\publish.ps1 -Name my-kit -Private
前置：
  winget install --id GitHub.cli -e          # 安装 gh
  gh auth login                              # 交互登录（一次性）
#>
param(
  [string]$Name = "devin-desktop-patchkit",
  [switch]$Private
)

$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Push-Location $repoRoot
try {
  if (-not (Get-Command gh -ErrorAction SilentlyContinue)) {
    Write-Host "未找到 gh。先执行： winget install --id GitHub.cli -e" -ForegroundColor Yellow
    Write-Host "安装后重开终端，再执行： gh auth login"
    exit 1
  }
  gh auth status 2>&1 | Out-Null
  if ($LASTEXITCODE -ne 0) {
    Write-Host "gh 未登录，请先执行： gh auth login" -ForegroundColor Yellow
    exit 1
  }
  if (-not (Test-Path ".git")) { git init -q }
  git add -A
  if ((git status --porcelain).Length -gt 0) {
    git commit -q -m "chore: update $(Get-Date -Format 'yyyy-MM-dd HH:mm')"
  }
  $vis = if ($Private) { "--private" } else { "--public" }
  gh repo create $Name $vis --source . --remote origin --push
  gh repo view --web
}
finally { Pop-Location }
