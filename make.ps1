param(
    [Parameter(Position = 0)]
    [ValidateSet("help", "eval", "eval-holdout", "frontend", "demo", "demo-offline", "verify", "e2e")]
    [string]$Target = "help"
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $Root

function Invoke-Checked {
    param(
        [string]$Executable,
        [string[]]$CommandArgs
    )
    & $Executable @CommandArgs
    if ($LASTEXITCODE -ne 0) {
        throw "Command failed with exit code $LASTEXITCODE`: $Executable $($CommandArgs -join ' ')"
    }
}

function Invoke-Evaluation {
    Invoke-Checked "python" @("-m", "doom.holdout_eval")
    Invoke-Checked "python" @("-m", "doom.evaluation")
}

function Invoke-FrontendBuild {
    Invoke-Checked "npm" @("--prefix", "frontend", "run", "build")
}

function Invoke-Verification {
    Invoke-Evaluation
    Invoke-FrontendBuild
    Invoke-Checked "python" @("-m", "ruff", "check", "doom", "holdout_attacks", "tests")
    Invoke-Checked "python" @("-m", "mypy", "doom", "holdout_attacks")
    Invoke-Checked "npm" @("--prefix", "frontend", "test")
    Invoke-Checked "python" @("-m", "doom.streaming", "--events", "12", "--seed", "83", "--fast", "--summary-only")
    Invoke-Checked "python" @("-m", "doom.demo", "--no-server")
    Invoke-Checked "python" @("-m", "doom.offline_demo")
    Invoke-Checked "python" @("-m", "pytest")
    Invoke-Checked "python" @("-m", "doom.e2e")
    Invoke-Checked "python" @("-m", "pytest", "-k", "detector_import_graph")
    Invoke-Checked "python" @("-m", "pytest", "-k", "holdout_families_are_isolated")
    Invoke-Checked "python" @("-m", "pytest", "-k", "multiseed_metrics_meet_regression_targets")
}

switch ($Target) {
    "help" {
        Write-Output "Targets: eval eval-holdout frontend demo demo-offline verify e2e"
    }
    "eval" {
        Invoke-Evaluation
    }
    "eval-holdout" {
        Invoke-Checked "python" @("-m", "doom.holdout_eval")
    }
    "frontend" {
        Invoke-FrontendBuild
    }
    "demo" {
        Invoke-Evaluation
        Invoke-FrontendBuild
        Invoke-Checked "python" @("-m", "doom.demo")
    }
    "demo-offline" {
        Invoke-Checked "python" @("-m", "doom.offline_demo")
    }
    "e2e" {
        Invoke-FrontendBuild
        Invoke-Checked "python" @("-m", "doom.e2e")
    }
    "verify" {
        Invoke-Verification
    }
}
