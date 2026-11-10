"""Targeted transport checks against pinned official Immich v3.3.5 contract excerpts."""
from pathlib import Path
import json,re,subprocess,unittest
from immich_files import API,asset_id
A='11111111-1111-4111-8111-111111111111'
contract=json.loads(Path(__file__).with_name('openapi-v3.3.5-excerpt.json').read_text())
resolved=json.loads(Path(__file__).with_name('openapi-v3.3.5-filter-schemas.json').read_text())
class ContractTests(unittest.TestCase):
 def test_real_search_transport_uses_versioned_filter_cursor_contract(self):
  captured=[]
  def runner(args,**kwargs):
   lines=kwargs['input'].decode().splitlines()
   data=next(line.split(' = ',1)[1] for line in lines if line.startswith('data = '))
   captured.append(json.loads(json.loads(data)))
   result={'assets':{'items':[{'id':A}],'nextCursor':'fixture-next','nextPage':None}}
   return subprocess.CompletedProcess(args,0,b'HTTP/1.1 200 OK\r\n\r\n'+json.dumps(result).encode(),b'')
  api=API('public-fixture-key',runner)
  for filters in [{'visibility':{'eq':'timeline'}},{'isFavorite':{'eq':True},'visibility':{'eq':'timeline'}},{'albumIds':{'any':[A]}}]:
   with self.subTest(filters=filters):
    rows,cursor=api.search(filters,'fixture-input')
    self.assertEqual(cursor,'fixture-next');self.assertEqual(rows[0]['id'],A)
    body=captured[-1]
    self.assertFalse(set(body)-set(contract['request']['properties']))
    self.assertFalse(set(body['filter'])-set(contract['request']['filterProperties']))
    self.assertEqual(body['filter'],filters);self.assertEqual(body['cursor'],'fixture-input')
    self.assertIn(body['orderBy']['field'],resolved['SearchOrderField']['enum'])
    self.assertIn(body['orderBy']['direction'],resolved['AssetOrder']['enum'])
    self.assertGreaterEqual(body['size'],contract['request']['properties']['size']['minimum'])
    self.assertLessEqual(body['size'],contract['request']['properties']['size']['maximum'])
 def test_v4_id_restriction_matches_target_spec_not_old_review_recollection(self):
  self.assertEqual(asset_id(A),A)
  for name in ['assetId','albumId']:
   pattern=contract['response'][name]['pattern']
   self.assertRegex(A,pattern)
   self.assertIsNone(re.fullmatch(pattern,A.replace('-4111-','-7111-')))
  with self.assertRaises(ValueError):asset_id(A.replace('-4111-','-7111-'))
if __name__=='__main__':unittest.main()
