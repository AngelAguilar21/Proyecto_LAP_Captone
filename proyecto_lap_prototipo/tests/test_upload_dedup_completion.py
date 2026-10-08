import io,json,sys,tempfile,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from uploads import receive,deduplicate_completed,completed_fingerprint,metadata_path

class CompletedDedupTests(unittest.TestCase):
    def test_duplicate_reuses_completed_upload_and_removes_own_marker(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);body=b'closed video evidence'
            first=receive(root,io.BytesIO(body),len(body),'.mp4')
            self.assertEqual(deduplicate_completed(root,first),first)
            second=receive(root,io.BytesIO(body),len(body),'.mp4')
            self.assertEqual(deduplicate_completed(root,second),first)
            self.assertFalse(second.exists());self.assertFalse(metadata_path(second).exists())
            completed_fingerprint(first,root)

    def test_unverified_index_target_is_not_reused_or_deleted(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);body=b'closed video evidence'
            target=receive(root,io.BytesIO(body),len(body),'.mp4')
            import hashlib
            index=target.parent/'_indice.json'
            index.write_text(json.dumps({hashlib.sha256(body).hexdigest():'../../../foreign.mp4'}))
            self.assertEqual(deduplicate_completed(root,target),target)
            completed_fingerprint(target,root)

if __name__=='__main__':unittest.main()
