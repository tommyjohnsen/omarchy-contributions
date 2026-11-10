"""Flag-faithful SecretService fixtures; no real keyring or credential access."""
import sys,types,unittest
from unittest.mock import patch
from immich_files import keyring_key
class KeyringTests(unittest.TestCase):
 def lookup(self,items):
  flags_seen=[]
  def search(schema,attrs,flags,cancel):flags_seen.append(flags);return items if flags & 2 else items[:1]
  secret=types.SimpleNamespace(Schema=types.SimpleNamespace(new=lambda *a:object()),SchemaFlags=types.SimpleNamespace(NONE=0),SchemaAttributeType=types.SimpleNamespace(STRING=0),Service=types.SimpleNamespace(get_sync=lambda *a:types.SimpleNamespace(search_sync=search)),ServiceFlags=types.SimpleNamespace(OPEN_SESSION=1),SearchFlags=types.SimpleNamespace(NONE=0,ALL=2))
  gi=types.ModuleType('gi');gi.require_version=lambda *a:None
  repo=types.ModuleType('gi.repository');repo.Secret=secret
  with patch.dict(sys.modules,{'gi':gi,'gi.repository':repo}):value=keyring_key()
  return value,flags_seen
 def item(self):return types.SimpleNamespace(get_locked=lambda:False,load_secret_sync=lambda _:True,get_secret=lambda:types.SimpleNamespace(get_text=lambda:'public-fixture-key'))
 def test_all_flag_exposes_duplicate_records_and_refuses_to_select_one(self):
  with self.assertRaises(RuntimeError):self.lookup([self.item(),self.item()])
 def test_single_matching_item_is_available(self):self.assertEqual(self.lookup([self.item()])[0],'public-fixture-key')
 def test_locked_key_is_not_reported_as_absent(self):
  item=self.item();item.get_locked=lambda:True
  with self.assertRaises(RuntimeError):self.lookup([item])
 def test_absent_key_remains_distinct(self):self.assertIsNone(self.lookup([])[0])
 def test_failed_secret_load_does_not_look_absent(self):
  item=self.item();item.load_secret_sync=lambda _:False
  with self.assertRaises(RuntimeError):self.lookup([item])
 def test_existing_item_without_secret_does_not_look_absent(self):
  item=self.item();item.get_secret=lambda:None
  with self.assertRaises(RuntimeError):self.lookup([item])
if __name__=='__main__':unittest.main()
