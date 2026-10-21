# Wrapper around bkerler/edl that always passes the repo's QCM6125 loader.
# Auto-detection does not pick it up (filename prefix 001750e1 vs our MSM_ID 0010a0e1).
#
# Usage:
#   .\scripts\edl.ps1 printgpt
#   .\scripts\edl.ps1 r boot_a dumps\boot_a.img
#   $env:EDL_MEMORY = "ufs"; .\scripts\edl.ps1 printgpt

$EdlDir = if ($env:EDL_DIR) { $env:EDL_DIR } else { "C:\Users\Asus\Downloads\edl-3.52.1" }
$Repo   = Split-Path -Parent $PSScriptRoot
$Loader = Join-Path $Repo "loader\prog_firehose.bin"

$extra = @()
if ($env:EDL_MEMORY) { $extra += "--memory=$($env:EDL_MEMORY)" }

python (Join-Path $EdlDir "edl.py") @args "--loader=$Loader" @extra
