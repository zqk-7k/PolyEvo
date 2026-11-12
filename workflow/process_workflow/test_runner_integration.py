"""Check the actual main-workflow hook, immutable inputs and frozen execution."""
import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

CODE = Path(__file__).resolve().parents[1]


class RunnerIntegration(unittest.TestCase):
    def test_generic_runner_consumes_a_source_semantic_graph(self):
        from .test_semantic_contract import fixture
        with tempfile.TemporaryDirectory(prefix='polymer_semantic_workflow_') as folder:
            root = Path(folder)
            graph, source, proposals, native = fixture()
            def write(name, value):
                path = root / name
                path.write_text(json.dumps(value, ensure_ascii=False), encoding='utf-8')
                return dict(path=str(path), sha256=hashlib.sha256(path.read_bytes()).hexdigest())
            native_witness = write('native.json', native)
            source_witness = write('stage0.json', source)
            packet_witness = write('source_packet.json', source)
            graph['source_document_sha256'] = packet_witness['sha256']
            proposals['native_property_source_sha256'] = native_witness['sha256']
            manifest = write('manifest.json', dict(papers=[dict(reference_no='synthetic',
                native_final=native_witness, stage0=source_witness,
                semantic=dict(graph=write('semantic_graph.json', graph), source_packet=packet_witness,
                    native_proposals=write('native_proposals.json', proposals)))]))
            output = root / 'out'
            finished = subprocess.run([sys.executable, '-X', 'utf8', str(CODE / 'process_workflow_runner.py'),
                '--manifest', manifest['path'], '--output', str(output)],
                text=True, encoding='utf-8', capture_output=True)
            self.assertEqual(finished.returncode, 0, finished.stdout + finished.stderr)
            result = json.loads((output / 'papers/synthetic/prediction.json').read_text(encoding='utf-8'))
            self.assertEqual(result['active_primary_process_graph'], 'source_semantic_graph')
            self.assertEqual(result['source_semantic_graph'], graph)
            self.assertEqual(result['counts']['semantic_operations'], 1)
            self.assertTrue(result['native_process_context_retained_as_revision_lineage_not_second_active_graph'])
            self.assertTrue(result['complete_semantic_source_support_not_certified_by_structural_validation'])
            self.assertEqual(hashlib.sha256(Path(native_witness['path']).read_bytes()).hexdigest(), native_witness['sha256'])

    def test_main_hook_is_offline_and_runtime_hash_is_enforced(self):
        with tempfile.TemporaryDirectory(prefix='polymer_process_workflow_') as folder:
            root = Path(folder)
            pdfs = root / 'pdfs'
            cache = root / 'cache/reference_no_1234567'
            pdfs.mkdir()
            cache.mkdir(parents=True)
            (pdfs / 'reference_no_1234567.pdf').write_bytes(b'%PDF-1.4\n%%EOF\n')
            doc = dict(samples=[dict(sample_id='sample', state_description='dry powder')],
                process_steps=[], property_series=[], evidence=[])
            (cache / 'final.json').write_text(json.dumps(doc), encoding='utf-8')
            (cache / 'stage0_blocks.json').write_text(json.dumps(dict(elements=[])), encoding='utf-8')
            before = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in cache.iterdir()}
            output = root / 'recovery'
            command = [sys.executable, '-X', 'utf8', str(CODE / 'pipeline_runner.py'), '--input-dir', str(pdfs),
                '--process-cache-root', str(cache.parent), '--process-recovery-output', str(output),
                '--process-recovery-only']
            finished = subprocess.run(command, text=True, encoding='utf-8', capture_output=True)
            self.assertEqual(finished.returncode, 0, finished.stdout + finished.stderr)
            summary = json.loads((output / 'execution_summary.json').read_text(encoding='utf-8'))
            self.assertEqual((summary['completed'], summary['failed'], summary['external_api_calls']), (1, 0, 0))
            after = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in cache.iterdir()}
            self.assertEqual(before, after)
            access = json.loads((output / 'process_access_log.json').read_text(encoding='utf-8'))
            self.assertEqual(access['denied_attempts'], [])
            self.assertFalse(access['os_hard_isolation'])
            self.assertFalse([p for p in access['accesses'] if p.lower().endswith('.env')])
            # A modified frozen runtime must fail before accepting/resuming an output.
            frozen_core = output / 'runtime/process_workflow/core.py'
            frozen_core.write_bytes(frozen_core.read_bytes() + b'\n# tampered fixture\n')
            retry = subprocess.run([sys.executable, '-X', 'utf8', str(CODE / 'process_workflow_runner.py'),
                '--manifest', str(root / 'recovery_input_manifest.json'), '--output', str(output), '--resume'],
                text=True, encoding='utf-8', capture_output=True)
            self.assertNotEqual(retry.returncode, 0)
            self.assertIn('Frozen runtime changed', retry.stdout + retry.stderr)


if __name__ == '__main__':
    unittest.main()
