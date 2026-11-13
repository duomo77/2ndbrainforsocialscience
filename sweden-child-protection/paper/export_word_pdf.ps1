$ErrorActionPreference = 'Stop'
$paperRoot = $PSScriptRoot
$inputPath = (Resolve-Path -LiteralPath (Join-Path $paperRoot 'output/Sweden_ChildProtection_Policy_Draft_KO.docx')).Path
$outputPath = Join-Path $paperRoot 'output/Sweden_ChildProtection_Policy_Draft_KO.pdf'
$word = $null
$document = $null
try {
    $word = New-Object -ComObject Word.Application
    $word.Visible = $false
    $word.DisplayAlerts = 0
    $document = $word.Documents.Open($inputPath, $false, $true)
    $null = $document.Fields.Update()
    $document.Repaginate()
    Write-Output ('Word pages: ' + $document.ComputeStatistics(2))
    $document.ExportAsFixedFormat($outputPath, 17)
    Write-Output ('Exported PDF: ' + $outputPath)
}
finally {
    if ($null -ne $document) { $document.Close(0) }
    if ($null -ne $word) { $word.Quit() }
    if ($null -ne $document) { $null = [System.Runtime.InteropServices.Marshal]::ReleaseComObject($document) }
    if ($null -ne $word) { $null = [System.Runtime.InteropServices.Marshal]::ReleaseComObject($word) }
}
