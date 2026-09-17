"""Failure-path tests: missing managers, missing backend, real verify."""
import io
import json
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch

from macpkg_migrate import cli
from macpkg_migrate import inventory
from macpkg_migrate.binaries import ensure_binaries
from macpkg_migrate.catalog import fetch


def installed(name, manager="homebrew", package_type="formula"):
    return {"manager": manager, "type": package_type, "name": name}


class FetchBackendTests(unittest.TestCase):
    def test_missing_backend_raises_helpful_error(self):
        # An unresolvable client name keeps this hermetic: the real exec
        # must fail no matter what the host PATH contains.
        with patch("shutil.which", return_value=None):
            with self.assertRaises(RuntimeError) as ctx:
                fetch([installed("wget")], client="macpkgmap-missing-test")
        self.assertIn("macpkgmap-missing-test", str(ctx.exception))

    def test_failed_query_warns_and_skips(self):
        class Result:
            returncode = 1
            stdout = ""

        warnings = []
        result = fetch(
            [installed("wget")],
            run=lambda command, **kwargs: Result(),
            progress=warnings.append,
        )
        self.assertEqual(result, [])
        self.assertTrue(any("wget" in warning for warning in warnings))

    def test_invalid_json_warns_and_skips(self):
        class Result:
            returncode = 0
            stdout = "not json{"

        warnings = []
        result = fetch(
            [installed("wget")],
            run=lambda command, **kwargs: Result(),
            progress=warnings.append,
        )
        self.assertEqual(result, [])
        self.assertTrue(any("wget" in warning for warning in warnings))


class InventoryRobustnessTests(unittest.TestCase):
    def test_homebrew_without_brew_returns_empty(self):
        def run(command, **kwargs):
            raise FileNotFoundError(2, "No such file", "brew")

        self.assertEqual(inventory.homebrew(run=run), [])

    def test_homebrew_failing_brew_returns_empty(self):
        def run(command, **kwargs):
            raise subprocess.CalledProcessError(1, command)

        self.assertEqual(inventory.homebrew(run=run), [])

    def test_macports_run_failure_returns_empty(self):
        def run(command, **kwargs):
            raise FileNotFoundError(2, "No such file", "port")

        self.assertEqual(inventory.macports(run=run), [])

    def test_macports_without_port_returns_empty(self):
        with patch("shutil.which", return_value=None), patch("os.path.exists", return_value=False):
            self.assertEqual(inventory.macports(), [])

    def test_macports_no_ports_trailer_is_ignored(self):
        class Result:
            returncode = 0
            stdout = "The following ports are currently installed:\n  wget @1.25_0 (active)\nNo ports are installed.\n"

        def run(command, **kwargs):
            return Result()

        rows = inventory.macports(run=run)
        self.assertEqual([row["name"] for row in rows], ["wget"])

    def test_fink_without_fink_returns_empty(self):
        with patch("shutil.which", return_value=None):
            self.assertEqual(inventory.fink(), [])

    def test_cask_list_name_is_flattened(self):
        class Result:
            returncode = 0
            stdout = json.dumps({"formulae": [], "casks": [{"token": None, "name": ["weird", "cask"], "version": "1"}]})

        def run(command, **kwargs):
            return Result()

        with patch("shutil.which", return_value="/usr/local/bin/brew"):
            rows = inventory.homebrew(run=run)
        self.assertEqual(rows[0]["name"], "weird")


class EnsureBinariesTests(unittest.TestCase):
    def test_fills_unknown_targets_and_caches(self):
        import os
        import tempfile

        bottle = {"formulae": [{"bottle": {"stable": {"files": {"sonoma": {}}}}}]}
        archive = '<a href="wget-1.25_0.darwin_23.x86_64.tbz2">x</a>'
        bindist = "Package: ansible\nFilename: stable/main/binary-darwin-x86_64/ansible.deb\n"
        fetches = []

        def brew_run(command, **kwargs):
            class Result:
                returncode = 0
                stdout = json.dumps(bottle)
            return Result()

        class Response:
            def __init__(self, text):
                self.text = text

            def read(self):
                return self.text.encode()

            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

        def fetch(request):
            fetches.append(request.full_url)
            if "packages.macports.org" in request.full_url:
                return Response(archive)
            return Response(bindist)

        relations = [
            {"source": {}, "target": {"manager": "homebrew", "package_type": "formula", "native_name": "wget"}},
            {"source": {}, "target": {"manager": "homebrew", "package_type": "cask", "native_name": "Docker"}},
            {"source": {}, "target": {"manager": "macports", "package_type": "port", "native_name": "wget"}},
            {"source": {}, "target": {"manager": "fink", "package_type": "package", "native_name": "ansible"}},
            {"source": {}, "target": {"manager": "macports", "package_type": "port", "native_name": "wget",
                                      "binaries": ["darwin_23.x86_64"]}},
        ]
        with tempfile.TemporaryDirectory() as directory:
            cache = os.path.join(directory, "binaries.json")
            ensure_binaries(relations, cache_path=cache, brew_run=brew_run, fetch=fetch)
            targets = [relation["target"] for relation in relations]
            self.assertEqual(targets[0]["binaries"], ["sonoma"])
            self.assertEqual(targets[1]["binaries"], ["any"])
            self.assertEqual(targets[2]["binaries"], ["darwin_23.x86_64"])
            self.assertEqual(targets[3]["binaries"], ["10.14/binary-darwin-x86_64", "10.15/binary-darwin-x86_64"])
            self.assertEqual(targets[4]["binaries"], ["darwin_23.x86_64"])
            before = list(fetches)
            ensure_binaries(relations, cache_path=cache, brew_run=brew_run, fetch=fetch)
            self.assertEqual(fetches, before)

    def test_probe_failures_stay_unknown(self):
        import os
        import tempfile

        def fetch(request):
            raise OSError("network down")

        relations = [
            {"source": {}, "target": {"manager": "macports", "package_type": "port", "native_name": "wget"}},
        ]
        with tempfile.TemporaryDirectory() as directory:
            ensure_binaries(relations, cache_path=os.path.join(directory, "b.json"), fetch=fetch)
        self.assertEqual(relations[0]["target"].get("binaries", []), [])


class PlanCommandTests(unittest.TestCase):
    def test_plan_without_backend_exits_nonzero(self):
        with patch("macpkg_migrate.cli.all_managers", return_value=[]), patch(
            "macpkg_migrate.cli.fetch", side_effect=RuntimeError("no backend")
        ), patch.object(sys, "argv", ["macpkg-migrate", "plan"]):
            with self.assertRaises(SystemExit) as ctx:
                cli.main()
        self.assertEqual(ctx.exception.code, 1)


class VerifyCommandTests(unittest.TestCase):
    def run_verify(self, plan, current):
        with tempfile.TemporaryDirectory() as directory:
            path = f"{directory}/plan.json"
            with open(path, "w") as handle:
                json.dump(plan, handle)
            argv = ["macpkg-migrate", "verify", "--plan", path]
            with patch("macpkg_migrate.cli.all_managers", return_value=current), patch.object(
                sys, "argv", argv
            ):
                output = io.StringIO()
                with redirect_stdout(output):
                    cli.main()
        return json.loads(output.getvalue())

    def test_verify_marks_installed_and_pending(self):
        plan = [
            {
                "members": [installed("wget")],
                "recommendation": {"manager": "macports", "type": "port", "name": "wget"},
                "action": "consolidate",
            },
            {
                "members": [installed("ansible@12")],
                "recommendation": {"manager": "fink", "type": "package", "name": "ansible"},
                "action": "consolidate",
            },
        ]
        current = [{"manager": "macports", "type": "port", "name": "wget", "version": "1.25"}]
        groups = self.run_verify(plan, current)
        self.assertEqual(
            [(group["recommendation"]["name"], group["status"]) for group in groups],
            [("wget", "verified"), ("ansible", "pending")],
        )


if __name__ == "__main__":
    unittest.main()
