# Studio Environment Helper
# Loads Python, Git, and FFmpeg into current PowerShell session

$root = Split-Path -Parent $PSScriptRoot
$studioTools = @(
    "$env:LOCALAPPDATA\Programs\Python\Python311",
    "$env:LOCALAPPDATA\Programs\Python\Python311\Scripts"
)
$studioTools += Get-ChildItem -Path "$root\tools\ffmpeg\*\bin" -Directory -ErrorAction SilentlyContinue | ForEach-Object { $_.FullName }
$studioTools += Get-ChildItem -Path "$env:LOCALAPPDATA\Microsoft\WinGet\Packages\Git.MinGit*\cmd" -Directory -ErrorAction SilentlyContinue | ForEach-Object { $_.FullName }
$studioTools += Get-ChildItem -Path "$env:LOCALAPPDATA\Microsoft\WinGet\Packages\Gyan.FFmpeg*\*\bin" -Directory -ErrorAction SilentlyContinue | ForEach-Object { $_.FullName }

foreach ($p in $studioTools) {
    if (Test-Path $p) {
        if ($env:Path -notlike "*$p*") {
            $env:Path = "$p;$env:Path"
        }
    }
}
