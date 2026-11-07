# Automatic GitHub releases on `v*` tag push

**Status:** approved design  
**Date:** 2026-11-07  
**Repo:** `Esspel/ha_coop_sverige`

## Context

`ha_coop_sverige` is a Home Assistant custom integration. HACS installs it directly from the repository and tracks GitHub Releases by tag, so the release artifact that matters most is the git tag + GitHub Release entry — not a build artifact.

Prior state: no `.github` directory, no CI/CD workflows, no git tags, no references to "release" anywhere in the repo. Version lives only in `manifest.json` (currently `1.1.0`).

## Goal

Pushing a git tag matching `v*` (e.g. `v1.2.0`) automatically creates a GitHub Release on GitHub, so maintainers can cut a release by simply bumping the version, committing, tagging, and pushing.

## Trigger

GitHub Actions `push` on tags matching `v*`:
- `v1.2.0`, `v2.0.0-rc.1`, etc. all match
- Branches and non-`v` tags do not trigger

## Workflow (`.github/workflows/release.yml`)

Job `create-release` on `ubuntu-latest`, `contents: write` permission:

1. `actions/checkout@v4` — check out the repo at the tagged commit
2. `ncipollo/release-action@v1` — create a GitHub Release:
   - `tag` / `name` = `${{ github.ref_name }}` (the pushed tag)
   - `generateReleaseNotes: true` — auto-generated changelog from commits since the previous tag
   - `draft: false`, `prerelease: false`

No version-derivation logic: the tag *is* the version. No build artifacts — HACS pulls from the repo zip.

## Files touched

- New: `.github/workflows/release.yml`
- New: `docs/superpowers/specs/2026-11-07-automatic-github-releases-design.md` (this document)

## How to use

1. Bump `version` in `manifest.json` (e.g. `1.1.0` → `1.2.0`)
2. Commit
3. Tag `v1.2.0` and push the tag
4. GitHub Actions creates the release automatically

## Success criteria

- Pushing tag `v1.2.0` results in a GitHub Release named `v1.2.0` appearing on the repository's Releases page
- No manual release creation required

## Non-goals

- Auto-bumping `manifest.json` (version bump remains manual)
- Building/distributing artifacts (HACS installs from the repo)
- Publishing to PyPI, npm, or any other registry

## Approval

Pending user review of this spec.
