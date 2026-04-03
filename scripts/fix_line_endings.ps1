#!/usr/bin/env pwsh
# 将指定目录下所有文本文件的 CRLF 转换为 LF

param(
    [string]$Path = ".",
    [string[]]$Extensions = @("*.py", "*.yml", "*.yaml", "*.toml", "*.json", "*.md", "*.vue", "*.ts", "*.js", "*.css", "*.html", "*.scss", "*.sh")
)

$count = 0
foreach ($ext in $Extensions) {
    Get-ChildItem -Path $Path -Filter $ext -Recurse -File |
        Where-Object { $_.FullName -notmatch '[\\/](\.venv|\.git|node_modules|__pycache__|\.pnpm-store)[\\/]' } |
        ForEach-Object {
            $bytes = [IO.File]::ReadAllBytes($_.FullName)
            $hasCR = $false
            foreach ($b in $bytes) {
                if ($b -eq 13) { $hasCR = $true; break }
            }
            if ($hasCR) {
                $content = [IO.File]::ReadAllText($_.FullName)
                $content = $content -replace "`r`n", "`n"
                [IO.File]::WriteAllText($_.FullName, $content, [Text.UTF8Encoding]::new($false))
                $count++
                # 不逐行输出，避免大量输出
            }
        }
}

Write-Output "Done! Converted $count files to LF."
