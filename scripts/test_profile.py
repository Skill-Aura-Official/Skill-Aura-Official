import unittest
from unittest.mock import patch
import public_profile as p

class PublicOnly(unittest.TestCase):
    def test_private_row_rejected(self):
        row={"private":True}
        with patch.object(p,"get",side_effect=[{"public_repos":1},[row]]):
            with self.assertRaises(ValueError):
                p.collect()

    def test_truncated_inventory_rejected(self):
        with patch.object(p,"get",side_effect=[{"public_repos":1},[]]):
            with self.assertRaises(ValueError):
                p.collect()

    def test_api_failure_preserves_readme(self):
        before=(p.ROOT/"README.md").read_bytes()
        with patch.object(p,"get",side_effect=TimeoutError):
            with self.assertRaises(TimeoutError):
                p.render()
        self.assertEqual(before,(p.ROOT/"README.md").read_bytes())
