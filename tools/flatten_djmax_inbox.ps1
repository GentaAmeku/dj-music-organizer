param(
    [Parameter(Mandatory = $true)]
    [string]$UsbRoot,
    [Parameter(Mandatory = $true)]
    [string]$Target,
    [switch]$Apply
)

$ErrorActionPreference = "Stop"

$audioExtensions = @(".wav", ".aiff", ".aif", ".mp3", ".m4a", ".flac")
$hangulL = @("g","kk","n","d","tt","r","m","b","pp","s","ss","","j","jj","ch","k","t","p","h")
$hangulV = @("a","ae","ya","yae","eo","e","yeo","ye","o","wa","wae","oe","yo","u","wo","we","wi","yu","eu","ui","i")
$hangulT = @("","k","kk","ks","n","nj","nh","t","l","lk","lm","lb","ls","lt","lp","lh","m","p","ps","t","t","ng","t","t","k","t","p","h")

function Convert-HangulChar {
    param([char]$Char)
    $code = [int]$Char
    if ($code -ge 0xAC00 -and $code -le 0xD7A3) {
        $syllable = $code - 0xAC00
        $lead = [math]::Floor($syllable / 588)
        $vowel = [math]::Floor(($syllable % 588) / 28)
        $tail = $syllable % 28
        return "$($script:hangulL[$lead])$($script:hangulV[$vowel])$($script:hangulT[$tail])"
    }
    return [string]$Char
}

function Convert-ToAsciiFileName {
    param([string]$FileName)

    $stem = [IO.Path]::GetFileNameWithoutExtension($FileName)
    $ext = [IO.Path]::GetExtension($FileName).ToLowerInvariant()
    $stem = $stem.Normalize([Text.NormalizationForm]::FormKC).Replace([char]0x00A0, " ")

    $romanized = [Text.StringBuilder]::new()
    foreach ($char in $stem.ToCharArray()) {
        [void]$romanized.Append((Convert-HangulChar -Char $char))
    }

    $normalized = $romanized.ToString().Normalize([Text.NormalizationForm]::FormKD)
    $safe = [Text.StringBuilder]::new()
    foreach ($char in $normalized.ToCharArray()) {
        $code = [int]$char
        if ($code -lt 32 -or $code -gt 126 -or '<>:"/\|?*'.Contains($char)) {
            [void]$safe.Append("_")
        } else {
            [void]$safe.Append($char)
        }
    }

    $name = [regex]::Replace($safe.ToString(), "\s+", " ")
    $name = [regex]::Replace($name, "_+", "_").Trim(" ._")
    if ([string]::IsNullOrWhiteSpace($name)) {
        $name = "Track"
    }
    return "$name$ext"
}

function Get-UniqueTarget {
    param(
        [string]$TargetDirectory,
        [string]$FileName,
        [System.Collections.Generic.HashSet[string]]$UsedNames
    )

    $basePath = Join-Path $TargetDirectory $FileName
    if (-not $UsedNames.Contains($FileName) -and -not (Test-Path -LiteralPath $basePath)) {
        [void]$UsedNames.Add($FileName)
        return [pscustomobject]@{ Path = $basePath; Collision = $false }
    }

    $stem = [IO.Path]::GetFileNameWithoutExtension($FileName)
    $ext = [IO.Path]::GetExtension($FileName)
    for ($i = 2; $i -lt 10000; $i++) {
        $candidateName = "$stem`__$i$ext"
        $candidatePath = Join-Path $TargetDirectory $candidateName
        if (-not $UsedNames.Contains($candidateName) -and -not (Test-Path -LiteralPath $candidatePath)) {
            [void]$UsedNames.Add($candidateName)
            return [pscustomobject]@{ Path = $candidatePath; Collision = $true }
        }
    }
    throw "Could not create unique target for $FileName"
}

$usbRootResolved = (Resolve-Path -LiteralPath $UsbRoot).Path.TrimEnd("\")
New-Item -ItemType Directory -Force -Path $Target | Out-Null
$targetResolved = (Resolve-Path -LiteralPath $Target).Path.TrimEnd("\")

if (-not $targetResolved.StartsWith($usbRootResolved, [StringComparison]::OrdinalIgnoreCase)) {
    throw "Refusing target outside USB root: $targetResolved"
}

$albumRoots = Get-ChildItem -LiteralPath $usbRootResolved -Directory -Force |
    Where-Object { $_.Name -like "DJMAX RESPECT V - *" } |
    Sort-Object Name

$files = foreach ($root in $albumRoots) {
    Get-ChildItem -LiteralPath $root.FullName -Recurse -File -Force |
        Where-Object {
            $audioExtensions -contains $_.Extension.ToLowerInvariant() -and
            $_.Name -notlike "._*"
        }
}

$usedNames = [System.Collections.Generic.HashSet[string]]::new([StringComparer]::OrdinalIgnoreCase)
Get-ChildItem -LiteralPath $targetResolved -File -Force | ForEach-Object { [void]$usedNames.Add($_.Name) }

$plan = foreach ($file in ($files | Sort-Object FullName)) {
    $targetName = Convert-ToAsciiFileName -FileName $file.Name
    $unique = Get-UniqueTarget -TargetDirectory $targetResolved -FileName $targetName -UsedNames $usedNames
    $targetPath = [string]$unique.Path
    [pscustomobject]@{
        Source = $file.FullName
        Target = $targetPath
        OriginalName = $file.Name
        TargetName = [IO.Path]::GetFileName($targetPath)
        ChangedName = ($file.Name -cne [IO.Path]::GetFileName($targetPath))
        Collision = [bool]$unique.Collision
    }
}

$libraryRoot = Split-Path -Parent (Split-Path -Parent $targetResolved)
$reportDir = Join-Path (Join-Path $libraryRoot "reports") (Get-Date -Format "yyyy-MM-dd")
New-Item -ItemType Directory -Force -Path $reportDir | Out-Null
$reportBase = Join-Path $reportDir ("djmax_flatten_report_{0}" -f (Get-Date -Format "yyyyMMdd-HHmmss"))
$jsonReportPath = "$reportBase.json"
$mdReportPath = "$reportBase.md"

$summary = [pscustomobject]@{
    generated_at = (Get-Date).ToString("o")
    usb_root = $usbRootResolved
    target = $targetResolved
    audio_files = $plan.Count
    renamed_or_ascii_changed = @($plan | Where-Object ChangedName).Count
    collisions_resolved = @($plan | Where-Object Collision).Count
}

$jsonReport = [pscustomobject]@{
    summary = $summary
    moves = $plan
}
$jsonReport | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath $jsonReportPath -Encoding UTF8

$mdLines = [System.Collections.Generic.List[string]]::new()
$mdLines.Add("# DJMAX Flatten Report")
$mdLines.Add("")
$mdLines.Add("## Summary")
$mdLines.Add("")
$mdLines.Add("- Generated at: $($summary.generated_at)")
$mdLines.Add("- USB root: ``$($summary.usb_root)``")
$mdLines.Add("- Target: ``$($summary.target)``")
$mdLines.Add("- Audio files: $($summary.audio_files)")
$mdLines.Add("- Renamed or ASCII changed: $($summary.renamed_or_ascii_changed)")
$mdLines.Add("- Collisions resolved: $($summary.collisions_resolved)")
$mdLines.Add("")

$collisionPreview = @($plan | Where-Object Collision)
if ($collisionPreview.Count -gt 0) {
    $mdLines.Add("## Collisions")
    $mdLines.Add("")
    $mdLines.Add("| Original name | Target name |")
    $mdLines.Add("| --- | --- |")
    foreach ($item in $collisionPreview) {
        $mdLines.Add("| ``$($item.OriginalName.Replace('|', '\|'))`` | ``$($item.TargetName.Replace('|', '\|'))`` |")
    }
    $mdLines.Add("")
}

$changedPreview = @($plan | Where-Object ChangedName | Select-Object -First 100)
if ($changedPreview.Count -gt 0) {
    $mdLines.Add("## Rename Preview")
    $mdLines.Add("")
    $mdLines.Add("| Original name | Target name |")
    $mdLines.Add("| --- | --- |")
    foreach ($item in $changedPreview) {
        $mdLines.Add("| ``$($item.OriginalName.Replace('|', '\|'))`` | ``$($item.TargetName.Replace('|', '\|'))`` |")
    }
    $mdLines.Add("")
    if ($summary.renamed_or_ascii_changed -gt $changedPreview.Count) {
        $mdLines.Add("Only the first $($changedPreview.Count) renamed items are shown here. See the JSON report for the full move list.")
        $mdLines.Add("")
    }
}

$mdLines | Set-Content -LiteralPath $mdReportPath -Encoding UTF8

if ($Apply) {
    "APPLY MODE"
} else {
"DRY RUN - no files will be moved"
}
"usb_root: $usbRootResolved"
"target: $targetResolved"
"json_report: $jsonReportPath"
"md_report: $mdReportPath"
""
"audio_files: $($plan.Count)"
$changedItems = @($plan | Where-Object ChangedName)
$collisionItems = @($plan | Where-Object Collision)
"renamed_or_ascii_changed: $($changedItems.Count)"
"collisions_resolved: $($collisionItems.Count)"
""

$collisions = $collisionItems
if ($collisions.Count -gt 0) {
    "Collisions:"
    $collisions | Select-Object -First 50 | ForEach-Object { "  $($_.OriginalName) -> $($_.TargetName)" }
    ""
}

$changed = $changedItems
if ($changed.Count -gt 0) {
    "Rename examples:"
    $changed | Select-Object -First 50 | ForEach-Object { "  $($_.OriginalName) -> $($_.TargetName)" }
    ""
}

if ($Apply) {
    foreach ($item in $plan) {
        if (Test-Path -LiteralPath $item.Target) {
            throw "Target already exists: $($item.Target)"
        }
        Move-Item -LiteralPath $item.Source -Destination $item.Target
    }
    "Moved: $($plan.Count)"
}
