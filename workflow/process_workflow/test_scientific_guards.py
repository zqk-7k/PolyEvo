"""Failure-focused checks for source ambiguity, state scope, bounds and order."""
import unittest
from copy import deepcopy

from .common import canonical
from .core import process_document


def empty_doc():
    return dict(samples=[], process_steps=[], property_series=[], property_observations=[], evidence=[])


def run(doc, source):
    return process_document(doc, source, property_source=dict(path='immutable.json', sha256='fixture'),
        stage0_source=dict(path='source.json', sha256='fixture'))


def table_fixture(name='LLDPE/SBH', value='100/0'):
    return dict(block_id='T1', type='table', caption='Material properties', page=0,
        table_cells=[dict(cell_id='h', row_index=0, column_index=0, text=name),
                     dict(cell_id='v', row_index=1, column_index=0, text=value)])


def coordinate_doc(table, phase=None):
    doc = empty_doc()
    doc['evidence'] = [dict(evidence_id='ev', block_id=table['block_id'], source_sentence=table['table_cells'][1]['text'],
        table_locator=dict(table_id=table['block_id'], cell_id='v', row_index=1, column_index=0))]
    point = dict(sample_id='native_sample', coordinates=[dict(name_raw='untyped column',
        value_raw=table['table_cells'][1]['text'], unit_raw='unknown basis', evidence_ids=['ev'])],
        measurement_context=dict(other_conditions={}))
    if phase:
        point['measurement_context']['other_conditions']['source_crystallization_state'] = phase
    doc['property_series'] = [dict(points=[point])]
    return doc


class ScientificGuards(unittest.TestCase):
    def test_zero_component_does_not_become_present_crystalline_phase(self):
        table = table_fixture()
        phase = 'SBH was crystalline'
        doc = coordinate_doc(table, phase)
        before = deepcopy(doc)
        result = run(doc, dict(elements=[table]))
        row = result['effective_process_contexts'][0]
        scoped = row['effective_measurement_context']['other_conditions']['source_crystallization_state']
        self.assertFalse(scoped['applicable_to_this_author_row'])
        self.assertEqual(scoped['state_text'], phase)
        self.assertEqual(row['effective_coordinates'][0]['value_raw'], '100/0')
        self.assertEqual(row['effective_coordinates'][0]['unit_raw'], 'unknown basis')
        self.assertEqual(doc, before)

    def test_ambiguous_different_source_cells_do_not_choose_one_header(self):
        t1 = table_fixture('Temperature', '20')
        t2 = table_fixture('Time', '20')
        t2['block_id'] = 'T2'
        doc = coordinate_doc(t1)
        doc['evidence'].append(dict(evidence_id='ev2', block_id='T2', source_sentence='20',
            table_locator=dict(table_id='T2', cell_id='v', row_index=1, column_index=0)))
        point = doc['property_series'][0]['points'][0]
        point['coordinates'][0]['evidence_ids'].append('ev2')
        result = run(doc, dict(elements=[t1, t2]))
        row = result['effective_process_contexts'][0]
        self.assertEqual(row['effective_coordinates'][0]['name_raw'], 'untyped column')
        self.assertEqual(row['unresolved_coordinates'][0]['source_candidate_count'], 2)

    def test_printed_scale_is_not_applied_to_numeric_value(self):
        table = table_fixture('Monomer concentration 10^4 (mol/L)', '1.6')
        doc = coordinate_doc(table)
        result = run(doc, dict(elements=[table]))
        co = result['effective_process_contexts'][0]['effective_coordinates'][0]
        self.assertEqual(co['value_raw'], '1.6')
        self.assertEqual(co['unit_raw'], 'unknown basis')
        self.assertIn('10^4', co['name_raw'])

    def test_run_label_is_not_transposed_parameter_name(self):
        table = dict(block_id='T1', type='table', caption='Synthesis conditions', table_cells=[
            dict(cell_id='h0', row_index=0, column_index=0, text='Condition'),
            dict(cell_id='h1', row_index=0, column_index=1, text='Run 1'),
            dict(cell_id='h2', row_index=0, column_index=2, text='Run 2'),
            dict(cell_id='r1', row_index=1, column_index=0, text='Temperature (°C)'),
            dict(cell_id='v', row_index=1, column_index=1, text='80')])
        doc = coordinate_doc(table_fixture('Temperature', '80'))
        doc['evidence'][0]['table_locator'].update(column_index=1)
        result = run(doc, dict(elements=[table]))
        self.assertEqual(result['effective_process_contexts'][0]['effective_coordinates'][0]['name_raw'], 'Temperature (°C)')

    def test_bound_is_not_an_exact_duration_and_properties_are_unchanged(self):
        doc = empty_doc()
        doc['evidence'] = [dict(evidence_id='ev', block_id='B', source_sentence='Conversion completed within 2 h.')]
        point = dict(value_raw='2', value_min=2.0, value_max=2.0, unit_raw='h', evidence_ids=['ev'],
            coordinates=[dict(name_raw='source sample label', value_raw='a reported material')],
            measurement_context=dict(other_conditions=dict(fact_role='process_parameter')))
        doc['property_series'] = [dict(property_name_raw='completion time', points=[point])]
        before = canonical(doc)
        result = run(doc, dict(elements=[dict(block_id='B', type='text', text='Conversion completed within 2 h.')]))
        parameter = result['effective_process_contexts'][0]['material_direct_parameter_contexts'][0]
        self.assertEqual(parameter['active_value_semantics']['relation'], 'upper_bound_inclusive')
        self.assertNotIn('value_min', parameter['primary_parameter'])
        self.assertNotIn('value_max', parameter['primary_parameter'])
        self.assertEqual(canonical(doc), before)

    def test_qualifier_needs_full_linked_source_phrase(self):
        doc = empty_doc()
        doc['evidence'] = [dict(evidence_id='ev', block_id='B', source_sentence='completed within 2 h')]
        point = dict(value_raw='2', value_min=2, value_max=2, unit_raw='h', evidence_ids=['ev'],
            coordinates=[dict(name_raw='source sample label', value_raw='a material')],
            measurement_context=dict(other_conditions=dict(fact_role='process_parameter')))
        doc['property_series'] = [dict(property_name_raw='completion time', points=[point])]
        result = run(doc, dict(elements=[dict(block_id='B', type='text', text='Another test used 2 h.')]))
        self.assertNotIn('material_direct_parameter_contexts', result['effective_process_contexts'][0])

    def test_array_position_and_shared_endpoint_do_not_create_time_order(self):
        doc = empty_doc()
        doc['samples'] = [dict(sample_id='s1'), dict(sample_id='s2')]
        doc['process_steps'] = [
            dict(step_id='later_in_list', process_type='drying', input_sample_ids=['s1'], output_sample_ids=['s2'], parameters={}),
            dict(step_id='earlier_in_list', process_type='mixing', input_sample_ids=['s2'], output_sample_ids=['s1'], parameters={})]
        result = run(doc, dict(elements=[]))
        self.assertEqual(result['process_graph']['orders'], [])
        self.assertEqual(result['native_process_context']['process_steps'], doc['process_steps'])

    def test_explicit_material_flow_is_kept_independent_of_array_position(self):
        doc = empty_doc()
        doc['samples'] = [dict(sample_id=s) for s in ['s1', 's2', 's3']]
        first = dict(step_id='prepare', process_type='mixing', input_sample_ids=['s1'], output_sample_ids=['s2'], parameters={})
        second = dict(step_id='dry', process_type='drying', input_sample_ids=['s2'], output_sample_ids=['s3'], parameters={})
        doc['process_steps'] = [second, first]
        result = run(doc, dict(elements=[]))
        self.assertEqual([(e['before'], e['after']) for e in result['process_graph']['orders']], [('prepare', 'dry')])
        self.assertTrue(result['process_graph']['orders'][0]['full_endpoint_identity_state_and_source_support_still_required'])

    def test_multiple_producers_do_not_create_a_cross_product_of_order_edges(self):
        doc = empty_doc()
        doc['process_steps'] = [
            dict(step_id='route_a', process_type='casting', output_sample_ids=['shared'], parameters={}),
            dict(step_id='route_b', process_type='casting', output_sample_ids=['shared'], parameters={}),
            dict(step_id='test', process_type='heating', input_sample_ids=['shared'], parameters={})]
        result = run(doc, dict(elements=[]))
        self.assertEqual(result['process_graph']['orders'], [])
        self.assertEqual(len(result['process_graph']['unresolved_native_material_flows']), 2)

    def test_negated_history_is_not_published_as_an_operation(self):
        doc = empty_doc()
        doc['samples'] = [dict(sample_id='s1', state_description='The sample was not dried at 80°C.', evidence_ids=['ev'])]
        doc['evidence'] = [dict(evidence_id='ev', block_id='B', source_sentence='The sample was not dried at 80°C.')]
        result = run(doc, dict(elements=[dict(block_id='B', type='text', text='The sample was not dried at 80°C.')]))
        self.assertEqual(result['recovered_operation_history'], [])
        self.assertTrue(result['pending_history_recovery'])
        self.assertEqual(result['native_process_context']['samples'], doc['samples'])

    def test_multi_clause_state_is_retained_whole(self):
        doc = empty_doc()
        text = 'Transparent film, insoluble in water; DMA mode gives relative values only.'
        doc['samples'] = [dict(sample_id='s1', state_description=text)]
        result = run(doc, dict(elements=[]))
        self.assertEqual(result['process_graph']['states'][0]['complete_original_sample']['state_description'], text)
        self.assertTrue(result['process_graph']['states'][0]['physical_state_taxonomy_not_automatically_certified'])

    def test_unicode_negative_temperature_is_not_made_positive(self):
        doc = empty_doc()
        text = 'heated at −78°C for 2 h'
        doc['samples'] = [dict(sample_id='s1', state_description=text, evidence_ids=['ev'])]
        doc['evidence'] = [dict(evidence_id='ev', block_id='B', source_sentence=text)]
        result = run(doc, dict(elements=[dict(block_id='B', type='text', text=text)]))
        self.assertEqual(len(result['recovered_operation_history']), 1)
        params = result['recovered_operation_history'][0]['parameters']
        self.assertEqual([p['value_raw'] for p in params if p['role'] == 'temperature'], ['−78°C'])

    def test_formula_suffix_does_not_create_duration(self):
        doc = empty_doc()
        text = 'heated in SO3H medium'
        doc['samples'] = [dict(sample_id='s1', state_description=text, evidence_ids=['ev'])]
        doc['evidence'] = [dict(evidence_id='ev', block_id='B', source_sentence=text)]
        result = run(doc, dict(elements=[dict(block_id='B', type='text', text=text)]))
        self.assertEqual(len(result['recovered_operation_history']), 1)
        self.assertFalse([p for p in result['recovered_operation_history'][0]['parameters'] if p['role'] == 'duration'])

    def test_formulation_phr_not_converted_to_percent_or_added_batch(self):
        table = dict(block_id='T1', type='table', caption='Mechanical properties of AA/BB blends', table_cells=[
            dict(cell_id='h0', row_index=0, column_index=0, text='BB content (phr)'),
            dict(cell_id='h1', row_index=0, column_index=1, text='Tensile strength (MPa)'),
            dict(cell_id='v', row_index=1, column_index=0, text='0'),
            dict(cell_id='resp', row_index=1, column_index=1, text='20')])
        doc = coordinate_doc(table_fixture('BB content (phr)', '0'))
        doc['evidence'].append(dict(evidence_id='er', block_id='T1', source_sentence='20',
            table_locator=dict(table_id='T1', cell_id='resp', row_index=1, column_index=1)))
        point = doc['property_series'][0]['points'][0]
        point.update(value_raw='20', evidence_ids=['er'])
        result = run(doc, dict(elements=[table]))
        ctx = result['effective_process_contexts'][0]['material_source_grid_contexts'][0]
        self.assertEqual(ctx['dose']['unit_raw'], 'phr')
        self.assertEqual(ctx['dose']['value_raw'], '0')
        self.assertTrue(ctx['zero_dose_control_no_component_presence_or_addition_inferred'])
        self.assertTrue(ctx['source_condition_class_not_unique_physical_batch'])
        self.assertEqual(result['process_graph']['operations'], [])

    def test_response_in_another_row_does_not_inherit_formulation(self):
        table = dict(block_id='T1', type='table', caption='Mechanical properties of AA/BB blends', table_cells=[
            dict(cell_id='h0', row_index=0, column_index=0, text='BB content (phr)'),
            dict(cell_id='h1', row_index=0, column_index=1, text='Tensile strength (MPa)'),
            dict(cell_id='v', row_index=1, column_index=0, text='0'),
            dict(cell_id='resp', row_index=2, column_index=1, text='20')])
        doc = coordinate_doc(table_fixture('BB content (phr)', '0'))
        doc['evidence'].append(dict(evidence_id='er', block_id='T1', source_sentence='20',
            table_locator=dict(table_id='T1', cell_id='resp', row_index=2, column_index=1)))
        doc['property_series'][0]['points'][0].update(value_raw='20', evidence_ids=['er'])
        result = run(doc, dict(elements=[table]))
        self.assertNotIn('material_source_grid_contexts', result['effective_process_contexts'][0])

    def test_source_case_does_not_certify_a_wrong_property_value(self):
        table = dict(block_id='T1', type='table', caption='Mechanical properties of AA/BB blends', table_cells=[
            dict(cell_id='h0', row_index=0, column_index=0, text='BB content (phr)'),
            dict(cell_id='h1', row_index=0, column_index=1, text='Tensile strength (MPa)'),
            dict(cell_id='v', row_index=1, column_index=0, text='0'),
            dict(cell_id='resp', row_index=1, column_index=1, text='20 ± 1')])
        doc = coordinate_doc(table_fixture('BB content (phr)', '0'))
        doc['evidence'].append(dict(evidence_id='er', block_id='T1', source_sentence='20 ± 1',
            table_locator=dict(table_id='T1', cell_id='resp', row_index=1, column_index=1)))
        point = doc['property_series'][0]['points'][0]
        point.update(value_raw='999', evidence_ids=['er'])
        result = run(doc, dict(elements=[table]))
        ctx = result['effective_process_contexts'][0]['material_source_grid_contexts'][0]
        self.assertEqual(ctx['dose']['value_raw'], '0')
        self.assertTrue(ctx['numerical_property_value_and_unit_not_validated_by_source_cell_location'])
        self.assertTrue(ctx['original_property_binding_not_newly_certified'])
        self.assertEqual(point['value_raw'], '999')


if __name__ == '__main__':
    unittest.main()
