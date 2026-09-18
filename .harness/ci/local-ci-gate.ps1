$ErrorActionPreference = "Stop"

$previousBytecode = $env:PYTHONDONTWRITEBYTECODE
$previousCachePrefix = $env:PYTHONPYCACHEPREFIX
$cacheRoot = [System.IO.Path]::GetFullPath((Join-Path ([System.IO.Path]::GetTempPath()) ("harness-ci-" + [guid]::NewGuid().ToString("N"))))
try {
    $env:PYTHONDONTWRITEBYTECODE = "1"
    $env:PYTHONPYCACHEPREFIX = $cacheRoot
    python -m pytest -q scripts\verification\tests -p no:cacheprovider
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    python -m compileall -q scripts\verification
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    python scripts\verification\harness.py --profile all
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    python scripts\verification\harness.py --profile mainline-unified-runtime
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
}
finally {
    $env:PYTHONDONTWRITEBYTECODE = $previousBytecode
    $env:PYTHONPYCACHEPREFIX = $previousCachePrefix
    if (Test-Path -LiteralPath $cacheRoot) {
        $resolvedCache = (Resolve-Path -LiteralPath $cacheRoot).Path
        $tempRoot = [System.IO.Path]::GetFullPath([System.IO.Path]::GetTempPath()).TrimEnd('\') + '\'
        if (-not $resolvedCache.StartsWith($tempRoot, [System.StringComparison]::OrdinalIgnoreCase)) {
            throw "Refusing to clean cache outside the temporary directory: $resolvedCache"
        }
        Remove-Item -LiteralPath $resolvedCache -Recurse -Force
    }
}
