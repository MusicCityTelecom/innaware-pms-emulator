$ErrorActionPreference = 'Stop'
git fetch origin --tags
if ($LASTEXITCODE -ne 0) { throw 'Unable to verify remote tags.' }
$Tag = $env:RELEASE_TAG
$Existing = git tag --list $Tag
if ($Existing) {
    $Target = (git rev-list -n 1 $Tag).Trim()
    if ($Target -ne $env:EXACT_SOURCE_SHA) {
        throw "Tag $Tag belongs to $Target. Bump the version before publishing a different commit."
    }
}
$ReleasesJson = gh release list --repo $env:GITHUB_REPOSITORY --limit 100 --json tagName,isDraft
if ($LASTEXITCODE -ne 0) { throw 'Unable to verify existing GitHub releases.' }
$Published = @($ReleasesJson | ConvertFrom-Json | Where-Object { $_.tagName -eq $Tag })
if ($Published.Count -gt 0) {
    'RELEASE_ALLOWED=false' | Out-File -FilePath $env:GITHUB_ENV -Append
    Write-Host "Release $Tag already exists. Its artifacts will remain unchanged."
    return
}
if (-not $Existing) {
    git config user.name 'github-actions[bot]'
    git config user.email '41898282+github-actions[bot]@users.noreply.github.com'
    git tag -a $Tag $env:EXACT_SOURCE_SHA -m "InnAware PMS Emulator $Tag"
    if ($LASTEXITCODE -ne 0) { throw 'Unable to create release tag.' }
    git push origin "refs/tags/$Tag"
    if ($LASTEXITCODE -ne 0) { throw 'Unable to publish release tag.' }
}
'RELEASE_ALLOWED=true' | Out-File -FilePath $env:GITHUB_ENV -Append
