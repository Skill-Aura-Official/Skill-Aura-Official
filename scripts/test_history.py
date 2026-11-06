import datetime as dt
import unittest
from unittest.mock import Mock, patch, MagicMock
from http.client import RemoteDisconnected
import io
import history as h


class HistoryTests(unittest.TestCase):
    def test_scoped_search_exhausts_both_types_without_mixed_query(self):
        searches=list(h.typed_searches())
        self.assertEqual(len(searches),5)
        for actor in ("author","commenter"):
            self.assertEqual({q.split()[-1] for q,_ in searches if q.startswith(actor+":")},{"is:issue","is:pr"})
        self.assertTrue(all(" is:" in q for q,_ in searches))

    def test_private_route_cannot_be_exposed_by_public_error(self):
        self.assertEqual(h.operation("repos/sensitive-owner/customer-project/pulls/47/reviews"),"review inventory")
        self.assertNotIn("private",h.operation("unexpected/private/customer"))

    def test_remote_disconnect_retries_without_exposing_request(self):
        response=MagicMock()
        response.__enter__.return_value=io.BytesIO(b'{"ok":true}')
        with patch.object(h,"urlopen",side_effect=[RemoteDisconnected(),response]) as opener, patch.object(h.time,"sleep"):
            self.assertEqual(h.GitHub("test").request("user"),{"ok":True})
            self.assertEqual(opener.call_count,2)

    def test_rest_pages_and_gql_cursors(self):
        api=h.GitHub("unused")
        api.request=Mock(side_effect=[list(range(100)),[100]])
        self.assertEqual(list(api.pages("irrelevant")),list(range(101)))
        self.assertEqual(api.request.call_args_list[1].args[1]["page"],2)
        def fetch(cursor):
            return ({"nodes":[1],"pageInfo":{"hasNextPage":True,"endCursor":"x"}} if cursor is None
                    else {"nodes":[2],"pageInfo":{"hasNextPage":False,"endCursor":None}})
        self.assertEqual(list(h.connection(fetch)),[1,2])

    def test_search_splits_cap_and_deduplicates_across_page_boundaries(self):
        client=Mock()
        client.request.side_effect=[
            {"total_count":1001,"incomplete_results":False,"items":[]},
            {"total_count":101,"incomplete_results":False,"items":[{"id":i} for i in range(100)]},
            {"total_count":101,"incomplete_results":False,"items":[{"id":100}]},
            {"total_count":1,"incomplete_results":False,"items":[{"id":101}]},
        ]
        start=dt.datetime(2025,1,1,tzinfo=h.UTC)
        result=list(h.search(client,"issues","author:example","created",start,start+dt.timedelta(days=1)))
        self.assertEqual(len(result),102)
        self.assertEqual(client.request.call_count,4)

    def test_linked_coauthor_across_visible_refs_and_no_display_name_guess(self):
        repo={"id":2,"node_id":"repo","default_branch":"main","full_name":"public/example"}
        api=Mock()
        api.pages.return_value=[{"name":"main","commit":{"sha":"01"}},{"name":"work","commit":{"sha":"01"}}]
        row={"oid":"01","authors":{"nodes":[{"user":{"login":h.OWNER}}],"pageInfo":{"hasNextPage":False}},
             "author":{"user":{"login":"someone-else"}},"committer":{"user":{"login":"someone-else"}},
             "messageHeadline":"regular","messageBody":"","parents":{"totalCount":1},"url":"https://github.com/example",
             "authoredDate":"2025-07-08T03:00:00Z","committedDate":"2025-07-08T04:00:00Z"}
        api.graph.return_value={"node":{"object":{"history":{"nodes":[row],"pageInfo":{"hasNextPage":False}}}}}
        rows,tips=h.commits(api,repo,[],{},True)
        self.assertEqual(rows[0]["role"],"coauthored")
        self.assertEqual(rows[0]["branches"],["main","work"])
        again,_=h.commits(api,repo,rows,tips,False)
        self.assertEqual(rows,again)
        self.assertEqual(api.graph.call_count,1)
        row["authors"]["nodes"]=[{"user":None,"name":"Jatin dalal","email":"unverified"}]
        self.assertIsNone(h.commit_role(api,repo,row))

    def test_unknown_cursor_and_partial_source_fail_closed(self):
        with self.assertRaises(h.Failure):
            list(h.connection(lambda p:{"nodes":[],"pageInfo":{"endCursor":"repeat","hasNextPage":True}}))
        api=Mock()
        api.pages.side_effect=h.Failure(403,"API")
        with self.assertRaises(h.Failure):
            h.repo_events(api,{"full_name":"scope/name","has_discussions":False},"2025-01-01","2027-01-01",
                          {"issues":{"status":"SCANNED"}})

    def test_profile_automation_requires_identity_trailer_and_safe_paths(self):
        repo={"full_name":h.PROFILE}
        item={"oid":"one","messageHeadline":"Automated profile inventory snapshot","messageBody":"Automation: profile-history"}
        api=Mock()
        api.request.return_value={"files":[{"filename":"README.md"},{"filename":"assets/history-signature.txt"}]}
        self.assertTrue(h.profile_automation(api,repo,item))
        api.request.return_value={"files":[{"filename":"src/product.py"}]}
        self.assertFalse(h.profile_automation(api,repo,item))
        self.assertFalse(h.profile_automation(api,{"full_name":"unrelated/repository"},item))

    def test_internal_visibility_never_becomes_public(self):
        raw={"id":1,"node_id":"a","owner":{"login":"scope","type":"Organization"},"full_name":"scope/internal",
             "private":False,"visibility":"internal","html_url":"private","default_branch":"main","archived":False,
             "fork":False,"created_at":"2025-01-01T00:00:00Z"}
        self.assertTrue(h.repo_meta(raw)["private"])
