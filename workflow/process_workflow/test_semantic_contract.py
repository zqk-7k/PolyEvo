import unittest
from copy import deepcopy

from .common import canonical
from .semantic import validate, retained_unknown_native_claims


def fixture():
    source = dict(elements=[dict(block_id='B', type='text', text='The A film was dried at 80°C.')])
    sample = dict(sample_id='s1', state_description='A dry film')
    native = dict(samples=[sample], process_steps=[])
    proposals = dict(native_disposition_requirements=[dict(source_pointer='/samples/0', original_sha256=canonical(sample))])
    anchor = [dict(block_id='B', quote='The A film was dried at 80°C.')]
    graph = dict(schema_version='portable_process_semantic_v1', reference_no='synthetic',
        source_document_sha256='source-hash',
        material_identities=[dict(id='M', label='A', scope_kind='actual_sample', member_ids=[], source_anchors=anchor)],
        states=[dict(id='S', material_id='M', stage='after drying', state_description='dry film', source_anchors=anchor)],
        operations=[dict(id='O', name='drying', inputs=[], outputs=['S'], parameter_ids=['P'], source_anchors=anchor)],
        parameters=[dict(id='P', role='temperature', value_raw='80', unit_raw='°C', relation='exact',
            operation_id='O', material_id='M', source_anchors=anchor)],
        orders=[], bindings=[], nonphysical_annotations=[], unresolved_source_items=[],
        native_dispositions=[dict(source_pointer='/samples/0', original_sha256=canonical(sample),
            disposition='retained', replacement_ids=['S'], reason='explicit dried film', source_anchors=anchor)],
        source_coverage=dict(read_block_ids=['B'], unread_block_ids=[], all_source_blocks_read=True))
    return graph, source, proposals, native


class SemanticContract(unittest.TestCase):
    def test_valid_contract_does_not_claim_semantic_correctness(self):
        graph, source, proposals, _ = fixture()
        result = validate(graph, source, 'source-hash', proposals, 'synthetic')
        self.assertTrue(result['passed'])
        self.assertFalse(result['semantic_accuracy_certified'])

    def test_fabricated_quote_is_rejected(self):
        graph, source, proposals, _ = fixture()
        graph = deepcopy(graph)
        graph['parameters'][0]['source_anchors'][0]['quote'] = 'The process took 5 hours.'
        self.assertFalse(validate(graph, source, 'source-hash', proposals, 'synthetic')['passed'])

    def test_dangling_operation_reference_is_rejected(self):
        graph, source, proposals, _ = fixture()
        graph['parameters'][0]['operation_id'] = 'nonexistent'
        self.assertFalse(validate(graph, source, 'source-hash', proposals, 'synthetic')['passed'])

    def test_old_native_claim_cannot_be_silently_omitted(self):
        graph, source, proposals, _ = fixture()
        graph['native_dispositions'] = []
        self.assertFalse(validate(graph, source, 'source-hash', proposals, 'synthetic')['passed'])

    def test_unconfirmed_native_claim_remains_in_output_review(self):
        graph, source, proposals, native = fixture()
        graph['native_dispositions'][0].update(disposition='unresolved', replacement_ids=[],
            reason='complete state scope not established', source_anchors=[])
        self.assertTrue(validate(graph, source, 'source-hash', proposals, 'synthetic')['passed'])
        retained = retained_unknown_native_claims(graph, native)
        self.assertEqual(retained[0]['complete_original_claim'], native['samples'][0])
        self.assertTrue(retained[0]['stays_in_output_support_review'])


if __name__ == '__main__':
    unittest.main()
