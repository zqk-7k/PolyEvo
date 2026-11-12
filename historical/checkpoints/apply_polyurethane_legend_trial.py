"""Connect old table-local cells to separately frozen source code meanings."""
import re
from copy import deepcopy
from prepare_audit import OUT,read,save,sha,canonical
from read_polyurethane_solubility_legend import DEST

TRIAL=OUT/'process_relation_trial_029'
EXTENSION='process_polyurethane_targeted_solubility_legend_supplement'


def label_parts(label):
    m=re.fullmatch(r'(.+?)\s*\$\^\{?([a-z])\}?\$',label.strip());assert m,label
    return m.group(1).strip(),m.group(2)


def build(property_doc,source,source_meta):
    series=property_doc['property_series'][22]
    assert series['property_name_normalized']=='Solubility' and 'TABLE VI' in series['points'][0]['measurement_context']['other_conditions']['source_caption']
    codes={x['raw_code']:x for x in source['code_definitions']};notes={x['raw_marker']:x for x in source['specimen_method_footnotes']}
    g=dict(operations=[],parameters=[],orders=[],states=[],bindings=[],material_identity_nodes=[],cell_index=[],
           source_legend=deepcopy(source),source_prediction_freeze=source_meta,
           old_series_pointer='@property:/property_series/22',old_series_sha256=canonical(series),
           table_body_not_reextracted=True,global_property_sample_ids_not_modified=True,external_api_calls=0)
    labels={};pairs=set()
    for i,point in enumerate(series['points']):
        coordinates={x['name_raw']:x['value_raw'] for x in point['coordinates']};raw=coordinates['source sample label'];medium=coordinates['source condition/state']
        label,marker=label_parts(raw);assert marker in notes
        if raw not in labels:
            ident='TABLE_VI_'+label+'_'+marker;labels[raw]=ident
            g['material_identity_nodes'].append(dict(id=ident,kind='material_identity',table_label='VI',sample_label_raw=raw,
                    polymer_code=label,preparation_method_marker=marker,preparation_method=notes[marker]['raw_definition'],
                    exact_table_local_specimen_identity=True,canonical_global_sample_identity_not_assumed=True))
            g['bindings'].append(dict(id='B_METHOD_'+ident,kind='binding',material_id=ident,
                    relation='table_local_column_has_the_method_defined_by_its_own_b_or_c_footnote',source_method_marker=marker,
                    source_method_definition=notes[marker]['raw_definition'],method_labels_not_transferred_from_other_tables=True))
        assert (raw,medium) not in pairs;pairs.add((raw,medium));code=point['value_raw'];assert code in codes
        definition=codes[code];assert definition['interpretation']['stages']
        sid='SOLUBILITY_'+str(i+1).zfill(3);pointptr='@property:/property_series/22/points/'+str(i)
        state=dict(id=sid,kind='state',material_id=labels[raw],sample_label_raw=raw,polymer_code=label,
                   preparation_method=notes[marker]['raw_definition'],medium_raw=medium,
                   stage='reported solvent test stages exactly as defined for this categorical cell',
                   state=definition['raw_definition'],reported_stages=deepcopy(definition['interpretation']['stages']),
                   source_category_raw=code,source_code_definition=deepcopy(definition),
                   old_point_pointer=pointptr,old_point_sha256=canonical(point),
                   absolute_temperature_concentration_duration_not_inferred=True)
        for key,value in definition['interpretation'].items():
            if key!='stages':state[key]=deepcopy(value)
        g['states'].append(state)
        g['bindings'].append(dict(id='B_'+sid,kind='binding',material_id=labels[raw],state_id=sid,
                   old_point_pointer=pointptr,old_point_sha256=canonical(point),solvent_raw=medium,source_code_raw=code,
                   relation='this_actual_old_categorical_cell_belongs_to_this_route_specific_specimen_and_solvent',
                   raw_numeric_category_not_replaced_by_a_property_value=True,full_reported_stage_conjunction_preserved=True))
        g['cell_index'].append(dict(point_index=i,point_pointer=pointptr,point_sha256=canonical(point),sample_label_raw=raw,
                                   medium_raw=medium,code_raw=code,state_index=len(g['states'])-1,binding_index=len(g['bindings'])-1))
    g['no_changes_to_original_property_sample_resolution']=True
    g['scope_notes']=['TableVI b/c explicitly distinguish polyaddition and polycondensation specimens; the six local columns are not collapsed into three polymers.',
                     'Code1 remains a disjunction of melted, sticky or swollen, not a uniquely assigned swollen specimen.',
                     'Codes3/4 retain both the hot and cold outcomes in one composite cell-state assertion; no absolute temperatures, cooling rate or numeric test timing is supplied.',
                     'Code0 is reported unaffected in hot solvent, without inventing a particular morphology or an independent cold test.',
                     'Code5 is soluble in cold solvent; prior heating is not inferred.']
    return g


def main():
    pp=OUT/'process_relation_trial_028/freeze.json';parent=read(pp)
    sf=DEST/'prediction_freeze.json';f=read(sf);assert sha(f['graph_path'])==f['graph_sha256'];source=read(f['graph_path']);rows=[]
    assert not (TRIAL/'freeze.json').exists()
    for p in parent['papers']:
        assert sha(p['candidate_path'])==p['candidate_sha256'];row=deepcopy(p);row['changed_from_immediate_parent']=False
        if p['reference_no']=='reference_no_0071569':
            pred=read(p['candidate_path']);origin=pred['property_source'];assert sha(origin['path'])==origin['sha256']
            assert EXTENSION not in pred;pred[EXTENSION]=[build(read(origin['path']),source,dict(path=str(sf),sha256=sha(sf)))];dest=TRIAL/'papers'/(p['reference_no']+'.json');save(dest,pred)
            row.update(candidate_path=str(dest),candidate_sha256=sha(dest),changed_from_parent=True,changed_from_immediate_parent=True,
                       immediate_parent_candidate_path=p['candidate_path'],immediate_parent_candidate_sha256=p['candidate_sha256'])
        rows.append(row)
    save(TRIAL/'freeze.json',dict(version=TRIAL.name,parent_trial='process_relation_trial_028',parent_trial_freeze_sha256=sha(pp),
          baseline_candidate='candidate_v10',baseline_candidate_freeze_sha256=sha(OUT/'candidate_v10/freeze.json'),prediction_application_code_sha256=sha(__file__),
          source_prediction_freeze=dict(path=str(sf),sha256=sha(sf)),papers=rows,papers_total=101,changed_papers_this_round=1,
          cumulative_changed_papers=sum(bool(x.get('changed_from_parent')) for x in rows),property_content_or_bindings_modified=False,frozen_original_outputs_modified=False,
          reference_answers_or_scores_used_as_prediction_inputs=False,new_pdf_information_extracted=1,
          new_pdf_information_unit='one original PDF page, TableVI category legend and two method footnotes only',old_categorical_cells_reused=96,
          whole_batch_reextraction=False,stable_workflow_release=False,external_api_calls=0))
    print(dict(papers=101,changed_this_round=1,old_cells_reused=96,new_source_page=1,scored=False))


if __name__=='__main__':main()
