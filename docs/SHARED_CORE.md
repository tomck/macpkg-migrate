# Shared macpkg-migrate core

The reusable API lives in the lightweight `macpkg-migrate-core` distribution,
under the `macpkg_migrate_core` import package. It is manager-neutral and is
the integration point for `brew2port`, `brew2fink`, and the combined
`macpkg-migrate` command.

```python
from macpkg_migrate_core import (
    Identity, candidates_for, choose_candidate, dry_run,
    load_snapshot, plan_record,
)
```

`load_snapshot(path)` reads one pinned `catalog.json`, relation-array JSON, or
SQLite export. It never downloads data. `candidates_for(relations, identity)`
preserves all matching catalog relations. `choose_candidate` selects only
`review_status == "automatic"`; near-hits and ambiguous results remain
review-only. `plan_record` carries catalog version, relation type, confidence,
matching method, evidence, and source catalog versions. `install_allowed` and
`dry_run` enforce the shared policy that review-only candidates cannot be
installed automatically and that no package is ever removed implicitly.

The core does not run `brew`, `port`, or `fink`, inspect manager-specific
availability, or verify installed files. Those operations remain in the
manager-specific adapters.

## Release strategy

Version `0.3.0` is the first shared-core API release. Consumers should depend
on `macpkg-migrate-core>=0.3,<0.4` while this API stabilizes. The full
`macpkg-migrate` application depends on this lightweight distribution and
retains a compatibility import at `macpkg_migrate.core`. Future breaking API
changes should increment the minor version before 1.0; a stable post-1.0 API
should use normal major-version changes. The Homebrew tap should update the
formula only after the standalone tests and a clean install pass.
