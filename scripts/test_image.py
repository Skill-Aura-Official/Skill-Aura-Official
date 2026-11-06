import datetime as dt
import unittest
from unittest.mock import patch
from activity import refresh, UTC
from activity_image import render
import publish_activity as pub
from test_activity import API


class ImageTests(unittest.TestCase):
    def setUp(self):
        self.state=refresh([API()],True,None,dt.datetime(2026,11,6,10,tzinfo=UTC))

    def test_pixels_encode_counts_and_source_timestamp(self):
        first=render(self.state)
        self.assertEqual(first.size,(1038,480))
        self.assertEqual(first.tobytes(),render(self.state).tobytes())
        self.state["days"]["2026-11-06"]["private"]["commits"]+=1
        second=render(self.state)
        self.assertNotEqual(first.tobytes(),second.tobytes())
        self.state["as_of"]="2026-11-06T10:01:00Z"
        self.assertNotEqual(second.tobytes(),render(self.state).tobytes())

    def test_unavailable_and_forbidden_public_fields(self):
        self.state["coverage"]="PRIVATE_UNKNOWN"
        for rows in self.state["days"].values():
            rows["private"]=dict.fromkeys(rows["private"])
        render(self.state)
        self.state["repository"]="private/project"
        with self.assertRaises(Exception):
            render(self.state)

    def test_only_inactive_slot_is_staged(self):
        releases=[{"id":i+1,"tag_name":tag,"body":pub.MARKER} for i,tag in enumerate(pub.SLOTS)]
        self.assertEqual(pub.choose_slot(releases,1)[1]["id"],2)
        self.assertEqual(pub.choose_slot(releases,2)[1]["id"],1)
        with self.assertRaises(RuntimeError):
            pub.choose_slot([{"tag_name":"software-release","id":7,"body":"release"}],7)
        with self.assertRaises(RuntimeError):
            pub.choose_slot(releases,5)
        releases[1]["immutable"]=True
        with self.assertRaises(RuntimeError):
            pub.choose_slot(releases,1)

    def test_display_failure_restores_prior_slot(self):
        releases=[{"id":i+1,"tag_name":tag,"body":pub.MARKER,"assets":[]} for i,tag in enumerate(pub.SLOTS)]
        calls=[]
        def endpoint(path,token,method="GET",body=None):
            if path.startswith("releases?"):
                return releases
            if path=="releases/latest":
                return releases[min(len(calls),1)]
            calls.append((path,method,body))
        import hashlib, io, json
        image=io.BytesIO()
        render(self.state).save(image,format="PNG")
        data=image.getvalue()
        asset={"id":55,"state":"uploaded","size":len(data),"digest":"sha256:"+hashlib.sha256(data).hexdigest()}
        with patch.object(pub,"endpoint",side_effect=endpoint), patch.object(pub,"request",side_effect=[json.dumps(asset).encode(),data]), patch.object(pub,"confirm_visitor",side_effect=RuntimeError):
            with self.assertRaises(RuntimeError):
                pub.publish(self.state,"unused","revision")
        self.assertEqual(calls[-1],("releases/1","PATCH",{"make_latest":"true"}))
