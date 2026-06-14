param(
    [Parameter(Mandatory = $true)]
    [string]$LibraryRoot
)

$ErrorActionPreference = "Stop"

$libraryRootResolved = (Resolve-Path -LiteralPath $LibraryRoot).Path.TrimEnd("\")
$reportsRoot = Join-Path $libraryRootResolved "reports"
New-Item -ItemType Directory -Force -Path $reportsRoot | Out-Null

$reportFiles = Get-ChildItem -LiteralPath $reportsRoot -Recurse -File -Force |
    Where-Object { $_.Extension.ToLowerInvariant() -in @(".json", ".md", ".csv") } |
    Sort-Object -Property @{ Expression = "LastWriteTime"; Descending = $true }, FullName

$lines = [System.Collections.Generic.List[string]]::new()
$lines.Add("# DJ Music Reports Index")
$lines.Add("")
$lines.Add("Generated at: $(Get-Date -Format o)")
$lines.Add("")
$lines.Add('Reports are grouped by date under `reports/YYYY-MM-DD/`. Prefer JSON for machine-readable history and Markdown for human review.')
$lines.Add("")

if ($reportFiles.Count -eq 0) {
    $lines.Add("No reports found.")
} else {
    $lines.Add("| Date | Type | Report | Updated |")
    $lines.Add("| --- | --- | --- | --- |")
    foreach ($file in $reportFiles) {
        $base = $reportsRoot.TrimEnd("\") + "\"
        $relative = $file.FullName.Substring($base.Length).Replace("\", "/")
        $date = $file.Directory.Name
        $type = $file.Extension.TrimStart(".").ToUpperInvariant()
        $updated = $file.LastWriteTime.ToString("yyyy-MM-dd HH:mm:ss")
        $lines.Add("| $date | $type | [$relative]($relative) | $updated |")
    }
}

$indexPath = Join-Path $reportsRoot "INDEX.md"
$lines | Set-Content -LiteralPath $indexPath -Encoding UTF8
Write-Output $indexPath
