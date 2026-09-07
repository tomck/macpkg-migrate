# macpkg-migrate

Multi-manager macOS package consolidation planner. It inventories Homebrew,
MacPorts, and Fink, consumes the neutral `macpkg-catalog`, groups related
package identities, and recommends one manager/package per program.

It is deliberately plan-only in its first release: it writes a JSON plan and
CSV review file, but never installs or removes packages automatically.

```sh
macpkg-migrate plan
macpkg-migrate plan --preference fink,macports,homebrew --refresh-catalog
```
