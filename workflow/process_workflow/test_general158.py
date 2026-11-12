"""Failure-focused tests. Synthetic fixtures are not scientific performance tests."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

from . import general158 as g

CODE = Path(__file__).resolve().parents[1]


def raw(value): return json.dumps(value, ensure_ascii=False).encode('utf-8')


def fixture():
    native = dict(samples=[dict(sample_id='A', state_description='wet film; brown film')],
        process_steps=[], property_observations=[dict(sample_id='A', value_raw='7', unit_raw='MPa')])
    source = dict(elements=[dict(block_id='B', type='text', text='A was dried at approximately 80 °C. The dry film was brown.')])
    nb, sb = raw(native), raw(source)
    np = dict(path='native.json', sha256=g.engine.sha(nb)); sp = dict(path='source.json', sha256=g.engine.sha(sb))
    packet = g.engine.prepare(nb, sb, np, sp)
    delta = g.delta_template(packet)
    delta.update(completed=True, source_coverage=dict(read_block_ids=['B'], unread_block_ids=[], all_source_blocks_read=True))
    delta['checklist'] = {key: dict(status='reviewed', reason='Synthetic source inspected; unsupported scope left unknown') for key in g.CHECKLIST}
    return packet, delta


def anchor(packet):
    block = packet['source_document']['elements'][0]
    return dict(block_id='B', block_sha256=g.canonical(block), text_field='text',
        start=0, end=len(block['text']), quote=block['text'])


def node(packet, ident, kind, content, links=()):
    return dict(id=ident, kind=kind, content=content,
        scope={k: ('A' if k == 'subject' else None) for k in g.engine.old.SCOPE},
        scope_null_reasons={k: 'Not asserted by this synthetic source' for k in g.engine.old.SCOPE if k != 'subject'},
        source_anchors=[anchor(packet)], links=list(links))


def correction(packet, delta):
    full = g.engine.template(packet)
    owner = next(o for o in full['owners'] if o['pointer'] == '/samples/0')
    field = next(f for f in owner['fields'] if f['pointer'].endswith('/state_description'))
    owner['fields'] = [field]
    field['segments'][0].update(disposition='corrected', reason='Original wet state conflicts with explicit dry state',
        source_anchors=[anchor(packet)], replacement_ids=['state'], entire_segment_superseded=True)
    delta['native_decisions'] = [owner]
    delta['graph_nodes'] = [node(packet, 'state', 'state', dict(state_raw='dry brown film'))]
    return field


class GeneralRules(unittest.TestCase):
    def test_sparse_transport_keeps_every_unreviewed_field_active(self):
        packet, delta = fixture()
        before = deepcopy(packet['native_document'])
        result = g.compile_prediction(packet, delta)
        rows = list(g.effective_fields(packet, result))
        self.assertTrue(rows)
        self.assertTrue(all(r['active'] and r['status'] == 'active_unknown' for r in rows))
        self.assertEqual(packet['native_document'], before)
        self.assertIsNone(result['five_dimension_metrics'])

    def test_targeted_correction_does_not_retire_other_fields_or_properties(self):
        packet, delta = fixture(); correction(packet, delta)
        result = g.compile_prediction(packet, delta)
        rows = list(g.effective_fields(packet, result))
        self.assertEqual(sum(not r['active'] for r in rows), 1)
        self.assertTrue(all(r['active'] for r in rows if r['field_pointer'].startswith('/property_observations/')))

    def test_property_value_unit_and_sample_binding_cannot_be_superseded(self):
        for terminal in ('value_raw', 'unit_raw', 'sample_id'):
            packet, delta = fixture()
            full = g.engine.template(packet)
            owner = next(o for o in full['owners'] if o['pointer'] == '/property_observations/0')
            field = next(f for f in owner['fields'] if f['pointer'].endswith('/' + terminal))
            owner['fields'] = [field]
            field['segments'][0].update(disposition='corrected', reason='Attempt to rewrite property data through process overlay',
                source_anchors=[anchor(packet)], replacement_ids=['state'], entire_segment_superseded=True)
            delta['native_decisions'] = [owner]
            delta['graph_nodes'] = [node(packet, 'state', 'state', dict(state_raw='dry film'))]
            with self.assertRaisesRegex(ValueError, 'property data and bindings are protected'):
                g.compile_prediction(packet, delta)

    def test_partial_string_partition_preserves_unknown_suffix(self):
        packet, delta = fixture(); field = correction(packet, delta)
        first = field['segments'][0]; first['end'] = 8
        second = deepcopy(first)
        second.update(start=8, end=len('wet film; brown film'), disposition='unresolved',
            reason='Remaining description not adjudicated', replacement_ids=[], source_anchors=[], entire_segment_superseded=False)
        field['segments'] = [first, second]
        rows = list(g.effective_fields(packet, g.compile_prediction(packet, delta)))
        parts = [r for r in rows if r['field_pointer'].endswith('/state_description')]
        self.assertEqual(''.join(r['original_value'] for r in parts), 'wet film; brown film')
        self.assertFalse(parts[0]['active']); self.assertTrue(parts[1]['active'])
        field['segments'] = [first]
        with self.assertRaisesRegex(ValueError, 'suffix'): g.compile_prediction(packet, delta)

    def test_fabricated_source_and_global_withdrawal_fail(self):
        packet, delta = fixture(); field = correction(packet, delta)
        field['segments'][0]['source_anchors'][0]['quote'] = 'fabricated'
        with self.assertRaisesRegex(ValueError, 'substring'): g.compile_prediction(packet, delta)
        packet, delta = fixture(); delta['withdraw_all_prior'] = True
        with self.assertRaisesRegex(ValueError, 'Exact delta'): g.compile_prediction(packet, delta)

    def test_role_and_bound_and_operation_are_required(self):
        packet, delta = fixture()
        delta['graph_nodes'] = [node(packet, 'op', 'operation', dict(operation_raw='dried')),
            node(packet, 'p', 'parameter', dict(name_raw='temperature', value_raw='80', unit_raw='°C',
                parameter_role='processing', relation='approximate', qualifier_raw='approximately'), [dict(role='operation', target_id='op')])]
        result = g.compile_prediction(packet, delta)
        self.assertEqual(result['active_graph_nodes'][1]['content']['relation'], 'approximate')
        delta['graph_nodes'][1]['content']['parameter_role'] = 'yield'
        with self.assertRaisesRegex(ValueError, 'Yield'): g.compile_prediction(packet, delta)
        delta['graph_nodes'][1]['content']['parameter_role'] = 'testing'
        delta['graph_nodes'][1]['links'] = []
        with self.assertRaisesRegex(ValueError, 'refer to its operation'): g.compile_prediction(packet, delta)

    def test_dangling_binding_and_temporal_cycle_fail(self):
        packet, delta = fixture()
        delta['graph_nodes'] = [node(packet, 'x', 'binding', {}, [dict(role='subject', target_id='missing')])]
        with self.assertRaisesRegex(ValueError, 'Dangling'): g.compile_prediction(packet, delta)
        nodes = [node(packet, k, 'operation', dict(operation_raw=k)) for k in ['a', 'b']]
        nodes += [node(packet, k, 'order', {}, [dict(role='before', target_id=a), dict(role='after', target_id=b)])
            for k, a, b in [('ab', 'a', 'b'), ('ba', 'b', 'a')]]
        delta['graph_nodes'] = nodes
        with self.assertRaisesRegex(ValueError, 'chronology'): g.compile_prediction(packet, delta)

    def test_source_read_and_score_and_incomplete_response_fail(self):
        packet, delta = fixture(); delta['completed'] = False
        with self.assertRaisesRegex(ValueError, 'Incomplete'): g.compile_prediction(packet, delta)
        delta['completed'] = True
        delta['source_coverage'] = dict(read_block_ids=[], unread_block_ids=['B'], all_source_blocks_read=False)
        with self.assertRaisesRegex(ValueError, 'Full source reading'): g.compile_prediction(packet, delta)
        with self.assertRaisesRegex(ValueError, 'Reference/score'):
            g.engine.prepare(raw({'scores': [99]}), raw({'elements': []}),
                dict(path='n', sha256=g.engine.sha(raw({'scores': [99]}))),
                dict(path='s', sha256=g.engine.sha(raw({'elements': []}))))

    def test_full_scope_and_same_value_different_samples_are_preserved(self):
        packet, delta = fixture()
        first = node(packet, 'first', 'state', dict(state_raw='brown film'))
        first['scope'] = dict(subject='A', composition='component Z absent', branch='cast film', stage='after drying',
            operation='drying', conditions='approximately 80 °C', qualifiers='not the separately annealed specimen')
        first['scope_null_reasons'] = {}
        second = deepcopy(first); second['id'] = 'second'; second['scope']['subject'] = 'B'
        second['scope']['branch'] = 'separate analytical aliquot'
        delta['graph_nodes'] = [first, second]
        result = g.compile_prediction(packet, delta)
        self.assertEqual(result['active_graph_nodes'], [first, second])
        # This is lossless scope transport, not a claim the fixture proves B.
        self.assertFalse(result['scientific_accuracy_certified'])

    def test_unresolved_source_request_does_not_disappear(self):
        packet, delta = fixture()
        delta['targeted_source_requests'] = [dict(block_id='B', reason='Need the original image to resolve a damaged symbol')]
        result = g.compile_prediction(packet, delta)
        self.assertEqual(result['targeted_source_requests'], delta['targeted_source_requests'])
        self.assertTrue(all(r['active'] for r in g.effective_fields(packet, result)))

    def test_prior_literals_propagate_only_exact_native_disposition(self):
        packet, delta = fixture()
        value = packet['native_document']['samples'][0]['state_description']
        prior = dict(graph={'alias': value, 'unrelated': value}, native_origin_index=[dict(alias_pointer='/alias',
            alias_sha256=g.canonical(value), derivation='literal_copy', native_field_witnesses=[dict(
                field_pointer='/samples/0/state_description', field_sha256=g.canonical(value))])])
        pb = raw(prior)
        packet = g.engine.prepare(raw(packet['native_document']), raw(packet['source_document']), packet['native_file'],
            packet['source_file'], pb, dict(path='prior', sha256=g.engine.sha(pb)))
        delta = g.delta_template(packet); delta.update(completed=True,
            source_coverage=dict(read_block_ids=['B'], unread_block_ids=[], all_source_blocks_read=True),
            checklist={k: dict(status='reviewed', reason='Synthetic source') for k in g.CHECKLIST})
        correction(packet, delta)
        rows = list(g.effective_fields(packet, g.compile_prediction(packet, delta)))
        self.assertFalse(next(r for r in rows if r['origin'] == 'prior' and r['field_pointer'] == '/alias')['active'])
        self.assertTrue(next(r for r in rows if r['origin'] == 'prior' and r['field_pointer'] == '/unrelated')['active'])


class UnifiedEntry(unittest.TestCase):
    def invoke(self, args, expected=0):
        finished = subprocess.run([sys.executable, '-B', '-X', 'utf8', str(CODE / 'process_workflow_runner.py')] + args,
            capture_output=True, text=True, encoding='utf-8')
        if expected == 0: self.assertEqual(finished.returncode, 0, finished.stdout + finished.stderr)
        else: self.assertNotEqual(finished.returncode, 0, finished.stdout + finished.stderr)
        return finished

    def test_prepare_client_publish_resume_and_source_tampering(self):
        with tempfile.TemporaryDirectory(prefix='general158_integration_') as temp:
            root = Path(temp); packet, _ = fixture()
            native = g.write_bytes(root / 'native.json', raw(packet['native_document']))
            source = g.write_bytes(root / 'source.json', raw(packet['source_document']))
            manifest = g.write(root / 'inputs.json', dict(papers=[dict(reference_no='new_unseen_paper', native_final=native, stage0=source)]))
            tasks = root / 'tasks'
            base = ['--workflow', 'general158', '--manifest', manifest['path']]
            self.invoke(base + ['--stage', 'prepare', '--output', str(tasks)])
            task_manifest = json.loads((tasks / 'prepared_tasks.json').read_text(encoding='utf-8'))
            self.assertFalse(task_manifest['semantic_model_executed'])
            # Execute the copied entry/package without the mutable project tree.
            copied = root / 'standalone'
            shutil.copytree(tasks / 'runtime', copied)
            portable = subprocess.run([sys.executable, '-B', '-X', 'utf8', str(copied / 'process_workflow_runner.py'),
                '--workflow', 'general158', '--stage', 'prepare', '--manifest', manifest['path'],
                '--output', str(root / 'standalone_tasks')], capture_output=True, text=True, encoding='utf-8')
            self.assertEqual(portable.returncode, 0, portable.stdout + portable.stderr)
            portable_tasks = json.loads((root / 'standalone_tasks/prepared_tasks.json').read_text(encoding='utf-8'))
            self.assertEqual(portable_tasks['workflow_binding'], task_manifest['workflow_binding'])
            packet = json.loads((tasks / 'papers/new_unseen_paper/packet.json').read_text(encoding='utf-8'))
            delta = g.delta_template(packet); delta.update(completed=True,
                source_coverage=dict(read_block_ids=['B'], unread_block_ids=[], all_source_blocks_read=True),
                checklist={k: dict(status='reviewed', reason='Synthetic client fixture, not a real LLM') for k in g.CHECKLIST})
            correction(packet, delta)
            responses = root / 'responses/new_unseen_paper'
            first = g.write(responses / 'attempt_001.json', delta)
            g.write(responses / 'attempts.json', dict(attempts=[dict(path='attempt_001.json', sha256=first['sha256'])]))
            g.write(responses / 'run_log.json', dict(reference_no='new_unseen_paper', synthetic_fixture=True, observed_backend_model=None, tokens=None, cost=None))
            out = root / 'published'
            command = base + ['--stage', 'publish', '--tasks', str(tasks / 'prepared_tasks.json'), '--responses', str(responses.parent), '--output', str(out)]
            self.invoke(command)
            self.invoke(command + ['--resume'])
            result = json.loads((out / 'papers/new_unseen_paper/prediction.json').read_text(encoding='utf-8'))
            self.assertFalse(result['scientific_accuracy_certified'])
            self.assertEqual(g.digest(native['path']), native['sha256'])
            self.assertEqual(g.digest(source['path']), source['sha256'])
            self.assertEqual(json.loads((out / 'process_access_log.json').read_text(encoding='utf-8'))['denied_attempts'], [])
            # Retain a failed first response and only accept an explicit revision.
            bad = deepcopy(delta); bad['completed'] = False
            bad_pin = g.write(responses / 'bad_first.json', bad)
            revision = deepcopy(delta); revision['previous_response_sha256'] = bad_pin['sha256']
            revised_pin = g.write(responses / 'revision.json', revision)
            (responses / 'attempts.json').write_text(json.dumps(dict(attempts=[
                dict(path='bad_first.json', sha256=bad_pin['sha256']),
                dict(path='revision.json', sha256=revised_pin['sha256'])])), encoding='utf-8')
            second_out = root / 'published_revision'
            second_command = command[:-1] + [str(second_out)]
            self.invoke(second_command)
            receipts = json.loads((second_out / 'papers/new_unseen_paper/attempt_receipts.json').read_text(encoding='utf-8'))
            self.assertEqual([r['passed'] for r in receipts], [False, True])
            self.assertEqual((second_out / 'papers/new_unseen_paper/attempt_001.json').read_bytes(), Path(bad_pin['path']).read_bytes())
            # Responses changed: do not accept the old successful run as this run.
            self.invoke(command + ['--resume'], expected=1)
            (responses / 'attempts.json').write_text(json.dumps(dict(attempts=[dict(path='attempt_001.json', sha256=first['sha256'])])), encoding='utf-8')
            (out / 'runtime/process_workflow/closure/protocol.md').write_text('tampered', encoding='utf-8')
            self.invoke(command + ['--resume'], expected=1)

    def test_main_pipeline_forwards_general158_to_same_entry(self):
        with tempfile.TemporaryDirectory(prefix='general158_pipeline_') as temp:
            root = Path(temp); pdfs = root / 'pdfs'; pdfs.mkdir()
            (pdfs / 'reference_no_1234567.pdf').write_bytes(b'%PDF-1.4\n%%EOF\n')
            cache = root / 'cache/reference_no_1234567'; cache.mkdir(parents=True)
            g.write(cache / 'final.json', dict(samples=[], process_steps=[]))
            g.write(cache / 'stage0_blocks.json', dict(elements=[]))
            finished = subprocess.run([sys.executable, '-B', '-X', 'utf8', str(CODE / 'pipeline_runner.py'),
                '--input-dir', str(pdfs), '--process-cache-root', str(cache.parent),
                '--process-recovery-only', '--process-recovery-output', str(root / 'tasks'),
                '--process-workflow', 'general158', '--process-stage', 'prepare'], capture_output=True, text=True, encoding='utf-8')
            self.assertEqual(finished.returncode, 0, finished.stdout + finished.stderr)
            result = json.loads((root / 'tasks/prepared_tasks.json').read_text(encoding='utf-8'))
            self.assertEqual(result['version'], 'general158-v1')
            self.assertEqual(len(result['papers']), 1)

    def test_protocol_contains_all_rule_families_without_paper_ids(self):
        protocol = (CODE / 'process_workflow/closure/protocol.md').read_text(encoding='utf-8')
        for key in g.CHECKLIST: self.assertIn('## ' + key + ' ', protocol)
        self.assertNotIn('reference_no_00', protocol)


if __name__ == '__main__': unittest.main()
