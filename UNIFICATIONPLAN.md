# macpkgmap unification plan

This plan is for the `brew2port` and `brew2fink` work threads. The goal is to
make `macpkgmap` the one catalog client and remove duplicated catalog-download
and cache logic from each migration application.

## Scope

Change only the consumer applications: `brew2port` and `brew2fink`.
`macpkgmap` remains responsible for downloading, caching, validating, and
serving catalog data. Do not copy its source-fetch logic into either consumer.

## Naming

Use neutral package-manager terminology in user-facing code and data:

- `package`, not `homebrew-package`
- `source_manager`, not a field that implies Homebrew is always the source
- `target_manager`, not a field that implies MacPorts is always the target

Homebrew remains one possible source manager, not the abstraction boundary.

## macpkgmap client contract

Consumers should invoke the installed `macpkgmap` executable:

```text
macpkgmap relations <manager> <package_type> <name>
macpkgmap lookup <manager> <package_type> <name>
macpkgmap popularity <manager> <package_type> <name>
```

The result is JSON with a `catalog_version` and `results` array. Consumers may
cache query results for the current run, but must not create a second persistent
catalog cache or implement another download URL.

If `macpkgmap` is unavailable, explain:

```sh
brew tap tomck/escapefrombrewyork
brew install macpkgmap
```

Do not silently revert to the old large MacPorts API download path.

## brew2port changes

1. Replace its direct catalog downloader with a subprocess client for
   `macpkgmap`.
2. Query relationships for each inventoried package.
3. Preserve statuses: `automatic` may be recommended; `needs-review`,
   `near-hit`, `missing`, and `not-equivalent` must not be auto-installed.
4. Rename Homebrew-specific plan fields to neutral names while accepting old
   fields when reading existing plans.
5. Keep MacPorts installation, dry-run, verification, and rollback guidance.
6. Add mocked-subprocess tests for Ansible near-hits and known negatives.

## brew2fink changes

1. Replace its direct catalog downloader with the same subprocess client.
2. Query relationships for each inventoried package.
3. Preserve the same confidence and review rules as `brew2port`.
4. Rename Homebrew-specific plan fields to neutral names while accepting old
   fields when reading existing plans.
5. Keep Fink installation and verification behavior separate from MacPorts.
6. Test that a Fink confident mapping can win over a MacPorts near-hit when
   Fink is preferred.

## Shared behavior

- No consumer downloads the full catalog independently.
- No consumer removes another package manager automatically.
- Every plan records `catalog_version`.
- Every near-hit remains review-only.
- Existing plan files remain readable during the transition.
- No-argument guides explain installing `macpkgmap` first.
- Tap formulas should declare `macpkgmap` as a dependency.

## Verification

Each thread should run its tests and verify:

```sh
brew2port --help
brew2fink --help
macpkgmap --help
```

Use mocked `macpkgmap` results covering one confident mapping, one near-hit,
one missing package, and one explicitly rejected equivalence.
