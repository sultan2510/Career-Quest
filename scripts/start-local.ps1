[CmdletBinding()]
param(
    [string]$PostgresBin = 'C:\Program Files\PostgreSQL\18\bin',
    [int]$DatabasePort = 5433,
    [int]$ApiPort = 8000,
    [int]$FrontendPort = 3000
)

$ErrorActionPreference = 'Stop'
$ProjectRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$LocalRoot = Join-Path $ProjectRoot '.local'
$DataDirectory = Join-Path $LocalRoot 'postgres\data'
$StatePath = Join-Path $LocalRoot 'services.json'
$PythonPath = Join-Path $ProjectRoot '.venv\Scripts\python.exe'
$FrontendDirectory = Join-Path $ProjectRoot 'frontend'
$NextPath = Join-Path $FrontendDirectory 'node_modules\next\dist\bin\next'
$PgCtlPath = Join-Path $PostgresBin 'pg_ctl.exe'
$PgReadyPath = Join-Path $PostgresBin 'pg_isready.exe'
$PostgresPath = Join-Path $PostgresBin 'postgres.exe'

function Get-PortOwner([int]$Port) {
    $Connection = Get-NetTCPConnection -State Listen -ErrorAction Stop |
        Where-Object { $_.LocalPort -eq $Port } |
        Select-Object -First 1
    if ($null -eq $Connection) { return $null }
    return Get-CimInstance Win32_Process -Filter "ProcessId = $($Connection.OwningProcess)" -ErrorAction Stop
}

function Test-ProjectProcess($ProcessInfo, [string]$Service) {
    if ($null -eq $ProcessInfo) { return $false }
    $CommandLine = [string]$ProcessInfo.CommandLine
    if ($Service -eq 'api') {
        return ($CommandLine -match 'backend\.main:app') -and (
            ([string]$ProcessInfo.ExecutablePath -ieq $PythonPath) -or
            ($CommandLine.IndexOf($ProjectRoot, [StringComparison]::OrdinalIgnoreCase) -ge 0)
        )
    }
    return ($CommandLine.IndexOf($FrontendDirectory, [StringComparison]::OrdinalIgnoreCase) -ge 0) -and
        ($CommandLine -match 'next')
}

function Wait-Http([string]$Url, [bool]$IsApi = $false) {
    $Timer = [Diagnostics.Stopwatch]::StartNew()
    while ($Timer.Elapsed.TotalSeconds -lt 45) {
        try {
            if ($IsApi) {
                $Health = Invoke-RestMethod -Uri $Url -TimeoutSec 2
                if ($Health.ok -eq $true) { return }
            } else {
                $Response = Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 2
                if ($Response.StatusCode -eq 200) { return }
            }
        } catch { }
        Start-Sleep -Milliseconds 500
    }
    throw "Service did not become ready at $Url within 45 seconds. Check its .local log files privately."
}

$ServiceState = @{}
if (Test-Path -LiteralPath $StatePath) {
    $ExistingState = Get-Content -LiteralPath $StatePath -Raw | ConvertFrom-Json
    if ($ExistingState.workspace -ine $ProjectRoot) {
        throw 'The saved service metadata belongs to another workspace.'
    }
    foreach ($ServiceName in @('api', 'frontend')) {
        if ($null -ne $ExistingState.$ServiceName) { $ServiceState[$ServiceName] = $ExistingState.$ServiceName }
    }
}

function Save-ServiceState {
    $State = [ordered]@{ workspace = $ProjectRoot }
    foreach ($ServiceName in @('api', 'frontend')) {
        if ($ServiceState.ContainsKey($ServiceName)) { $State[$ServiceName] = $ServiceState[$ServiceName] }
    }
    $State | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath $StatePath -Encoding UTF8
}

function Remember-Service([string]$Service, $ProcessInfo) {
    $TrackedProcess = Get-CimInstance Win32_Process -Filter "ProcessId = $($ProcessInfo.Id)"
    $ServiceState[$Service] = [ordered]@{
        pid = $ProcessInfo.Id
        createdUtc = $TrackedProcess.CreationDate.ToUniversalTime().ToString('o')
        executable = [string]$TrackedProcess.ExecutablePath
    }
    Save-ServiceState
}

foreach ($RequiredPath in @($PgCtlPath, $PgReadyPath, $PostgresPath, $PythonPath, $NextPath,
    (Join-Path $DataDirectory 'PG_VERSION'), (Join-Path $ProjectRoot 'backend\.env'))) {
    if (-not (Test-Path -LiteralPath $RequiredPath)) {
        throw "Required local setup is missing: $RequiredPath. Follow the local setup instructions first."
    }
}
New-Item -ItemType Directory -Path $LocalRoot -Force | Out-Null

$DatabaseOwner = Get-PortOwner $DatabasePort
$DatabaseRunning = $false
$PostmasterPath = Join-Path $DataDirectory 'postmaster.pid'
if (Test-Path -LiteralPath $PostmasterPath) {
    $PostmasterLines = Get-Content -LiteralPath $PostmasterPath
    if ($PostmasterLines.Count -lt 4 -or
        [IO.Path]::GetFullPath($PostmasterLines[1]) -ine $DataDirectory -or
        [int]$PostmasterLines[3] -ne $DatabasePort) {
        throw 'The database PID file does not match the configured project cluster and port.'
    }
    $DatabaseProcess = Get-CimInstance Win32_Process -Filter "ProcessId = $([int]$PostmasterLines[0])" -ErrorAction Stop
    if ($null -ne $DatabaseProcess) {
        $DatabaseCommand = ([string]$DatabaseProcess.CommandLine).Replace('/', '\')
        if ([string]$DatabaseProcess.ExecutablePath -ine $PostgresPath -or
            $DatabaseCommand.IndexOf($DataDirectory, [StringComparison]::OrdinalIgnoreCase) -lt 0) {
            throw 'The database PID does not belong to the dedicated project PostgreSQL process.'
        }
        if ($null -ne $DatabaseOwner -and $DatabaseOwner.ProcessId -ne $DatabaseProcess.ProcessId) {
            throw "Port $DatabasePort belongs to another process."
        }
        $DatabaseRunning = $true
    }
}
if (-not $DatabaseRunning) {
    if ($null -ne $DatabaseOwner) {
        throw "Port $DatabasePort is already in use. The dedicated project database was not started."
    }
    $PostgresLog = Join-Path $LocalRoot 'postgres\server.log'
    $ControlArguments = @('-D', ('"' + $DataDirectory + '"'), '-l', ('"' + $PostgresLog + '"'),
        '-o', ('"-h 127.0.0.1 -p ' + $DatabasePort + '"'), '-w', '-t', '45', 'start')
    # The detached server must inherit file handles, never the caller's output
    # pipes: otherwise a terminal/tool can remain blocked after pg_ctl exits.
    $ControlProcess = Start-Process -FilePath $PgCtlPath -ArgumentList $ControlArguments -WindowStyle Hidden `
        -PassThru -RedirectStandardOutput (Join-Path $LocalRoot 'postgres\control-start.stdout.log') `
        -RedirectStandardError (Join-Path $LocalRoot 'postgres\control-start.stderr.log')
    $null = $ControlProcess.Handle
    if (-not $ControlProcess.WaitForExit(60000)) {
        throw 'Database startup exceeded 60 seconds. Check the private .local/postgres control logs.'
    }
    if ($ControlProcess.ExitCode -ne 0) { throw 'The dedicated project database could not start.' }
}
$PostmasterLines = Get-Content -LiteralPath $PostmasterPath
if ([IO.Path]::GetFullPath($PostmasterLines[1]) -ine $DataDirectory -or [int]$PostmasterLines[3] -ne $DatabasePort) {
    throw 'The database process does not match the configured project cluster and port.'
}
$DatabaseOwner = Get-PortOwner $DatabasePort
if ($null -eq $DatabaseOwner -or $DatabaseOwner.ProcessId -ne [int]$PostmasterLines[0]) {
    throw 'The project database process does not own its configured TCP port.'
}
& $PgReadyPath -h 127.0.0.1 -p $DatabasePort *> $null
if ($LASTEXITCODE -ne 0) { throw 'The project database is not accepting connections.' }
Write-Host "Database ready: 127.0.0.1:$DatabasePort"

$ApiOwner = Get-PortOwner $ApiPort
if ($null -ne $ApiOwner) {
    if (-not (Test-ProjectProcess $ApiOwner 'api')) { throw "Port $ApiPort belongs to another process." }
    Write-Host 'Reusing the running CareerQuest API.'
} else {
    $ApiArguments = @('-m', 'uvicorn', 'backend.main:app', '--app-dir', ('"' + $ProjectRoot + '"'),
        '--host', '127.0.0.1', '--port', $ApiPort)
    $ApiProcess = Start-Process -FilePath $PythonPath -ArgumentList $ApiArguments -WorkingDirectory $ProjectRoot `
        -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $LocalRoot 'api.stdout.log') `
        -RedirectStandardError (Join-Path $LocalRoot 'api.stderr.log')
    Remember-Service 'api' $ApiProcess
}
Wait-Http "http://127.0.0.1:$ApiPort/health" $true
Write-Host "API ready: http://localhost:$ApiPort/docs"

$FrontendOwner = Get-PortOwner $FrontendPort
if ($null -ne $FrontendOwner) {
    if (-not (Test-ProjectProcess $FrontendOwner 'frontend')) { throw "Port $FrontendPort belongs to another process." }
    Write-Host 'Reusing the running CareerQuest frontend.'
} else {
    $NodePath = (Get-Command node.exe -ErrorAction Stop).Source
    $PreviousApiOrigin = [Environment]::GetEnvironmentVariable('API_ORIGIN', 'Process')
    try {
        $env:API_ORIGIN = "http://127.0.0.1:$ApiPort"
        $FrontendArguments = @(('"' + $NextPath + '"'), 'dev', ('"' + $FrontendDirectory + '"'),
            '--hostname', '127.0.0.1', '--port', $FrontendPort)
        $FrontendProcess = Start-Process -FilePath $NodePath -ArgumentList $FrontendArguments `
            -WorkingDirectory $FrontendDirectory -WindowStyle Hidden -PassThru `
            -RedirectStandardOutput (Join-Path $LocalRoot 'frontend.stdout.log') `
            -RedirectStandardError (Join-Path $LocalRoot 'frontend.stderr.log')
        Remember-Service 'frontend' $FrontendProcess
    } finally {
        [Environment]::SetEnvironmentVariable('API_ORIGIN', $PreviousApiOrigin, 'Process')
    }
}
Wait-Http "http://127.0.0.1:$FrontendPort"
Wait-Http "http://127.0.0.1:$FrontendPort/api/health" $true
Write-Host "CareerQuest ready: http://localhost:$FrontendPort"
Write-Host 'Use scripts/stop-local.ps1 to stop services started by these scripts.'
