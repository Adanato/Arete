try {
    # 1. Try generic command (PATH/Alias)
    Write-Host "Attempting 'anki' command..."
    Start-Process -FilePath "anki" -ErrorAction Stop
    Write-Host "Success: Launched via 'anki' command."
    exit
} catch {
    Write-Warning "'anki' command not found."
}

# 2. Check Paths
$paths = @(
    "$env:LOCALAPPDATA\Programs\Anki\anki.exe",
    "C:\Program Files\Anki\anki.exe"
)

foreach ($path in $paths) {
    if (Test-Path $path) {
        Write-Host "Found at: $path"
        Start-Process -FilePath $path
        Write-Host "Success: Launched from path."
        exit
    }
}

# 3. Fallback
Write-Warning "Anki exe not found in standard paths. Trying 'start anki'..."
try {
    Start-Process -FilePath "cmd" -ArgumentList "/c start anki"
    Write-Host "Attempted fallback launch."
} catch {
    Write-Error "Failed to launch Anki."
}
