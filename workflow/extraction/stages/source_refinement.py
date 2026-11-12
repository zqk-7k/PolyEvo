"""Single source-only refinement entry shared by Stage4 and evolution replay.

No gold, PoLyInfo, experiment references or evaluation modules are imported.
Keeps the existing numbered pipeline; repairs execute within property Stage4.
"""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
from functools import lru_cache

from stages.stage4_direct_text_supplement import merge_text
from stages.stage4_direct_table_supplement import merge_supplement
from stages.source_standard_unit_resolution import resolve_standard_units
from stages.source_quantity_normalization import normalize_source_quantities
from stages.stage4_aligned_table_release import recover_aligned_temperature_rows
from stages.source_phase_transitions import recover_phase_transitions
from stages.source_peak_lists import recover_peak_lists
from stages.source_diffraction_lists import recover_diffraction_lists
from stages.source_display_scaling import repair_display_scales
from stages.source_verified_exponent_runs import repair_verified_exponent_runs
from stages.source_explicit_thermal_cells import recover_explicit_thermal_cells
from stages.source_prose_loss_facts import recover_prose_loss_facts
from stages.source_subject_labels import preserve_prose_subject_labels
from stages.source_record_precision import repair_source_records
from stages.source_property_semantics import repair_property_semantics
from stages.source_measurement_consistency import apply_measurement_corrections
from stages.source_response_header_consistency import repair_header_contexts
from stages.source_display_quantity_consistency import repair_display_quantities
from stages.source_definition_priority import repair_defined_dispersion
from stages.source_thermal_criterion_semantics import repair_loss_temperature_meaning
from stages.source_identity_scalar_consistency import repair_identity_scalars
from stages.source_phase_label_localization import repair as localize_phase_labels
from stages.source_caption_method_repair import repair as repair_caption_methods
from stages.source_footnote_quantity_semantics import repair as repair_footnote_quantities
from stages.source_mixed_subject_inheritance import repair as localize_mixed_subjects
from stages.source_aligned_response_context import repair as repair_aligned_context
from stages.source_method_scope_temperature import repair as repair_method_scope

VERSION='1.9.9'


@lru_cache(maxsize=1)
def runtime_fingerprint():
    folder=Path(__file__).resolve().parent
    paths=[Path(__file__),*folder.glob('source_*.py'),*folder.glob('stage4_*supplement.py'),
           folder/'stage4_aligned_table_release.py',folder/'stage4_symbol_condition_binding.py']
    hashes={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(set(paths))}
    return hashlib.sha256(json.dumps(hashes,sort_keys=True).encode()).hexdigest()


def refine_source_properties(stage4,stage0,*,table_responses=(),text_responses=(),
                             column_contexts=(),measurement_corrections=(),samples=(),entities=()):
    output,table_audit=merge_supplement(stage4,list(table_responses))
    output,text_audit=merge_text(output,stage0,list(text_responses))
    output,unit_audit=resolve_standard_units(output,stage0)
    output,alignment_audit=recover_aligned_temperature_rows(output,stage0)
    output,phase_audit=recover_phase_transitions(output,stage0)
    output,peak_audit=recover_peak_lists(output,stage0)
    output,diffraction_audit=recover_diffraction_lists(output,stage0)
    output,display_audit=repair_display_scales(output,stage0)
    output,run_audit=repair_verified_exponent_runs(output,stage0)
    output,explicit_thermal_audit=recover_explicit_thermal_cells(output,stage0)
    output,prose_loss_audit=recover_prose_loss_facts(output,stage0)
    output,subject_label_audit=preserve_prose_subject_labels(output,stage0)
    output,precision_audit=repair_source_records(output,stage0)
    output,semantics_audit=repair_property_semantics(output,stage0,column_contexts)
    output,measurement_audit=apply_measurement_corrections(output,stage0,measurement_corrections)
    output,quantity_audit=normalize_source_quantities(output)
    output,header_boundary_audit=repair_header_contexts(output,stage0)
    output,display_quantity_audit=repair_display_quantities(output,stage0)
    output,definition_priority_audit=repair_defined_dispersion(output,stage0)
    output,loss_meaning_audit=repair_loss_temperature_meaning(output,stage0)
    output,identity_scalar_audit=repair_identity_scalars(output,stage0,samples)
    output,local_phase_label_audit=localize_phase_labels(output,stage0)
    output,caption_method_audit=repair_caption_methods(output,stage0)
    output,footnote_quantity_audit=repair_footnote_quantities(output,stage0)
    output,mixed_subject_audit=localize_mixed_subjects(
        output,stage0,{'polymer_entities':list(entities)},{'samples':list(samples)})
    output,aligned_context_audit=repair_aligned_context(output,stage0)
    output,method_scope_audit=repair_method_scope(output,stage0)
    return output,{'version':VERSION,'runtime_fingerprint':runtime_fingerprint(),
        'table':table_audit,'text':text_audit,'standard_units':unit_audit,
        'aligned_rows':alignment_audit,'phase_transitions':phase_audit,'peak_lists':peak_audit,'quantity_normalization':quantity_audit,
        'diffraction_lists':diffraction_audit,'display_scales':display_audit,
        'verified_exponent_runs':run_audit,'explicit_thermal_cells':explicit_thermal_audit,
        'prose_loss_relations':prose_loss_audit,'source_subject_labels':subject_label_audit,
        'record_precision':precision_audit,'property_semantics':semantics_audit,
        'measurement_consistency':measurement_audit,
        'response_header_boundaries':header_boundary_audit,
        'display_quantity_coherence':display_quantity_audit,
        'explicit_author_definition':definition_priority_audit,
        'loss_temperature_meaning':loss_meaning_audit,
        'identity_bound_scalar':identity_scalar_audit,
        'local_component_response_labels':local_phase_label_audit,
        'caption_witnessed_methods':caption_method_audit,
        'own_table_quantity_definitions':footnote_quantity_audit,
        'mixed_subject_inheritance':mixed_subject_audit,
        'aligned_response_context':aligned_context_audit,
        'method_scoped_temperature':method_scope_audit,'gold_access':False}
