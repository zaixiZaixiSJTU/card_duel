param(
    [int]$BackendPort = 8000,
    [int]$FrontendPort = 3000,
    [switch]$NoOpenBrowser
)

$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [Text.Encoding]::UTF8
$root = $PSScriptRoot
$frontendDirectory = Join-Path $root "frontend"

function Test-HttpReady {
    param([string]$Url)
    try {
        Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 2 | Out-Null
        return $true
    } catch {
        return $null -ne $_.Exception.Response
    }
}

function Start-ServiceJob {
    param(
        [string]$Name,
        [string]$WorkingDirectory,
        [string]$FilePath,
        [string[]]$ArgumentList
    )

    return Start-Job -Name $Name -ScriptBlock {
        param($WorkingDirectory, $FilePath, $ArgumentList)
        Set-Location $WorkingDirectory
        & $FilePath @ArgumentList
        exit $LASTEXITCODE
    } -ArgumentList $WorkingDirectory, $FilePath, $ArgumentList
}

$venvPython = Join-Path $root ".venv\Scripts\python.exe"
if (-not (Test-Path $venvPython)) {
    throw "未找到 Python 虚拟环境：$venvPython"
}

if (-not (Test-Path (Join-Path $frontendDirectory "node_modules"))) {
    throw "未找到前端依赖。请先运行: cd frontend; npm install"
}

$backendHealth = "http://127.0.0.1:$BackendPort/health"
$frontendUrl = "http://127.0.0.1:$FrontendPort"
$jobs = @()

try {
    if (-not (Test-HttpReady $backendHealth)) {
        Write-Host "[启动] 后端 http://127.0.0.1:$BackendPort" -ForegroundColor Cyan
        $jobs += Start-ServiceJob -Name "card-duel-backend" -WorkingDirectory $root -FilePath $venvPython -ArgumentList @("-m", "uvicorn", "card_duel.web.app:app", "--host", "127.0.0.1", "--port", "$BackendPort")
    } else {
        Write-Host "[复用] 后端已在运行" -ForegroundColor Yellow
    }

    $deadline = [DateTime]::UtcNow.AddSeconds(15)
    while ([DateTime]::UtcNow -lt $deadline -and -not (Test-HttpReady $backendHealth)) {
        Start-Sleep -Milliseconds 250
    }
    if (-not (Test-HttpReady $backendHealth)) {
        Receive-Job -Job $jobs -Keep -ErrorAction SilentlyContinue
        throw "后端启动超时：$backendHealth"
    }
    Write-Host "[就绪] 后端健康检查通过" -ForegroundColor Green

    if (Test-HttpReady $frontendUrl) {
        Write-Host "[复用] 前端已在运行" -ForegroundColor Yellow
    } else {
        Write-Host "[启动] 前端 http://127.0.0.1:$FrontendPort" -ForegroundColor Cyan
        $jobs += Start-ServiceJob -Name "card-duel-frontend" -WorkingDirectory $frontendDirectory -FilePath "npm.cmd" -ArgumentList @("run", "dev", "--", "--port", "$FrontendPort")

        $deadline = [DateTime]::UtcNow.AddSeconds(30)
        while ([DateTime]::UtcNow -lt $deadline -and -not (Test-HttpReady $frontendUrl)) {
            Start-Sleep -Milliseconds 500
        }
    }
    if (-not (Test-HttpReady $frontendUrl)) {
        Receive-Job -Job $jobs -Keep -ErrorAction SilentlyContinue
        throw "前端启动超时：$frontendUrl"
    }
    Write-Host "[就绪] 前端可访问" -ForegroundColor Green

    if (-not $NoOpenBrowser) {
        Start-Process explorer.exe -ArgumentList "$frontendUrl/?player=host"
        Start-Sleep -Milliseconds 300
        Start-Process explorer.exe -ArgumentList "$frontendUrl/?player=guest"
    }

    Write-Host ""
    Write-Host "Card Duel 已启动。" -ForegroundColor Green
    Write-Host "后端: $backendHealth"
    Write-Host "前端: $frontendUrl"
    if ($NoOpenBrowser) { Write-Host "已跳过打开浏览器。" }
    Write-Host "保持本窗口开启即可继续游玩；按 Ctrl+C 停止由本脚本启动的服务。"

    try {
        while ($true) {
            Start-Sleep -Seconds 60
            foreach ($job in $jobs) {
                if ($job.State -eq "Failed") {
                    Receive-Job -Job $job -Keep
                }
            }
        }
    } finally {
        $jobs | Stop-Job -ErrorAction SilentlyContinue
        $jobs | Remove-Job -Force -ErrorAction SilentlyContinue
    Write-Host ""
    Write-Host "Card Duel 服务已停止。"
    }
} catch {
    $jobs | Stop-Job -ErrorAction SilentlyContinue
    $jobs | Remove-Job -Force -ErrorAction SilentlyContinue
    throw
}
