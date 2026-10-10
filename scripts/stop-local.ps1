[CmdletBinding()]
param(
    [string]$PostgresBin = 'C:\Program Files\PostgreSQL\18\bin',
    [int]$DatabasePort = 5433
)

$ErrorActionPreference = 'Stop'
$ProjectRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$LocalRoot = Join-Path $ProjectRoot '.local'
$DataDirectory = Join-Path $LocalRoot 'postgres\data'
$StatePath = Join-Path $LocalRoot 'services.json'
$PgCtlPath = Join-Path $PostgresBin 'pg_ctl.exe'
$PostgresPath = Join-Path $PostgresBin 'postgres.exe'

function Stop-OwnedService([string]$Service, $SavedProcess) {
    if ($null -eq $SavedProcess) { return }
    $ProcessInfo = Get-CimInstance Win32_Process -Filter "ProcessId = $($SavedProcess.pid)" -ErrorAction Stop
    if ($null -eq $ProcessInfo) { return }
    $CreatedUtc = $ProcessInfo.CreationDate.ToUniversalTime().ToString('o')
    if ($CreatedUtc -ne $SavedProcess.createdUtc -or
        [string]$ProcessInfo.ExecutablePath -ine [string]$SavedProcess.executable) {
        Write-Warning "Skipping $Service because its saved process ID has been reused."
        return
    }
    $CommandLine = [string]$ProcessInfo.CommandLine
    if ($CommandLine.IndexOf($ProjectRoot, [StringComparison]::OrdinalIgnoreCase) -lt 0) {
        Write-Warning "Skipping $Service because its command line does not identify this workspace."
        return
    }
    if (($Service -eq 'api' -and $CommandLine -notmatch 'backend\.main:app') -or
        ($Service -eq 'frontend' -and $CommandLine -notmatch 'next')) {
        Write-Warning "Skipping $Service because its command line does not match the expected service."
        return
    }

    # Snapshot descendants before stopping the parent, then verify each identity
    # again before stopping it. A reused PID must never target another program.
    $ProcessSnapshot = @(Get-CimInstance Win32_Process)
    $SnapshotRoot = $ProcessSnapshot | Where-Object { $_.ProcessId -eq $ProcessInfo.ProcessId } | Select-Object -First 1
    if ($null -eq $SnapshotRoot -or $SnapshotRoot.CreationDate -ne $ProcessInfo.CreationDate) {
        Write-Warning "Skipping $Service because its process changed while checking descendants."
        return
    }
    $OwnedProcesses = [Collections.Generic.List[object]]::new()
    $PendingParents = [Collections.Generic.Queue[object]]::new()
    $SeenProcessIds = [Collections.Generic.HashSet[uint32]]::new()
    $null = $SeenProcessIds.Add([uint32]$ProcessInfo.ProcessId)
    $PendingParents.Enqueue($ProcessInfo)
    $OwnedProcesses.Add($ProcessInfo)
    while ($PendingParents.Count -gt 0) {
        $ParentProcess = $PendingParents.Dequeue()
        foreach ($Child in $ProcessSnapshot) {
            if ($Child.ParentProcessId -eq $ParentProcess.ProcessId -and
                $Child.CreationDate -ge $ParentProcess.CreationDate -and
                $SeenProcessIds.Add([uint32]$Child.ProcessId)) {
                $OwnedProcesses.Add($Child)
                $PendingParents.Enqueue($Child)
            }
        }
    }
    for ($Index = $OwnedProcesses.Count - 1; $Index -ge 0; $Index--) {
        $Owned = $OwnedProcesses[$Index]
        $Current = Get-CimInstance Win32_Process -Filter "ProcessId = $($Owned.ProcessId)" -ErrorAction SilentlyContinue
        if ($null -ne $Current -and $Current.CreationDate -eq $Owned.CreationDate -and
            $Current.ExecutablePath -ieq $Owned.ExecutablePath) {
            Stop-Process -Id $Current.ProcessId -ErrorAction SilentlyContinue
        }
    }
    Write-Host "Stopped project $Service."
}

if (Test-Path -LiteralPath $StatePath) {
    $State = Get-Content -LiteralPath $StatePath -Raw | ConvertFrom-Json
    if ($State.workspace -ine $ProjectRoot) { throw 'The saved service metadata belongs to another workspace.' }
    Stop-OwnedService 'frontend' $State.frontend
    Stop-OwnedService 'api' $State.api
}

if ((Test-Path -LiteralPath $PgCtlPath) -and (Test-Path -LiteralPath (Join-Path $DataDirectory 'postmaster.pid'))) {
    $PostmasterLines = Get-Content -LiteralPath (Join-Path $DataDirectory 'postmaster.pid')
    if ($PostmasterLines.Count -lt 4 -or [IO.Path]::GetFullPath($PostmasterLines[1]) -ine $DataDirectory -or
        [int]$PostmasterLines[3] -ne $DatabasePort) {
        throw "Refusing to stop a database that does not match the dedicated project cluster on port $DatabasePort."
    }
    $DatabaseProcess = Get-CimInstance Win32_Process -Filter "ProcessId = $([int]$PostmasterLines[0])" -ErrorAction Stop
    if ($null -ne $DatabaseProcess) {
        $DatabaseCommand = ([string]$DatabaseProcess.CommandLine).Replace('/', '\')
        if ([string]$DatabaseProcess.ExecutablePath -ine $PostgresPath -or
            $DatabaseCommand.IndexOf($DataDirectory, [StringComparison]::OrdinalIgnoreCase) -lt 0) {
            throw 'Refusing to stop a PostgreSQL process that does not belong to the dedicated project cluster.'
        }
        $DatabaseConnection = Get-NetTCPConnection -State Listen -ErrorAction Stop |
            Where-Object { $_.LocalPort -eq $DatabasePort } | Select-Object -First 1
        if ($null -ne $DatabaseConnection -and $DatabaseConnection.OwningProcess -ne $DatabaseProcess.ProcessId) {
            throw "Refusing to stop a database because port $DatabasePort belongs to another process."
        }
        $ControlArguments = @('-D', ('"' + $DataDirectory + '"'), '-m', 'fast', '-w', '-t', '45', 'stop')
        $ControlProcess = Start-Process -FilePath $PgCtlPath -ArgumentList $ControlArguments -WindowStyle Hidden `
            -PassThru -RedirectStandardOutput (Join-Path $LocalRoot 'postgres\control-stop.stdout.log') `
            -RedirectStandardError (Join-Path $LocalRoot 'postgres\control-stop.stderr.log')
        $null = $ControlProcess.Handle
        if (-not $ControlProcess.WaitForExit(60000)) { throw 'Database shutdown exceeded 60 seconds.' }
        if ($ControlProcess.ExitCode -ne 0) { throw 'The project database did not stop successfully.' }
        Write-Host "Stopped the dedicated project database on port $DatabasePort."
    }
}
Write-Host 'Local stop completed. Services reused from other terminals remain running.'
