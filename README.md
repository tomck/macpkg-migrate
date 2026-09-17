# macpkg-migrate

Multi-manager macOS package consolidation planner. It inventories Homebrew,
MacPorts, and Fink, consumes the neutral `macpkg-catalog` through the
installed `macpkgmap` client, groups related package identities, and
recommends one manager/package per program.

Workflow: `inventory` → `plan` (JSON plan + CSV review file) → `migrate`
(dry run by default) → `migrate --plan ... --install` applies the reviewed
plan after confirmation → `verify` checks which recommendations are
installed. Only MacPorts and Fink targets are installed; Homebrew targets
are reported but never installed. Nothing is ever removed automatically.

Requires the catalog client:

```sh
brew tap tomck/escapefrombrewyork && brew install macpkgmap
```

```sh
macpkg-migrate plan
macpkg-migrate plan --preference fink,macports,homebrew
```
