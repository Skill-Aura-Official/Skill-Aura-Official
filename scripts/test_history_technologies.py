import unittest
from unittest.mock import patch

from history import Failure
from technologies import collect, inspect_repo, public_rows, REVISION


class TechnologyTests(unittest.TestCase):
    def setUp(self):
        self.repo = {
            "id": 1, "full_name": "private-owner/private-project", "archived": False,
            "default_branch": "main", "branch_heads": {"main": "source-sha"},
        }

    def test_source_beats_declared_dependencies_and_copied_examples(self):
        files = {
            "package.json": '{"dependencies":{"vue":"0.1"},"scripts":{"build":"vite build"}}',
            "package-lock.json": '{"packages":{"node_modules/vue":{}}}',
            "frontend/main.jsx": "import React from 'react';\n",
            "backend/main.py": "from fastapi import FastAPI\nimport sqlite3\n",
            "examples/demo.ts": "import { createApp } from 'vue';\n",
            ".env": "private-config",
        }

        class Api:
            def request(self, route, params=None):
                if route.endswith("/languages"):
                    return {"JavaScript": 100, "Python": 120, "TypeScript": 30}
                return {"tree": [{"path": path, "type": "blob", "size": len(value), "sha": "blob"}
                                 for path, value in files.items()]}

            def graph(self, query, **variables):
                return {"repository": {
                    key: {"isBinary": False, "text": files[value.split(":", 1)[1]]}
                    for key, value in variables.items() if key.startswith("file")
                }}

        evidence = inspect_repo(Api(), self.repo, "source-sha")
        self.assertEqual(set(evidence["technology_paths"]), {"FastAPI", "JavaScript", "Python", "React", "SQLite", "Vite"})
        self.assertEqual(evidence["manifest_candidates"]["package.json"], ["vue"])
        self.assertEqual(evidence["lockfiles"], {"package-lock.json": "blob"})

    def test_unavailable_sources_keep_last_known_evidence(self):
        previous = {"revision": REVISION, "repositories": {
            "1": {"status": "VERIFIED", "commit": "old", "technology_paths": {"React": ["private-path"]}}
        }}
        with patch("technologies.inspect_repo", side_effect=Failure(403, "private source")):
            result = collect([(self.repo, object())], previous)
        self.assertEqual(result["repositories"]["1"]["status"], "UNKNOWN")
        self.assertEqual(result["repositories"]["1"]["technology_paths"], {"React": ["private-path"]})

    def test_public_badges_are_allowlisted_and_archived_deduplicated(self):
        evidence = {"repositories": {
            "1": {"status": "VERIFIED", "technology_paths": {"React": ["private-path"], "private-project": ["private-id"]}},
            "2": {"status": "VERIFIED", "archived": True, "technology_paths": {"React": ["another"], "Flask": ["old"]}},
        }}
        public = "\n".join(public_rows(evidence))
        self.assertEqual(public.count("`React`"), 1)
        self.assertIn("`Flask`", public)
        self.assertIn("archived projects", public)
        self.assertNotIn("private-", public)
