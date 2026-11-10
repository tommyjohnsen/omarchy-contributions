"""Private-TTY helper fixtures; no real keyring, server, service or file chooser."""
import contextlib,errno,io,sys,tempfile,types,unittest
from pathlib import Path
from unittest.mock import patch
import connect_immich_files as helper
class FakeAPI:
 def __init__(self,key):
  if ' ' in key:raise ValueError('fixture malformed key')
  self.key=key
class HelperTests(unittest.TestCase):
 def run_helper(self,stored,replacement='public-new-fixture-key',failure=errno.EACCES,new_valid=True,mounted=False,stored_valid=False,saved_readback=True,initial_error=None):
  saved=[];prompts=[];validations=[];commands=[]
  def keyring(store=None):
   if store is not None:saved.append(store);return True
   return (saved[-1] if saved_readback else None) if saved else stored
  def validate(api):
   validations.append(api.key)
   if api.key==stored and stored is not None and not stored_valid:raise OSError(failure,'fixture rejected or failed')
   if not new_valid:raise OSError(errno.EACCES,'fixture replacement rejected')
  def prompt(message):prompts.append(message);return replacement
  self.saved,self.prompts,self.validations,self.commands=saved,prompts,validations,commands
  with tempfile.TemporaryDirectory(prefix='immich-helper-fixture-') as d:
   with patch.object(helper.mount_support,'probe_mount',return_value=True),patch.object(sys,'argv',['connect-immich-files']),patch.object(sys,'stdin',types.SimpleNamespace(isatty=lambda:True)),patch.object(helper,'prepare_mountpoint',side_effect=[initial_error or mounted,True]),patch.object(helper,'mount_record',return_value=['fuse','Immich']),patch.object(helper,'MOUNT',Path(d)),patch.object(helper,'keyring_key',keyring),patch.object(helper,'API',FakeAPI),patch.object(helper,'validate',validate),patch.object(helper.getpass,'getpass',prompt),patch.object(helper,'bookmark'),patch.object(helper.subprocess,'run',side_effect=lambda a,**k:commands.append(a)),patch.object(helper.subprocess,'Popen'),contextlib.redirect_stdout(io.StringIO()):
    return helper.main()
 def test_stored_rejected_key_reprompts_validates_then_saves(self):
  self.assertEqual(self.run_helper('public-old-fixture-key'),0)
  self.assertEqual(len(self.prompts),1);self.assertEqual(self.validations,['public-old-fixture-key','public-new-fixture-key']);self.assertEqual(self.saved,['public-new-fixture-key'])
 def test_invalid_replacement_does_not_overwrite_keyring_or_start_service(self):
  with self.assertRaises(OSError):self.run_helper('public-old-fixture-key',new_valid=False)
  self.assertFalse(self.saved);self.assertFalse(self.commands)
 def test_network_failure_does_not_prompt_for_replacement(self):
  with self.assertRaises(OSError):self.run_helper('public-old-fixture-key',failure=errno.ETIMEDOUT)
  self.assertFalse(self.prompts);self.assertFalse(self.saved);self.assertFalse(self.commands)
 def test_fresh_invalid_key_is_not_saved_or_reprompted(self):
  with self.assertRaises(OSError):self.run_helper(None,new_valid=False)
  self.assertEqual(len(self.prompts),1);self.assertFalse(self.saved);self.assertFalse(self.commands)
 def test_active_mount_rejected_key_is_replaced_and_daemon_restarted(self):
  self.assertEqual(self.run_helper('public-old-fixture-key',mounted=True),0)
  self.assertEqual(len(self.prompts),1);self.assertEqual(self.saved,['public-new-fixture-key'])
  self.assertTrue(any(command[2]=='restart' for command in self.commands))
 def test_active_mount_valid_key_does_not_restart_daemon(self):
  self.assertEqual(self.run_helper('public-valid-fixture-key',mounted=True,stored_valid=True),0)
  self.assertFalse(self.prompts);self.assertFalse(self.saved);self.assertFalse(self.commands)
 def test_malformed_stored_key_is_replaced_privately_before_start(self):
  self.assertEqual(self.run_helper('public malformed fixture',mounted=True),0)
  self.assertEqual(len(self.prompts),1);self.assertEqual(self.saved,['public-new-fixture-key'])
  self.assertTrue(any(command[2]=='restart' for command in self.commands))
 def test_failed_saved_key_readback_never_enables_service(self):
  with self.assertRaises(RuntimeError):self.run_helper(None,saved_readback=False)
  self.assertFalse(self.commands)
 def test_failed_unit_budget_is_reset_before_start(self):
  self.assertEqual(self.run_helper(None),0)
  self.assertEqual(self.commands[0][2],'reset-failed')
 def test_disconnected_active_mount_validates_key_then_restarts(self):
  error=helper.mount_support.DisconnectedMountActive('public fixture')
  self.assertEqual(self.run_helper('public-valid-key',stored_valid=True,initial_error=error),0)
  self.assertEqual(self.validations,['public-valid-key']);self.assertFalse(self.prompts)
  self.assertTrue(any(command[2]=='restart' for command in self.commands))
if __name__=='__main__':unittest.main()
