param(
    [Parameter(Mandatory=$true, Position=0)]
    [ValidateSet("1","2","3")]
    [string]$Slice,

    [Parameter(Position=1)]
    [string]$ScenarioIds
)

$env:Path = "C:\Program Files\Docker\Docker\resources\bin;" + $env:Path

switch ($Slice) {
    "1" { $defaultIds = "S01,S02,S03,S04,S05,S06,S07,S08" }
    "2" { $defaultIds = "S09,S10,S11,S12,S13,S14,S15" }
    "3" { $defaultIds = "S16,S17,S18,S19,S20,S21,S22" }
}

$ids = if ($ScenarioIds) { $ScenarioIds } else { $defaultIds }
$suffix = if ($ScenarioIds) { "_rerun" + (Get-Date -Format "HHmm") } else { "" }
$evalOut = if ($env:EVAL_OUT) { $env:EVAL_OUT } else { "eval/results" }

function Set-Agents {
    param([string]$enabled)
    Write-Host "Setting MODIFIER_SEARCH_ENABLED=$enabled and restarting agents..."
    $env:MODIFIER_SEARCH_ENABLED = $enabled
    docker compose up -d --no-deps --wait researcher assessor api
    if ($LASTEXITCODE -ne 0) {
        Write-Error "Could not restart agents - is the stack up?"
        exit 1
    }
}

function Run-Arm {
    param([string]$label, [string]$variant)
    Write-Host "== $label ($variant) on $ids"
    docker compose --profile tools run --rm --no-deps eval python -m bpc.evaluation.run_eval `
        --variant "$variant" `
        --label "$($label)_part$($Slice)$suffix" `
        --only "$ids" `
        --reuse-model-cache `
        --timeout 900 `
        --out "$evalOut"
}

Set-Agents "true"
Run-Arm "real_v1" "v1"
Run-Arm "real_v2" "v2"
Set-Agents "false"
Run-Arm "real_nomod" "v2"
Set-Agents "true"

Write-Host ""
Write-Host "Done. Results saved in eval/results/real_*_part$($Slice)$suffix.*"
