<#
.SYNOPSIS
EvidenceRAG 本地环境初始化引导脚本（仅准备环境骨架，需在仓库根目录执行）。
注意：本脚本尚未在新机器上实际运行验证。
#>
[CmdletBinding()]
param(
    [string]$PythonExe = "python",
    [switch]$SkipPythonCheck,
    [switch]$SkipVenv,
    [switch]$SkipInstall,
    [switch]$SkipEnvNotice
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$VenvDir = Join-Path $RepoRoot ".venv"
$VenvPython = Join-Path $VenvDir "Scripts\python.exe"
$RequirementsFile = Join-Path $RepoRoot "requirements-all.txt"
$CpuIndexUrl = "https://download.pytorch.org/whl/cpu"

if (-not $SkipPythonCheck) {
    Write-Host "[1/4] 检查 Python 版本（要求 >= 3.11）..."
    $versionOutput = & $PythonExe -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')"
    if ($LASTEXITCODE -ne 0) {
        throw "无法调用 Python 解释器：$PythonExe"
    }
    $parts = $versionOutput.Trim().Split(".")
    $major = [int]$parts[0]
    $minor = [int]$parts[1]
    if (($major -lt 3) -or ($major -eq 3 -and $minor -lt 11)) {
        throw "Python 版本过低（当前 $versionOutput），需要 Python >= 3.11。"
    }
    Write-Host "已检测到 Python $versionOutput"
} else {
    Write-Host "[1/4] 已跳过 Python 版本检查。"
}

if (-not $SkipVenv) {
    Write-Host "[2/4] 检查并创建虚拟环境：$VenvDir"
    if (-not (Test-Path $VenvPython)) {
        & $PythonExe -m venv $VenvDir
        if ($LASTEXITCODE -ne 0) {
            throw "创建虚拟环境失败：$VenvDir"
        }
    } else {
        Write-Host "虚拟环境已存在，复用：$VenvDir"
    }
} else {
    Write-Host "[2/4] 已跳过创建虚拟环境。"
}

if (-not $SkipInstall) {
    Write-Host "[3/4] 安装 CPU 版 PyTorch 与全部依赖（$RequirementsFile）..."
    if (-not (Test-Path $VenvPython)) {
        throw "找不到虚拟环境 Python：$VenvPython，请先取消 -SkipVenv 或手动创建 .venv。"
    }
    & $VenvPython -m pip install --extra-index-url $CpuIndexUrl -r $RequirementsFile
    if ($LASTEXITCODE -ne 0) {
        throw "依赖安装失败，请检查网络或 PyTorch CPU 索引配置。"
    }
} else {
    Write-Host "[3/4] 已跳过依赖安装。"
}

if (-not $SkipEnvNotice) {
    Write-Host "[4/4] 下一步配置与索引准备："
    Write-Host "  1) 复制 .env.example 为 .env，并填写本机 LLM_API_KEY、LLM_BASE_URL、LLM_MODEL_ID"
    Write-Host "  2) 构建本地索引：.\.venv\Scripts\python.exe -X utf8 .\build_index.py --corpus full"
    Write-Host "  3) 运行离线单元测试：.\.venv\Scripts\python.exe -m unittest discover -s tests -v"
} else {
    Write-Host "[4/4] 已跳过配置提示。"
}
