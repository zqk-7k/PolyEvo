"""Check that the original main entry really consumes a semantic graph cache."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from .test_semantic_contract import fixture

CODE=Path(__file__).resolve().parents[1]


class MainSemanticManifestTests(unittest.TestCase):
    def test_main_integrates_semantic_graph_and_rejects_cohort_changes(self):
        with tempfile.TemporaryDirectory(prefix='polymer_main_semantic_') as folder:
            root=Path(folder)
            pdfs=root/'pdfs';pdfs.mkdir()
            ref='reference_no_1234567'
            (pdfs/(ref+'.pdf')).write_bytes(b'%PDF-1.4\n%%EOF\n')
            def write(name,value):
                p=root/name;p.write_text(json.dumps(value),encoding='utf-8')
                return dict(path=str(p),sha256=hashlib.sha256(p.read_bytes()).hexdigest())
            graph,source,proposals,native=fixture()
            graph['reference_no']=ref
            sw=write('source.json',source)
            nw=write('native.json',native)
            graph['source_document_sha256']=sw['sha256']
            proposals['native_property_source_sha256']=nw['sha256']
            manifest=write('manifest.json',dict(papers=[dict(reference_no=ref,native_final=nw,stage0=sw,
                semantic=dict(graph=write('graph.json',graph),source_packet=sw,
                    native_proposals=write('proposal.json',proposals)))]))
            command=[sys.executable,'-X','utf8',str(CODE/'pipeline_runner.py'),'--input-dir',str(pdfs),
                '--process-recovery-only','--process-recovery-output',str(root/'out'),
                '--process-recovery-manifest',manifest['path']]
            r=subprocess.run(command,text=True,encoding='utf-8',capture_output=True)
            self.assertEqual(r.returncode,0,r.stdout+r.stderr)
            result=json.loads((root/'out'/'papers'/ref/'prediction.json').read_text(encoding='utf-8'))
            self.assertEqual(result['active_primary_process_graph'],'source_semantic_graph')
            self.assertEqual(result['source_semantic_graph'],graph)
            self.assertEqual(hashlib.sha256(Path(nw['path']).read_bytes()).hexdigest(),nw['sha256'])
            # A manifest selecting a different paper cannot be relabelled as this cohort.
            bad=json.loads(Path(manifest['path']).read_text(encoding='utf-8'))
            bad['papers'][0]['reference_no']='reference_no_7654321'
            write('bad_manifest.json',bad)
            command[-1]=str(root/'bad_manifest.json')
            command[command.index('--process-recovery-output')+1]=str(root/'bad_out')
            r=subprocess.run(command,text=True,encoding='utf-8',capture_output=True)
            self.assertNotEqual(r.returncode,0)
            self.assertIn('必须与所选论文完全一致',r.stdout+r.stderr)
            self.assertFalse((root/'bad_out').exists())


if __name__=='__main__':
    unittest.main()
