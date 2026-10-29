# Wrapper around bkerler/edl that always passes the repo's QCM6125 loader.
# Auto-detection does not pick it up (filename prefix 001750e1 vs our MSM_ID 0010a0e1).
#
# Install edl (https://github.com/bkerler/edl) anywhere and point $env:EDL_DIR at it,
# e.g. `tools\edl` inside this repo (that path is .gitignored, so it's a good default).
#
# Usage:
#   $env:EDL_DIR = "tools\edl"
#   .\scripts\edl.ps1 printgpt
#   .\scripts\edl.ps1 r boot_a dumps\boot_a.img
#   $env:EDL_MEMORY = "ufs"; .\scripts\edl.ps1 printgpt

$Repo   = Split-Path -Parent $PSScriptRoot
$EdlDir = if ($env:EDL_DIR) { $env:EDL_DIR } else { Join-Path $Repo "tools\edl" }
if (-not (Test-Path (Join-Path $EdlDir "edl.py"))) {
    Write-Error "edl.py not found in '$EdlDir'. Clone/download https://github.com/bkerler/edl there, or set `$env:EDL_DIR to its location."
    exit 1
}
$Loader = Join-Path $Repo "loader\prog_firehose.bin"

$extra = @()
if ($env:EDL_MEMORY) { $extra += "--memory=$($env:EDL_MEMORY)" }

python (Join-Path $EdlDir "edl.py") @args "--loader=$Loader" @extra
