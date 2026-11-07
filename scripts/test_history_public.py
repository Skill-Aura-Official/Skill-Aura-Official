import copy
import unittest
from render_history import render, summarize
from history_publish import csv_bytes, semantic_public


class PublicHistoryTests(unittest.TestCase):
    def setUp(self):
        self.data = {
            "account": "Skill-Aura-Official", "snapshot_at": "2026-11-06T12:00:00Z",
            "coverage": {"status": "PARTIAL"},
            "repositories": [
                {"id": 1, "full_name": "Skill-Aura-Official/public", "private": False, "owned": True,
                 "fork": False, "owner": "Skill-Aura-Official", "archived": False, "relationship": "owner", "scanned": True},
                {"id": 2, "full_name": "secret-client/private-project", "private": True, "owned": False,
                 "fork": False, "owner": "secret-client", "archived": False, "relationship": "contributor", "scanned": True}],
            "records": [
                {"repo_id": 1, "type": "commit", "id": "public-sha", "sha": "public-sha", "date": "2025-01-01T00:00:00Z", "branches": ["main"]},
                {"repo_id": 1, "type": "commit", "id": "public-sha", "sha": "public-sha", "date": "2025-01-01T00:00:00Z", "branches": ["feature"]},
                {"repo_id": 2, "type": "commit", "id": "secret-sha", "sha": "secret-sha", "date": "2026-01-01T00:00:00Z", "branches": ["secret-branch"], "title": "=1+1"},
                {"repo_id": 2, "type": "pr", "id": 4, "date": "2026-01-01T00:00:00Z", "title": "secret-title"}],
        }

    def test_no_private_identifiers_in_public_markdown(self):
        readme, directory = render(self.data)
        for secret in ("secret-client", "private-project", "secret-sha", "secret-branch", "secret-title"):
            self.assertNotIn(secret, readme + directory)
        self.assertIn("| Commits | 1 | 1 |", readme)
        self.assertIn("| PRs opened | 0 | 1 |", readme)
        self.assertIn("2025", readme)
        self.assertIn("2026", readme)

    def test_sha_dedup_and_year_reconciliation(self):
        _, totals, years, _ = summarize(self.data)
        self.assertEqual(totals["public", "commit"], 1)
        for key, count in totals.items():
            self.assertEqual(sum(year[key] for year in years.values()), count)

    def test_public_preferred_across_private_fork(self):
        self.data["records"][-2]["sha"] = "public-sha"
        _, counts, _, _ = summarize(self.data)
        self.assertEqual(counts["public", "commit"], 1)
        self.assertEqual(counts["private", "commit"], 0)

    def test_inaccessible_private_counts_are_unknown(self):
        self.data["repositories"][1]["scanned"] = False
        readme, _ = render(self.data)
        self.assertIn("Unavailable", readme)
        self.assertIn("| Commits | 1 | Unknown |", readme)

    def test_export_escapes_formula_but_preserves_records(self):
        exported = csv_bytes(self.data).decode("utf-8-sig")
        self.assertIn("'=1+1", exported)
        self.assertIn("secret-sha", exported)

    def test_timestamp_only_refresh_is_not_public_data_change(self):
        changed = copy.deepcopy(self.data)
        changed["snapshot_at"] = "2026-11-06T12:15:00Z"
        self.assertEqual(semantic_public(self.data), semantic_public(changed))

    def test_lost_coverage_requires_public_display_update(self):
        changed = copy.deepcopy(self.data)
        changed["repositories"][1]["scanned"] = False
        self.assertNotEqual(semantic_public(self.data), semantic_public(changed))


if __name__ == "__main__":
    unittest.main()
