$ErrorActionPreference = "Stop"

# APP_PORT is injected by the sandbox (3000-3099 range)
# Vite dev server listens on APP_PORT so the sandbox proxy can reach it
# FastAPI backend runs on an internal port, proxied by Vite
if (-not $env:APP_PORT) { $env:APP_PORT = "5173" }
$VitePort = [int]$env:APP_PORT
$BackendPort = $VitePort + 100
$env:VITE_BACKEND_PORT = "$BackendPort"

# Startup timing
$T0 = [DateTimeOffset]::UtcNow.ToUnixTimeMilliseconds()
function elapsed { [DateTimeOffset]::UtcNow.ToUnixTimeMilliseconds() - $script:T0 }

# Install Python deps (with lockfile hash guard)
$uvHash = (Get-FileHash -Algorithm MD5 uv.lock -ErrorAction SilentlyContinue).Hash
$uvHashFile = ".venv/.uv-hash-$uvHash"
if ($uvHash -and -not (Test-Path $uvHashFile)) {
    Write-Host "[+$(elapsed)ms] uv sync starting..."
    uv sync --compile-bytecode --frozen
    if ($LASTEXITCODE -ne 0) { uv sync --compile-bytecode }
    Remove-Item .venv/.uv-hash-* -ErrorAction SilentlyContinue
    New-Item -ItemType File -Path $uvHashFile -Force | Out-Null
    Write-Host "[+$(elapsed)ms] uv sync done"
} else {
    Write-Host "[+$(elapsed)ms] uv sync skipped (lockfile unchanged)"
}

# Install JS deps (with lockfile hash guard)
$hasBun = $null -ne (Get-Command bun -ErrorAction SilentlyContinue)
$jsLock = if ($hasBun) { "bun.lock" } else { "package-lock.json" }
$jsHash = (Get-FileHash -Algorithm MD5 $jsLock -ErrorAction SilentlyContinue).Hash
$jsHashFile = "node_modules/.js-hash-$jsHash"
if ($jsHash -and -not (Test-Path $jsHashFile)) {
    Write-Host "[+$(elapsed)ms] JavaScript install starting via $(if ($hasBun) { 'bun' } else { 'npm' })..."
    if ($hasBun) { bun install --frozen-lockfile } else { npm install }
    if ($LASTEXITCODE -ne 0) { throw "JavaScript dependency install failed" }
    Remove-Item node_modules/.js-hash-* -ErrorAction SilentlyContinue
    New-Item -ItemType File -Path $jsHashFile -Force | Out-Null
    Write-Host "[+$(elapsed)ms] JavaScript install done"
} else {
    Write-Host "[+$(elapsed)ms] JavaScript install skipped (lockfile unchanged)"
}

# Start FastAPI backend as a background job
Write-Host "[+$(elapsed)ms] Starting FastAPI on port $BackendPort"
$backendJob = Start-Job -ScriptBlock {
    param($port)
    Set-Location $using:PWD
    uv run uvicorn app:asgi --reload --host 0.0.0.0 --port $port `
        --reload-exclude ".venv" --reload-exclude ".git" --reload-exclude "__pycache__" --reload-exclude "*.pyc" --reload-exclude "node_modules"
} -ArgumentList $BackendPort

# Start Vite dev server (foreground)
Write-Host "[+$(elapsed)ms] Starting Vite on port $VitePort"
try {
    if ($hasBun) { bunx vite --host 0.0.0.0 --port $VitePort --strictPort }
    else { npx vite --host 0.0.0.0 --port $VitePort --strictPort }
} finally {
    # Cleanup backend when Vite exits
    Stop-Job $backendJob -ErrorAction SilentlyContinue
    Remove-Job $backendJob -Force -ErrorAction SilentlyContinue
}
