"""Synthetic-only native publication and legacy-prefix integration checks."""
import hashlib
import importlib.util
import json
from copy import deepcopy
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from .core import process_document
from .native_owner_completion import AUDIT, COLLECTION, canonical, complete_native_owners, pointer

CODE = Path(__file__).resolve().parents[1]
EXP = CODE / 'compat/native_inventory'
sys.path.insert(0, str(EXP))


def fixture():
    return dict(samples=[dict(sample_id='S0', state_description='synthetic dry state')],
        process_steps=[dict(step_id='P0', process_type='synthetic heating',
            input_sample_ids=['S0'], output_sample_ids=[], parameters=dict(temperature='127 degreeX'))],
        property_observations=[
            dict(value_raw='17.03', unit_raw='custom unit', measurement_condition_id='M0',
                state_description='synthetic cooling', coordinates=[]),
            dict(value_raw='1.2', state_description='synthetic rest', unit_raw='u'),
            dict(value_raw='4.0', coordinates=[dict(name_raw='synthetic axis', value_raw='003.2', unit_raw='UX')])],
        specialized_property_observations=[dict(process=dict(temperature='003K', operation='synthetic quench'))],
        unresolved_property_observations=[dict(state_description='synthetic pending', value_raw='0009')],
        measurement_conditions=[dict(measurement_condition_id='M0', hold_time='008 minX')],
        characterizations=[dict(characterization_id='K0', state_description='synthetic after test')],
        property_series=[dict(series_id='R0', sample_id='S0', characterization_id='K0',
            measurement_context=dict(temperature='002.70 UX'), qualifiers=['original'],
            points=[dict(value_raw='1.0', unit_raw='A', coordinates=[]),
                dict(value_raw='2.0', unit_raw='B'),
                dict(value_raw='3.0', coordinates=[dict(name_raw='time', value_raw='9', unit_raw='s')])])],
        polymer_entities=[dict(entity_id='E0', name_raw='synthetic polymer')],
        material_mentions=[dict(text='synthetic material')],
        **{'unknown/scientific~extension': dict(state='synthetic unusual state', value_raw='0001.20', unit_raw='zzz')},
        evidence=[], provenance=dict(note='synthetic'), warnings=['synthetic warning'],
        quality=dict(status='synthetic'), schema_version='synthetic_v1')


def prediction(native, source=None):
    source = source or dict(path='synthetic_native.json', sha256='a' * 64)
    result = process_document(native, dict(elements=[]), property_source=source,
        stage0_source=dict(path='synthetic_stage0.json', sha256='b' * 64))
    result['reference_no'] = 'synthetic'
    return result


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class NativeOwnerCompletion(unittest.TestCase):
    def test_lossless_complete_coverage_and_series_projection(self):
        native = fixture()
        before = deepcopy(native)
        old = prediction(native)
        old_copy = deepcopy(old)
        completed = complete_native_owners(old, native, native_source=old['property_source'])
        self.assertEqual(old, old_copy)
        self.assertEqual(native, before)
        self.assertEqual(list(completed)[:-2], list(old))
        self.assertEqual({k: completed[k] for k in old}, old)
        rows = {r['original_owner_path']: r for r in completed[COLLECTION]}
        required = {'/property_observations/0', '/property_observations/1',
            '/specialized_property_observations/0', '/unresolved_property_observations/0',
            '/measurement_conditions/0', '/characterizations/0', '/property_series/0',
            '/property_series/0/points/0', '/property_series/0/points/1',
            '/polymer_entities/0', '/material_mentions/0', '/unknown~1scientific~0extension'}
        self.assertEqual(set(rows), required)
        self.assertFalse(set(rows) & {r['owner_path'] for r in old['effective_process_contexts']})
        self.assertFalse(any(p.startswith(('/samples/', '/process_steps/')) for p in rows))
        for path, row in rows.items():
            owner = pointer(native, path)
            self.assertEqual(row['original_owner_sha256'], canonical(owner))
            self.assertEqual(row['native_source'], old['property_source'])
            if row['record_kind'] == 'complete_native_owner':
                self.assertEqual(row['unmodified_original_owner'], owner)
        parent = rows['/property_series/0']
        self.assertNotIn('unmodified_original_owner', parent)
        self.assertEqual(parent['unmodified_original_owner_fields_except_points'],
            {k: v for k, v in native['property_series'][0].items() if k != 'points'})
        self.assertEqual(len(parent['point_owner_coverage']), 3)
        self.assertEqual(parent['point_owner_coverage'][2]['disposition'], 'already_effective_owner')
        for covered in parent['point_owner_coverage']:
            target = pointer(completed, covered['prediction_path'])
            self.assertEqual(target['original_owner_sha256'], covered['original_owner_sha256'])
        ref = rows['/property_observations/0']['explicit_native_context_references'][0]
        self.assertEqual(ref['matching_native_contexts'][0]['original_context_path'], '/measurement_conditions/0')
        ref = parent['explicit_native_context_references'][0]
        self.assertEqual(ref['matching_native_contexts'][0]['original_context_path'], '/characterizations/0')
        exclusions = {r['allowlist_entry'] for r in completed[AUDIT]['excluded_metadata_roots']}
        self.assertEqual(exclusions, {'evidence', 'provenance', 'warnings', 'quality', 'schema_version'})
        self.assertEqual(complete_native_owners(completed, native, native_source=old['property_source']), completed)

    def test_standalone_inventory_exact_old_prefix_and_true_paths(self):
        native = fixture()
        old = prediction(native)
        completed = complete_native_owners(old, native, native_source=old['property_source'])
        # Read only the explicitly allowed original generator and integrity code.
        sys.path.insert(0, str(EXP))
        try:
            legacy = load(EXP / 'build_active_claim_inventory.py', '_test_legacy_native_prefix')
        finally:
            sys.path.pop(0)
        new = load(EXP / 'build_active_claim_inventory_native_complete_v2.py', '_test_native_complete_gen')
        original_inventory = legacy.inventory(old)
        actual = new.inventory(completed)
        count = original_inventory['container_count']
        self.assertEqual(actual['legacy_container_prefix_count'], count)
        self.assertEqual(actual['review_containers'][:count], original_inventory['review_containers'])
        self.assertEqual(actual['container_count'] - count, len(completed[COLLECTION]))
        for row in actual['review_containers']:
            self.assertEqual(pointer(completed, row['prediction_path']), row['complete_container'])
            self.assertEqual(canonical(pointer(completed, row['prediction_path'])), row['complete_container_sha256'])
        semantic = deepcopy(old)
        semantic.update(active_primary_process_graph='source_semantic_graph',
            source_semantic_graph=dict(states=[dict(id='synthetic_state')], operations=[], parameters=[],
                orders=[], bindings=[], material_identities=[], native_dispositions=[],
                unknown_scientific_extension=dict(original='unchanged')),
            unconfirmed_native_claims_still_active_for_output_support=[dict(source_pointer='/samples/0')],
            extra_existing_root=dict(original='unchanged'))
        semantic_complete = complete_native_owners(semantic, native, native_source=semantic['property_source'])
        semantic_legacy = legacy.inventory(semantic)
        semantic_new = new.inventory(semantic_complete)
        self.assertEqual(semantic_new['review_containers'][:semantic_legacy['container_count']],
            semantic_legacy['review_containers'])
        tampered = deepcopy(completed)
        tampered[COLLECTION][0]['unmodified_original_owner']['value_raw'] = 'changed'
        with self.assertRaises(ValueError):
            new.inventory(tampered)

    def test_explicit_existing_full_retention_and_unknown_scalar(self):
        native = fixture()
        native['opaque_extension'] = 'original scalar'
        old = prediction(native)
        old['native_process_context']['polymer_entities'] = deepcopy(native['polymer_entities'])
        completed = complete_native_owners(old, native, native_source=old['property_source'])
        paths = {r['original_owner_path'] for r in completed[COLLECTION]}
        self.assertNotIn('/polymer_entities/0', paths)
        self.assertIn('/opaque_extension', paths)
        old['native_process_context']['polymer_entities'][0]['name_raw'] = 'incomplete retention'
        completed = complete_native_owners(old, native, native_source=old['property_source'])
        self.assertIn('/polymer_entities/0', {r['original_owner_path'] for r in completed[COLLECTION]})

    def test_real_runner_v2_off_resume_and_frozen_runtime_only_synthetic(self):
        with tempfile.TemporaryDirectory(prefix='native_owner_completion_synthetic_') as temp:
            root = Path(temp)
            def write(name, value):
                path = root / name
                path.write_text(json.dumps(value), encoding='utf-8')
                return dict(path=str(path), sha256=hashlib.sha256(path.read_bytes()).hexdigest())
            source = write('native.json', fixture())
            stage0 = write('stage0.json', dict(elements=[]))
            manifest = write('manifest.json', dict(papers=[dict(reference_no='synthetic', native_final=source, stage0=stage0)]))
            def run(out, *extra):
                return subprocess.run([sys.executable, '-B', '-X', 'utf8', str(CODE / 'process_workflow_runner.py'),
                    '--manifest', manifest['path'], '--output', str(root / out), '--workers', '1', *extra],
                    text=True, encoding='utf-8', capture_output=True)
            for out, args in [('v2', []), ('legacy', ['--native-owner-completion', 'off'])]:
                done = run(out, *args)
                self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
            completed = json.loads((root / 'v2/papers/synthetic/prediction.json').read_text(encoding='utf-8'))
            old = json.loads((root / 'legacy/papers/synthetic/prediction.json').read_text(encoding='utf-8'))
            self.assertEqual({k: v for k, v in completed.items() if k not in (COLLECTION, AUDIT)}, old)
            self.assertTrue((root / 'v2/runtime/process_workflow/native_owner_completion.py').is_file())
            # The separate production inventory CLI consumes this actual synthetic release.
            inventory_path = root / 'synthetic_inventory.json'
            inventory_command = subprocess.run([sys.executable, '-B', '-X', 'utf8',
                str(EXP / 'build_active_claim_inventory_native_complete_v2.py'),
                '--prediction', str(root / 'v2/papers/synthetic/prediction.json'),
                '--output', str(inventory_path)], text=True, encoding='utf-8', capture_output=True)
            self.assertEqual(inventory_command.returncode, 0, inventory_command.stdout + inventory_command.stderr)
            self.assertEqual(json.loads(inventory_path.read_text(encoding='utf-8'))['prediction']['sha256'],
                hashlib.sha256((root / 'v2/papers/synthetic/prediction.json').read_bytes()).hexdigest())
            access = json.loads((root / 'v2/process_access_log.json').read_text(encoding='utf-8'))
            self.assertEqual(access['denied_attempts'], [])
            self.assertTrue(access['no_network_access_permitted'])
            self.assertEqual(run('v2', '--resume').returncode, 0)
            self.assertNotEqual(run('v2', '--resume', '--native-owner-completion', 'off').returncode, 0)
            self.assertEqual(hashlib.sha256(Path(source['path']).read_bytes()).hexdigest(), source['sha256'])
            frozen = root / 'v2/runtime/process_workflow/native_owner_completion.py'
            frozen.write_bytes(frozen.read_bytes() + b'\n# synthetic tamper\n')
            self.assertNotEqual(run('v2', '--resume').returncode, 0)


if __name__ == '__main__':
    unittest.main()
