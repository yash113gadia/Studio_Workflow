# Studio Environment Helper
# Loads Python, Git, and FFmpeg into current PowerShell session

$studioTools = @(
    "C:\Users\nikhi\AppData\Local\Programs\Python\Python311",
    "C:\Users\nikhi\AppData\Local\Programs\Python\Python311\Scripts",
    "C:\Users\nikhi\AppData\Local\Microsoft\WinGet\Packages\Git.MinGit_Microsoft.Winget.Source_8wekyb3d8bbwe\cmd",
    "C:\Users\nikhi\AppData\Local\Microsoft\WinGet\Packages\Gyan.FFmpeg.Essentials_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-9.0.1-essentials_build\bin"
)

foreach ($p in $studioTools) {
    if (Test-Path $p) {
        if ($env:Path -notlike "*$p*") {
            $env:Path = "$p;$env:Path"
        }
    }
}
