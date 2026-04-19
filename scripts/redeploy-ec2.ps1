param(
    [string]$TerraformDir = "Terraform",
    [string]$RemoteUser = "ec2-user",
    [string]$AppDir = "/opt/DistributedInfraMonitoring",
    [string]$Branch = "",
    [string]$KeyPath = "",
    [ValidateSet("all", "capital", "regional", "infra")]
    [string]$Role = "all",
    [switch]$SkipDeps
)

$ErrorActionPreference = "Stop"

function Get-TerraformOutput {
    param([string]$Dir)

    if (-not (Test-Path -LiteralPath $Dir)) {
        throw "Terraform directory not found: $Dir"
    }

    $resolvedDir = (Resolve-Path -LiteralPath $Dir).Path
    $json = terraform "-chdir=$resolvedDir" output -json
    if (-not $json) {
        throw "terraform output returned no data. Run terraform apply first."
    }

    return $json | ConvertFrom-Json
}

function Get-RoleTargets {
    param(
        [object]$Outputs,
        [string]$SelectedRole
    )

    $roles = @()
    if ($SelectedRole -eq "all" -or $SelectedRole -eq "capital") {
        $roles += @{
            Name = "capital"
            Service = "distinfra-capital.service"
            Output = $Outputs.capital_public_ips.value
        }
    }
    if ($SelectedRole -eq "all" -or $SelectedRole -eq "regional") {
        $roles += @{
            Name = "regional"
            Service = "distinfra-regional.service"
            Output = $Outputs.regional_public_ips.value
        }
    }
    if ($SelectedRole -eq "all" -or $SelectedRole -eq "infra") {
        $roles += @{
            Name = "infra"
            Service = "distinfra-infra.service"
            Output = $Outputs.infra_public_ips.value
        }
    }

    $targets = @()
    foreach ($roleInfo in $roles) {
        if ($null -eq $roleInfo.Output) {
            continue
        }

        foreach ($node in $roleInfo.Output.PSObject.Properties) {
            if ([string]::IsNullOrWhiteSpace($node.Value)) {
                Write-Warning "Skipping $($node.Name): no public IP in Terraform output."
                continue
            }

            $targets += [pscustomobject]@{
                Name = $node.Name
                Role = $roleInfo.Name
                PublicIp = $node.Value
                Service = $roleInfo.Service
            }
        }
    }

    return $targets
}

function Invoke-RemoteRedeploy {
    param(
        [object]$Target,
        [string]$User,
        [string]$Directory,
        [string]$GitBranch,
        [string]$IdentityFile,
        [bool]$InstallDeps
    )

    $remoteCommands = @(
        "set -euo pipefail",
        "cd '$Directory'",
        "git fetch origin"
    )

    if (-not [string]::IsNullOrWhiteSpace($GitBranch)) {
        $remoteCommands += "git checkout '$GitBranch'"
    }

    $remoteCommands += "git pull --ff-only"

    if ($InstallDeps) {
        $remoteCommands += "uv sync || true"
        $remoteCommands += "uv pip install websockets pydantic colorama"
    }

    $remoteCommands += "sudo systemctl restart '$($Target.Service)'"
    $remoteCommands += "sudo systemctl --no-pager --full status '$($Target.Service)' | head -n 20"

    $remoteScript = $remoteCommands -join " && "
    $sshArgs = @(
        "-o", "StrictHostKeyChecking=accept-new"
    )

    if (-not [string]::IsNullOrWhiteSpace($IdentityFile)) {
        $sshArgs += @("-i", $IdentityFile)
    }

    $sshArgs += "$User@$($Target.PublicIp)"
    $sshArgs += $remoteScript

    Write-Host "[$($Target.Role):$($Target.Name)] redeploying on $($Target.PublicIp)"
    & ssh @sshArgs
    if ($LASTEXITCODE -ne 0) {
        throw "Redeploy failed for $($Target.Name) ($($Target.PublicIp))"
    }
}

$outputs = Get-TerraformOutput -Dir $TerraformDir
$targets = Get-RoleTargets -Outputs $outputs -SelectedRole $Role

if ($targets.Count -eq 0) {
    throw "No targets found for role '$Role'. Check Terraform outputs and whether instances exist."
}

foreach ($target in $targets) {
    Invoke-RemoteRedeploy `
        -Target $target `
        -User $RemoteUser `
        -Directory $AppDir `
        -GitBranch $Branch `
        -IdentityFile $KeyPath `
        -InstallDeps:(-not $SkipDeps)
}

Write-Host "Redeploy complete for $($targets.Count) target(s)."
