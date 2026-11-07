import copy
import unittest
from unittest.mock import patch
from render_history import render, summarize, artwork, INTRODUCTION, CLOSED_SOURCE
from history_publish import csv_bytes, semantic_public, semantic_private, Publisher, PROFILE, ACCOUNT, IDENTITY_COMMIT, AUTOMATION_COMMIT, AUTOMATION_ACCOUNT, STATE_MARKER


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
        all_images="".join(value.decode() for value in artwork(self.data).values())
        for secret in ("secret-client", "private-project", "secret-sha", "secret-branch", "secret-title"):
            self.assertNotIn(secret, readme + directory + all_images)
        self.assertIn("| Commits | 1 | 1 |", readme)
        self.assertIn("| PRs opened | 0 | 1 |", readme)
        self.assertIn("2025", readme)
        self.assertIn("2026", readme)

    def test_generated_identity_comes_from_linked_automation_and_actor_is_checked(self):
        human={"author":{"login":ACCOUNT},"committer":{"login":ACCOUNT}}
        machine={"author":{"login":AUTOMATION_ACCOUNT},"committer":{"login":AUTOMATION_ACCOUNT},
                 "commit":{"author":{"name":"verified automation","email":"existing-public-bot-address"}}}
        def response(route):
            return {"user":{"login":ACCOUNT},
                    "repos/"+PROFILE+"/commits/"+IDENTITY_COMMIT:human,
                    "repos/"+PROFILE+"/commits/"+AUTOMATION_COMMIT:machine,
                    "user/repos?per_page=100&page=1":[{"private":True,"owner":{"login":ACCOUNT},"description":STATE_MARKER,"full_name":"owner/private-state"}]}[route]
        with patch.object(Publisher,"api",side_effect=response):
            publisher=Publisher("test")
        self.assertEqual(publisher.identity,machine["commit"]["author"])
        with patch.object(Publisher,"api",return_value={"login":"wrong-account"}):
            with self.assertRaises(ValueError):
                Publisher("test")

    def test_introduction_reflects_multiple_work_areas(self):
        readme, _ = render(self.data)
        self.assertIn("### Work at a glance", readme)
        self.assertTrue(60 <= len(INTRODUCTION.split()) <= 100)
        self.assertIn(INTRODUCTION, readme)

    def test_closed_source_cards_are_explicit_approved_copy(self):
        self.data["repositories"][1]["description"] = "PRIVATE CUSTOMER DESCRIPTION"
        self.data["repositories"][1]["html_url"] = "https://github.com/secret-client/private-project"
        readme, directory = render(self.data)
        section = readme.split("## Private / Closed-source Projects", 1)[1].split("## Complete public projects", 1)[0]
        self.assertEqual(len(CLOSED_SOURCE), 10)
        self.assertEqual(len([line for line in section.splitlines() if line.startswith("- **")]), 10)
        for name, summary, attribution, url in CLOSED_SOURCE:
            self.assertIn(name, section)
            self.assertIn(summary, section)
            self.assertIn(attribution, section)
            if url:
                self.assertIn(url, section)
        for private in ("PRIVATE CUSTOMER DESCRIPTION", "secret-client/private-project"):
            self.assertNotIn(private, readme + directory)

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
        changed["repositories"][0]["last_success_at"] = changed["snapshot_at"]
        changed["repositories"][0]["branch_heads"] = {"main": "new-tip"}
        changed["repositories"][0]["source_coverage"] = {"issues": {"status": "SCANNED", "to": changed["snapshot_at"]}}
        self.assertEqual(semantic_public(self.data), semantic_public(changed))

    def test_lost_coverage_requires_public_display_update(self):
        changed = copy.deepcopy(self.data)
        changed["repositories"][1]["scanned"] = False
        self.assertNotEqual(semantic_public(self.data), semantic_public(changed))

    def test_private_timestamp_refresh_does_not_create_checkpoint(self):
        original = copy.deepcopy(self.data)
        original["coverage"]["mode"] = "full"
        original["coverage"]["sources"] = [{"source": "affiliation", "to": original["snapshot_at"]}]
        original["repositories"][0]["source_coverage"] = {"issues": {"status": "SCANNED", "to": original["snapshot_at"]}}
        refreshed = copy.deepcopy(original)
        refreshed["snapshot_at"] = "2026-11-06T12:15:00Z"
        refreshed["coverage"]["mode"] = "incremental"
        refreshed["coverage"]["sources"][0]["to"] = refreshed["snapshot_at"]
        refreshed["repositories"][0]["source_coverage"]["issues"]["to"] = refreshed["snapshot_at"]
        self.assertEqual(semantic_private(original), semantic_private(refreshed))
        refreshed["repositories"][0]["source_coverage"]["issues"]["status"] = "UNKNOWN"
        self.assertNotEqual(semantic_private(original), semantic_private(refreshed))


if __name__ == "__main__":
    unittest.main()
