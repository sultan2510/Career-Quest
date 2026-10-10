# Local dev launcher (Windows). Loads .env into the environment, then starts the API.
# The repo README uses `set -a; source .env; set +a` which is bash-only.
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $here

Get-Content (Join-Path $here ".env") | ForEach-Object {
    $line = $_.Trim()
    if ($line -and -not $line.StartsWith("#")) {
        $i = $line.IndexOf("=")
        if ($i -gt 0) { Set-Item -Path ("env:" + $line.Substring(0, $i).Trim()) -Value $line.Substring($i + 1) }
    }
}

& (Join-Path $here ".venv\Scripts\python.exe") -m uvicorn main:app --reload --host 127.0.0.1 --port 8000
