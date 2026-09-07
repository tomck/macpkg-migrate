import unittest
import json
from macpkg_migrate.catalog import fetch
from macpkg_migrate.planner import make_plan

class TestPlanner(unittest.TestCase):
    def test_queries_shared_macpkgmap_backend(self):
        class Result:
            returncode=0; stdout=json.dumps({"catalog_version":"fixture-v1","results":[{"source":{"manager":"homebrew","package_type":"formula","native_name":"ansible@12"},"target":{"manager":"fink","package_type":"package","native_name":"ansible"},"confidence":1.0,"review_status":"automatic"}]})
        calls=[]
        def run(command,**kwargs): calls.append(command); return Result()
        result=fetch([{"manager":"homebrew","type":"formula","name":"ansible@12"}],run=run)
        self.assertEqual(result[0]["target"]["native_name"],"ansible")
        self.assertEqual(result[0]["catalog_version"],"fixture-v1")
        self.assertIn("macpkgmap",calls[0])

    def test_prefers_available_fink_version_when_requested(self):
        installed=[{"manager":"homebrew","type":"formula","name":"ansible@12"}]
        relations=[
            {"source":{"manager":"homebrew","package_type":"formula","native_name":"ansible@12"},"target":{"manager":"macports","package_type":"port","native_name":"py313-ansible"},"confidence":.78,"review_status":"needs-review","matching_method":"version-family"},
            {"source":{"manager":"homebrew","package_type":"formula","native_name":"ansible@12"},"target":{"manager":"fink","package_type":"package","native_name":"ansible"},"confidence":1.0,"review_status":"automatic","matching_method":"curated"},
        ]
        row=make_plan(installed,relations,("fink","macports","homebrew"))[0]
        self.assertEqual(row["recommendation"]["manager"],"fink")
