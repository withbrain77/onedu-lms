param(
    [ValidateSet(
        "status",
        "health",
        "check",
        "logs",
        "logs-web",
        "logs-nginx",
        "logs-worker",
        "logs-redis",
        "hls-status",
        "expiry-notices",
        "restart-nginx",
        "restart-web",
        "restart-queue",
        "sync",
        "deploy",
        "readiness",
        "backup-db",
        "backup-check"
    )]
    [string]$Action = "health",

    [string]$Target = $(if ($env:ONEDU_SSH_TARGET) { $env:ONEDU_SSH_TARGET } else { "onedu-nas" }),
    [string]$AppDir = $(if ($env:ONEDU_APP_DIR) { $env:ONEDU_APP_DIR } else { "/volume1/wbinstitute/docker/onedu/app" }),
    [switch]$AllowDirty
)

$ErrorActionPreference = "Stop"

function Require-Command {
    param([string]$Name)

    if (-not (Get-Command $Name -ErrorAction SilentlyContinue)) {
        throw "Required command not found: $Name"
    }
}

function Invoke-Native {
    param(
        [string]$FilePath,
        [string[]]$Arguments
    )

    & $FilePath @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "$FilePath failed with exit code $LASTEXITCODE"
    }
}

function Invoke-Remote {
    param([string]$Command)

    Invoke-Native "ssh" @("-o", "BatchMode=yes", $Target, $Command)
}

function Get-GitOutput {
    param([string[]]$Arguments)

    $output = & git @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "git $($Arguments -join ' ') failed with exit code $LASTEXITCODE"
    }
    return $output
}

function Assert-CleanTree {
    if ($AllowDirty) {
        return
    }

    $status = Get-GitOutput @("status", "--porcelain")
    if ($status) {
        Write-Host "Uncommitted changes were found. Commit first, or rerun with -AllowDirty." -ForegroundColor Yellow
        $status | ForEach-Object { Write-Host $_ }
        throw "Refusing to sync an uncommitted working tree."
    }
}

function Sync-Source {
    Require-Command "git"
    Require-Command "ssh"
    Assert-CleanTree

    $commit = (Get-GitOutput @("rev-parse", "--short", "HEAD")).Trim()
    Write-Host "Syncing committed source $commit to ${Target}:$AppDir" -ForegroundColor Cyan

    $remoteCommand = "mkdir -p '$AppDir' && tar -xpf - -C '$AppDir'"
    $archiveCommand = "git archive --format=tar HEAD | ssh -o BatchMode=yes $Target `"$remoteCommand`""

    & cmd.exe /d /c $archiveCommand
    if ($LASTEXITCODE -ne 0) {
        throw "Source sync failed with exit code $LASTEXITCODE"
    }
}

function Ensure-RemoteDataDirs {
    Invoke-Remote "mkdir -p '$AppDir/data/static' '$AppDir/data/media' '$AppDir/data/private_media' '$AppDir/data/logs' '$AppDir/data/postgres' '$AppDir/data/redis'"
}

function Invoke-Ops {
    param([string]$OpsAction)

    Invoke-Remote "sudo -n /usr/local/sbin/onedu-ops $OpsAction"
}

Require-Command "ssh"

switch ($Action) {
    "sync" {
        Sync-Source
    }
    "deploy" {
        Sync-Source
        Ensure-RemoteDataDirs
        Invoke-Ops "deploy"
        Invoke-Ops "health"
    }
    default {
        Invoke-Ops $Action
    }
}
