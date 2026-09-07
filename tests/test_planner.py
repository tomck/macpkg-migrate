import unittest
from macpkg_migrate.planner import make_plan

class TestPlanner(unittest.TestCase):
    def test_prefers_available_fink_version_when_requested(self):
        installed=[{"manager":"homebrew","type":"formula","name":"ansible@12"}]
        relations=[
            {"source":{"manager":"homebrew","package_type":"formula","native_name":"ansible@12"},"target":{"manager":"macports","package_type":"port","native_name":"py313-ansible"},"confidence":.78,"review_status":"needs-review","matching_method":"version-family"},
            {"source":{"manager":"homebrew","package_type":"formula","native_name":"ansible@12"},"target":{"manager":"fink","package_type":"package","native_name":"ansible"},"confidence":1.0,"review_status":"automatic","matching_method":"curated"},
        ]
        row=make_plan(installed,relations,("fink","macports","homebrew"))[0]
        self.assertEqual(row["recommendation"]["manager"],"fink")
