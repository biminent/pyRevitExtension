<#
.SYNOPSIS
    Regenerate all Biminent ribbon icons in the brand gradient.

.DESCRIPTION
    Two styles:
      -Mode continuous  (default) : ONE gradient flows across the whole ribbon,
                                     each icon is a slice. Lightest teal far left,
                                     darkest navy far right. Re-run after adding,
                                     removing, or reordering any tool, because every
                                     icon's colour depends on its position + the count.
      -Mode tile                  : every icon carries the FULL teal->navy gradient
                                     on its own (position-independent, no re-run
                                     needed when tools change).

    The $Order list below is the assumed LEFT-TO-RIGHT ribbon order (pyRevit lays
    panels/buttons out alphabetically by folder name). If your ribbon shows a
    different order, just reorder the entries here and re-run.

.EXAMPLE
    powershell -File regen_icons.ps1                 # continuous (cross-ribbon)
    powershell -File regen_icons.ps1 -Mode tile      # per-tile full gradient
#>
param(
    [ValidateSet("continuous", "tile")]
    [string]$Mode = "continuous"
)

Add-Type -AssemblyName System.Drawing

# Extension root = parent of this script's folder.
$ext = Split-Path -Parent $PSScriptRoot
$tab = Join-Path $ext "BMT.tab"

# ---- LEFT-TO-RIGHT RIBBON ORDER (edit to remap the gradient) ----------------
# rel  = icon path relative to the BMT.tab folder
# glyph/fp = text drawn on the tile and its pixel font size
$Order = @(
    @{ rel = "Biminent.panel\About.pushbutton\icon.png";                     glyph = "B";   fp = 52 }
    @{ rel = "Biminent.panel\links.stack\ApartmentSheets.urlbutton\icon.png"; glyph = "AS";  fp = 42 }
    @{ rel = "Biminent.panel\links.stack\Website.urlbutton\icon.png";         glyph = "www"; fp = 28 }
    @{ rel = "DWG.panel\LinkDWGs.pushbutton\icon.png";                        glyph = "DWG"; fp = 27 }
    @{ rel = "DWG.panel\LinkTools.stack\OpenDWGLink.pushbutton\icon.png";      glyph = "Open"; fp = 22 }
    @{ rel = "DWG.panel\LinkTools.stack\ReloadDWGLink.pushbutton\icon.png";    glyph = "Re";  fp = 40 }
    @{ rel = "Naming.panel\RenameStudio.pushbutton\icon.png";                 glyph = "Aa";  fp = 42 }
    @{ rel = "Review.panel\PurgePlus.pushbutton\icon.png";                    glyph = "P+";  fp = 40 }
    @{ rel = "Review.panel\Warnings.pushbutton\icon.png";                     glyph = "!";   fp = 56 }
    @{ rel = "Select.panel\SelectInRange.pushbutton\icon.png";                glyph = "<>";  fp = 40 }
    @{ rel = "Select.panel\SelectInScopeBox.pushbutton\icon.png";             glyph = "[+]"; fp = 34 }
    @{ rel = "Select.panel\SelectSimilar.pushbutton\icon.png";                glyph = "[~]"; fp = 34 }
)

# ---- brand gradient (Biminent.Shared.UI HeaderGradientBrush stops) ----------
$Stops = @(
    @{ p = 0.0; c = @(0x2a, 0x91, 0x87) }   # teal
    @{ p = 0.5; c = @(0x00, 0x3B, 0x73) }   # blue
    @{ p = 1.0; c = @(0x00, 0x1A, 0x3D) }   # navy
)

function Get-GradientColor([double]$t) {
    if ($t -le 0) { return $Stops[0].c }
    if ($t -ge 1) { return $Stops[-1].c }
    for ($i = 0; $i -lt $Stops.Count - 1; $i++) {
        $a = $Stops[$i]; $b = $Stops[$i + 1]
        if ($t -ge $a.p -and $t -le $b.p) {
            $f = ($t - $a.p) / ($b.p - $a.p)
            return @(
                [int]($a.c[0] + ($b.c[0] - $a.c[0]) * $f),
                [int]($a.c[1] + ($b.c[1] - $a.c[1]) * $f),
                [int]($a.c[2] + ($b.c[2] - $a.c[2]) * $f)
            )
        }
    }
    return $Stops[-1].c
}

function New-Icon {
    param([string]$OutFile, [string]$Glyph, [int]$FontPt, [double]$T0, [double]$T1, [int]$Size = 96)
    $a = Get-GradientColor $T0; $b = Get-GradientColor $T1
    $col0 = [System.Drawing.Color]::FromArgb(255, $a[0], $a[1], $a[2])
    $col1 = [System.Drawing.Color]::FromArgb(255, $b[0], $b[1], $b[2])

    $bmp = New-Object System.Drawing.Bitmap($Size, $Size)
    $g = [System.Drawing.Graphics]::FromImage($bmp)
    $g.SmoothingMode = [System.Drawing.Drawing2D.SmoothingMode]::AntiAlias
    $g.TextRenderingHint = [System.Drawing.Text.TextRenderingHint]::AntiAliasGridFit
    $g.Clear([System.Drawing.Color]::Transparent)

    $r = [int]($Size * 0.2)
    $tile = New-Object System.Drawing.Drawing2D.GraphicsPath
    $tile.AddArc(0, 0, 2 * $r, 2 * $r, 180, 90)
    $tile.AddArc($Size - 2 * $r - 1, 0, 2 * $r, 2 * $r, 270, 90)
    $tile.AddArc($Size - 2 * $r - 1, $Size - 2 * $r - 1, 2 * $r, 2 * $r, 0, 90)
    $tile.AddArc(0, $Size - 2 * $r - 1, 2 * $r, 2 * $r, 90, 90)
    $tile.CloseFigure()

    $grad = New-Object System.Drawing.Drawing2D.LinearGradientBrush(
        (New-Object System.Drawing.Point(0, 0)),
        (New-Object System.Drawing.Point($Size, 0)), $col0, $col1)
    $g.FillPath($grad, $tile)

    $font = New-Object System.Drawing.Font("Segoe UI", $FontPt, [System.Drawing.FontStyle]::Bold, [System.Drawing.GraphicsUnit]::Pixel)
    $fg = New-Object System.Drawing.SolidBrush([System.Drawing.Color]::White)
    $fmt = New-Object System.Drawing.StringFormat
    $fmt.Alignment = [System.Drawing.StringAlignment]::Center
    $fmt.LineAlignment = [System.Drawing.StringAlignment]::Center
    $g.DrawString($Glyph, $font, $fg, (New-Object System.Drawing.RectangleF(0, 0, $Size, $Size)), $fmt)

    $g.Dispose()
    $bmp.Save($OutFile, [System.Drawing.Imaging.ImageFormat]::Png)
    $bmp.Dispose()
}

$n = $Order.Count
for ($i = 0; $i -lt $n; $i++) {
    $item = $Order[$i]
    $out = Join-Path $tab $item.rel
    if (-not (Test-Path (Split-Path -Parent $out))) {
        Write-Warning "Missing folder for $($item.rel) - skipped"
        continue
    }
    if ($Mode -eq "continuous") {
        $t0 = [double]$i / $n
        $t1 = [double]($i + 1) / $n
    }
    else {
        $t0 = 0.0; $t1 = 1.0   # full gradient on every tile
    }
    New-Icon -OutFile $out -Glyph $item.glyph -FontPt $item.fp -T0 $t0 -T1 $t1
    Write-Output ("{0,-4} {1}" -f $item.glyph, $item.rel)
}

Write-Output ""
Write-Output "Done ($Mode). $n icons regenerated. Reload pyRevit to see them."
