import datetime as dt
import json
import unittest
from unittest.mock import patch
import activity as a


class API:
    def __init__(self):
        self.hidden = {"id": 275, "full_name":"confidential-customer/secret-project", "private":True,"pushed_at":"2026-11-06"}
        self.public = {"id": 122, "full_name":"example/demo", "private":False,"pushed_at":"2026-11-06"}
        self.me = {"login":a.OWNER, "type":"User"}

    def get(self,path,params=None):
        if path == "user":
            return self.me
        return {"incomplete_results":False,"items":[],"total_count":0}

    def pages(self,path,params=None):
        if path == "user/repos":
            return [self.hidden,self.hidden,self.public]
        if path.endswith("/branches"):
            return [{"commit":{"sha":"branch-one"}},{"commit":{"sha":"branch-two"}}]
        if path.endswith("/commits"):
            row = {"author":self.me,"committer":self.me,"parents":[{}],"commit":{"message":"ordinary change","committer":{"date":"2026-11-06T00:10:00Z"}}}
            rows=[dict(row,sha="overlap"),dict(row,sha="merge",parents=[{},{}]),dict(row,sha="bot",committer={"type":"Bot"}),
                  dict(row,sha="other",author={"login":"other","type":"User"})]
            if self.hidden["full_name"] in path:
                rows.append(dict(row,sha="private-only"))
            return rows
        raise AssertionError("Unexpected request")


class ActivityTests(unittest.TestCase):
    def setUp(self):
        self.now = dt.datetime(2026,11,6,10,tzinfo=a.UTC)

    def test_dedup_privacy_and_overlap(self):
        api=API()
        state=a.refresh([api],True,None,self.now)
        for scope in a.SCOPES:
            self.assertEqual(state["days"]["2026-11-06"][scope]["commits"],1)
        for private_string in ("confidential","secret-project","branch-one","overlap","private-only"):
            self.assertNotIn(private_string,json.dumps(state) + a.summary(state))
        self.assertEqual(a.refresh([api], True, state, self.now),state)
        state["days"]["2026-11-06"]["private"]["name"]="confidential"
        with self.assertRaises(a.Incomplete):
            a.validate(state)

    def test_empty_and_revoked_private_coverage(self):
        api=API()
        state=a.refresh([api],True,None,self.now)
        with patch.object(a,"inventory",return_value={}):
            with self.assertRaises(a.Incomplete):
                a.refresh([api],True,state,self.now)
            unknown=a.refresh([api],False,None,self.now)
            self.assertIsNone(unknown["days"]["2026-11-06"]["private"]["commits"])

    def test_incomplete_search_rejected(self):
        api=API()
        with patch.object(api,"get",return_value={"incomplete_results":True}):
            with self.assertRaises(a.Incomplete):
                list(a.search(api,"is:issue",self.now.date(),self.now.date(),"created"))

    def test_issue_pr_and_multiple_reviews(self):
        api=API()
        row={"repository_url":"https://api.github.com/repos/example/demo","id":123,"number":2,
             "user":api.me,"created_at":"2026-11-06T00:01:02Z"}
        def page(path,params=None):
            if path.endswith("reviews"):
                return [{"id":number,"user":api.me,"submitted_at":"2026-11-06T02:03:04Z"} for number in [1,2]]
            return []
        with patch.object(api,"pages",side_effect=page), patch.object(a,"search",return_value=[row]):
            events=list(a.collect_events({122:(api.public,api)},[api], self.now.date(),self.now.date(),"2026-11-06T10:00:00Z"))
        self.assertEqual(sorted(e[2] for e in events),["issues","pull_requests","reviews","reviews"])
