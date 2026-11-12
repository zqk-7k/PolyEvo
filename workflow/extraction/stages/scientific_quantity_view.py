"""Project one native quantity to a coherent value/unit pair for external consumers.

Native records retain both source literals and normalized quantities. A consumer
must not combine a source Kelvin value with a normalized Celsius range endpoint.
This projection does not alter native records or create physical conversions.
"""
from stages.stage4_direct_table_supplement import table_cell_scalar


def quantity_view(row, parent=None):
    parent = parent or {}
    raw_unit = row.get('unit_raw') or parent.get('unit_raw')
    normalized_unit = row.get('unit_normalized') or parent.get('unit_normalized')
    lower, upper = row.get('value_min'), row.get('value_max')
    if raw_unit and normalized_unit and raw_unit != normalized_unit and lower is not None:
        source_scalar = table_cell_scalar(str(row.get('value_raw') or ''))
        if source_scalar is not None and upper == lower:
            # Equal native bounds denote one scalar, not a printed range. Retain
            # its original precision and express the redundant bound in the SAME
            # source unit. Both normalized bounds remain in the native archive.
            return {'value':row['value_raw'], 'value_max':source_scalar, 'unit':raw_unit,
                    'representation':'coherent_source_scalar',
                    'source_value_raw':row['value_raw'], 'source_unit_raw':raw_unit}
        return {'value':format(lower,'.12g'), 'value_max':upper,
                'unit':normalized_unit, 'representation':'normalized_physical_quantity',
                'source_value_raw':row.get('value_raw'), 'source_unit_raw':raw_unit}
    return {'value':row.get('value_raw',lower), 'value_max':upper,
            'unit':raw_unit or normalized_unit or '', 'representation':'source_quantity',
            'source_value_raw':row.get('value_raw'), 'source_unit_raw':raw_unit}
