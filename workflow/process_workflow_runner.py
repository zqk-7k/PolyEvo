"""Run a frozen, source-only process recovery workflow on any cache manifest.

This entry point makes no network calls and does not load project .env files.
Fresh PDF extraction remains the responsibility of pipeline_runner.py. Its
optional process-recovery hook invokes this entry after native extraction.
"""
import argparse
import concurrent.futures
import hashlib
import importlib
import importlib.abc
import importlib.machinery
import importlib.util
import json
import os
import re
import shutil
import sys
import threading
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

CODE = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def save(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def utc():
    return datetime.now(timezone.utc).isoformat()


def check_entry_inputs(entry):
    witnesses=[entry[key] for key in ['native_final','stage0']]
    witnesses += [w for w in (entry.get('semantic') or {}).values()
        if isinstance(w,dict) and 'path' in w and 'sha256' in w]
    for witness in witnesses:
        if sha(witness['path'])!=witness['sha256']:
            raise ValueError('Input changed: '+witness['path'])


def check_portable_ids(ids):
    reserved={'con','prn','aux','nul'}|{p+str(i) for p in ['com','lpt'] for i in range(1,10)}
    if not ids or not all(isinstance(i,str) and re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]*',i)
        and not i.endswith('.') and i.split('.')[0].casefold() not in reserved for i in ids):
        raise ValueError('Unsafe paper ID')
    if len({i.casefold() for i in ids})!=len(ids):
        raise ValueError('Duplicate or Windows-alias paper IDs')


def freeze_runtime(output):
    target = output / 'runtime/process_workflow'
    for source in sorted((CODE / 'process_workflow').rglob('*')):
        if not source.is_file() or source.suffix not in {'.py', '.md', '.json'} or '__pycache__' in source.parts:
            continue
        path = target / source.relative_to(CODE / 'process_workflow')
        path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, path)
    runner = output / 'runtime/process_workflow_runner.py'
    shutil.copyfile(__file__, runner)
    files = [dict(path=str(p), sha256=sha(p)) for p in sorted((output / 'runtime').rglob('*')) if p.is_file()]
    save(output / 'runtime_freeze.json', dict(files=files, frozen_before_execution=True))


def frozen_engine(output):
    runtime_files = read(output / 'runtime_freeze.json')['files']
    expected = {Path(item['path']).resolve(): item['sha256'] for item in runtime_files}
    for item in runtime_files:
        assert sha(item['path']) == item['sha256'], 'Frozen runtime changed: ' + item['path']
    name = '_polymer_frozen_process_runtime'
    package = output / 'runtime/process_workflow'
    class ExactSourceLoader(importlib.machinery.SourceFileLoader):
        def get_code(self, fullname):
            path = Path(self.path).resolve()
            data = self.get_data(str(path))
            assert path in expected and hashlib.sha256(data).hexdigest() == expected[path]
            return self.source_to_code(data, str(path))

    class FrozenPackageFinder(importlib.abc.MetaPathFinder):
        def find_spec(self, fullname, path=None, target=None):
            if not fullname.startswith(name + '.'):
                return None
            relative = fullname[len(name) + 1:].split('.')
            location = package.joinpath(*relative)
            is_package = (location / '__init__.py').is_file()
            source = location / '__init__.py' if is_package else location.with_suffix('.py')
            if source.resolve() not in expected:
                raise ImportError('Module outside frozen source manifest: ' + fullname)
            return importlib.util.spec_from_file_location(fullname, source,
                loader=ExactSourceLoader(fullname, str(source)),
                submodule_search_locations=[str(location)] if is_package else None)

    sys.meta_path.insert(0, FrozenPackageFinder())
    # Each command is one process; this alias never imports mutable source rules.
    spec = importlib.util.spec_from_file_location(name, package / '__init__.py',
        loader=ExactSourceLoader(name, str(package / '__init__.py')),
        submodule_search_locations=[str(package)])
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return importlib.import_module(name + '.core'), importlib.import_module(name + '.common')


def install_cache_guards(output, manifest_path, papers, extra_inputs=()):
    """Python process guards, not an OS sandbox or a clean model context."""
    exact_inputs = {manifest_path.resolve()}
    exact_inputs.update(Path(p).resolve() for p in extra_inputs)
    exact_inputs |= {Path(p[key]['path']).resolve() for p in papers for key in ['native_final', 'stage0']}
    for p in papers:
        for witness in (p.get('semantic') or {}).values():
            if isinstance(witness, dict) and 'path' in witness and 'sha256' in witness:
                exact_inputs.add(Path(witness['path']).resolve())
    python_roots = {Path(sys.base_prefix).resolve(), Path(sys.exec_prefix).resolve()}
    accessed = Counter()
    denied = []
    lock = threading.Lock()

    def audit(event, args):
        if event in {'socket.connect', 'socket.getaddrinfo', 'urllib.Request', 'http.client.connect'}:
            with lock:
                denied.append(dict(event=event, reason='network_disabled_in_cache_mode'))
            raise PermissionError('Network is disabled in the process-cache workflow')
        if event != 'open' or not args or not isinstance(args[0], (str, bytes, os.PathLike)):
            return
        path = Path(os.fsdecode(args[0])).resolve()
        mode = args[1] if len(args) > 1 else 'r'
        flags = args[2] if len(args) > 2 else 0
        write = (isinstance(mode, str) and any(k in mode for k in 'wax+'))
        write = write or (isinstance(flags, int) and bool(flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC)))
        allowed = path.is_relative_to(output)
        if not write:
            allowed = allowed or path in exact_inputs or any(path.is_relative_to(root) for root in python_roots)
        if not allowed:
            with lock:
                denied.append(dict(event='open', path=str(path), write=write))
            raise PermissionError('File outside the frozen cache input/output allowlist: ' + str(path))
        with lock:
            accessed[('write:' if write else 'read:') + str(path)] += 1

    sys.addaudithook(audit)
    return accessed, denied


def validate_result(result, original, common):
    assert result['native_process_context']['samples'] == original.get('samples', [])
    assert result['native_process_context']['process_steps'] == original.get('process_steps', [])
    expected = {}
    for root in common.ROOTS:
        for path, coordinates, owner_path, owner in common.walk(original.get(root, []), '/' + root):
            expected[owner_path] = (path, coordinates, owner)
    actual = {r['owner_path']: r for r in result['effective_process_contexts']}
    assert set(expected) == set(actual)
    for owner_path, (path, coordinates, owner) in expected.items():
        row = actual[owner_path]
        assert row['original_owner_sha256'] == common.canonical(owner)
        effective = row['effective_coordinates']
        assert len(effective) == len(coordinates)
        for before, after in zip(coordinates, effective):
            assert {k: v for k, v in before.items() if k != 'name_raw'} == {
                k: v for k, v in after.items() if k != 'name_raw'}
        assert row['existing_sample_id'] == owner.get('sample_id')
        assert row['existing_sample_ids'] == owner.get('sample_ids')
    old_orders = original.get('orders') or []
    assert result['process_graph']['orders'][:len(old_orders)] == old_orders
    steps = original.get('process_steps', [])
    for edge in result['process_graph']['orders'][len(old_orders):]:
        assert edge['basis'] == 'native_declared_output_to_input_material_flow'
        before, after = steps[edge['before_index']], steps[edge['after_index']]
        assert edge['before'] == before['step_id'] and edge['after'] == after['step_id']
        assert edge['shared_sample_ids'] == sorted(set(before.get('output_sample_ids', [])) & set(after.get('input_sample_ids', [])))
        assert common.canonical(before) == edge['before_complete_step_sha256']
        assert common.canonical(after) == edge['after_complete_step_sha256']
    return dict(original_native_samples_and_steps_preserved=True,
        coordinate_owners_verified=len(actual), no_coordinate_values_units_evidence_or_ids_changed=True,
        no_array_order_edges_invented=True, scientific_source_support_not_certified=True)


def run_general158(args):
    """The same entry prepares source tasks or publishes actual client responses."""
    if args.stage is None:
        raise ValueError('general158 requires --stage prepare or publish; missing semantic work is never silently skipped')
    manifest_path = args.manifest.resolve()
    raw = manifest_path.read_bytes()
    # Load the initial manifest with duplicate/nonfinite-key rejection as well.
    from process_workflow.closure.closure_v2 import decode, reject_feedback, require
    manifest = decode(raw); reject_feedback(manifest)
    if args.tasks is not None or args.responses is not None:
        require(args.stage == 'publish' and args.tasks is not None and args.responses is not None,
            '--tasks and --responses must be used together for general158 publication')
        require(set(manifest) == {'papers'}, 'With --tasks/--responses supply the original preparation input manifest')
        manifest['prepared_tasks'] = dict(path=str(args.tasks.resolve()), sha256=sha(args.tasks))
        for paper in manifest['papers']:
            base = (args.responses.resolve() / paper['reference_no']).resolve()
            # Validate IDs before using them as directory names.
            check_portable_ids([paper['reference_no']])
            require(base.is_relative_to(args.responses.resolve()), 'Response directory escapes explicit root')
            attempts = decode((base / 'attempts.json').read_bytes())
            require(set(attempts) == {'attempts'} and isinstance(attempts['attempts'], list), 'Exact ordered attempts manifest required')
            witnesses = []
            for item in attempts['attempts']:
                require(set(item) == {'path', 'sha256'}, 'Actual response filename/hash required')
                path = (base / item['path']).resolve()
                require(path.is_relative_to(base), 'Attempt escapes paper response directory')
                witnesses.append(dict(path=str(path), sha256=item['sha256']))
            paper['response'] = dict(attempts=witnesses,
                run_log=dict(path=str(base / 'run_log.json'), sha256=sha(base / 'run_log.json')))
    require(set(manifest) == ({'papers'} if args.stage == 'prepare' else {'papers', 'prepared_tasks'}), 'Exact general158 input manifest required')
    papers = manifest['papers']
    check_portable_ids([p['reference_no'] for p in papers])
    pins = []
    def collect(value):
        if isinstance(value, dict):
            if set(value) == {'path', 'sha256'}:
                pins.append(value)
            else:
                for child in value.values(): collect(child)
        elif isinstance(value, list):
            for child in value: collect(child)
    for paper in papers:
        permitted = {'reference_no', 'native_final', 'stage0', 'prior'} | ({'response'} if args.stage == 'publish' else set())
        require(set(paper) <= permitted and {'reference_no', 'native_final', 'stage0'} <= set(paper), 'Unexpected/missing paper inputs')
        if args.stage == 'publish':
            require(set(paper.get('response', {})) == {'attempts', 'run_log'} and paper['response']['attempts'], 'Pinned attempts and real client run log required')
        collect(paper)
    if args.stage == 'publish':
        collect(manifest['prepared_tasks'])
        tasks = decode(Path(manifest['prepared_tasks']['path']).read_bytes()); collect(tasks)
        for task in tasks['papers']:
            packet = decode(Path(task['packet']['path']).read_bytes())
            # Only actual immutable files, not arbitrary path-shaped scientific text.
            for key in ('native_file', 'source_file', 'prior_file'):
                if packet[key]: collect(packet[key])
    for item in pins:
        require(sha(item['path']) == item['sha256'], 'Input hash changed: ' + item['path'])
    output = args.output.resolve()
    # Prevent an output placement from shadowing any scientific input or runtime.
    require(not any(Path(p['path']).resolve().is_relative_to(output) for p in pins), 'Output may not contain input files')
    require(not output.is_relative_to(CODE / 'process_workflow'), 'Output may not modify workflow code')
    if output.exists():
        require(args.resume, 'Existing output preserved; use --resume or a new output directory')
        binding = read(output / 'execution_manifest.json')
        require(binding['input_manifest_sha256'] == sha(manifest_path) and binding['runner_sha256'] == sha(__file__)
            and binding['stage'] == args.stage, 'Resume input/entry/stage mismatch')
        require(binding['effective_manifest'] == manifest, 'Resume response/task pins changed')
        require(sha(output / 'runtime_freeze.json') == binding['runtime_freeze_sha256'], 'Runtime freeze changed')
        for item in read(output / 'freeze.json')['files']:
            require(sha(item['path']) == item['sha256'], 'Completed output changed: ' + item['path'])
        print(json.dumps(dict(event='general158_resume_verified', successful_outputs_regenerated=False)))
        return 0
    require(not args.resume, 'Cannot resume a nonexistent run')
    output.mkdir(parents=True)
    freeze_runtime(output)
    save(output / 'input_manifest.json', manifest)
    save(output / 'execution_manifest.json', dict(workflow='general158-v1', stage=args.stage,
        input_manifest_sha256=sha(manifest_path), runner_sha256=sha(__file__),
        effective_manifest=manifest,
        runtime_freeze_sha256=sha(output / 'runtime_freeze.json'), created_utc=utc(),
        external_api_calls=0, semantic_model_calls_by_this_entry=0, os_hard_isolation=False))
    sys.dont_write_bytecode = True
    accessed, denied = install_cache_guards(output, manifest_path, papers, [p['path'] for p in pins])
    frozen_core, _ = frozen_engine(output)
    general = importlib.import_module(frozen_core.__package__ + '.general158')
    result = general.run(args, manifest, frozen_core)
    for item in pins:
        require(sha(item['path']) == item['sha256'], 'Input changed during execution')
    save(output / ('prepared_tasks.json' if args.stage == 'prepare' else 'execution_summary.json'), result)
    save(output / 'process_access_log.json', dict(accesses=dict(sorted(accessed.items())), denied_attempts=denied,
        os_hard_isolation=False, python_audit_hook_is_not_an_os_security_boundary=True))
    failed = result.get('failed', 0)
    if not failed:
        save(output / 'freeze.json', dict(files=[dict(path=str(p), sha256=sha(p))
            for p in sorted(output.rglob('*')) if p.is_file() and p.name != 'freeze.json'],
            implementation_version='general158-v1', scientific_metrics_certified=False))
    print(json.dumps(dict(event='general158_finished', stage=args.stage, papers=len(papers), failed=failed,
        semantic_model_executed_by_python=False, external_api_calls=0), ensure_ascii=False))
    return 1 if failed else 0


def main(argv=None):
    if not __debug__:
        raise RuntimeError('Optimized Python is unsupported for integrity checks')
    parser = argparse.ArgumentParser(description='离线通用工艺整理；不调用模型或读取评分文件')
    parser.add_argument('--manifest', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--workers', type=int, default=4)
    parser.add_argument('--resume', action='store_true')
    parser.add_argument('--workflow', choices=('cache-v2', 'general158'), default='cache-v2')
    parser.add_argument('--stage', choices=('prepare', 'publish'),
        help='general158: prepare source-model tasks, or publish hash-bound actual responses')
    parser.add_argument('--tasks', type=Path, help='general158 prepared_tasks.json for publication')
    parser.add_argument('--responses', type=Path, help='Client response root containing one folder per paper')
    parser.add_argument('--native-owner-completion', choices=('v2', 'off'), default='v2',
        help='Add lossless native-owner review contexts; off retains the legacy output shape')
    args = parser.parse_args(argv)
    if args.workflow == 'general158':
        return run_general158(args)
    if args.stage is not None:
        raise ValueError('--stage requires --workflow general158')
    manifest_path = args.manifest.resolve()
    manifest = read(manifest_path)
    papers = manifest['papers']
    ids = [p['reference_no'] for p in papers]
    check_portable_ids(ids)
    assert len(ids) == len(set(ids)) and papers, 'Need a nonempty unique paper manifest'
    assert all(isinstance(ident, str) and re.fullmatch(r'[A-Za-z0-9_.-]+', ident)
        and ident not in {'.', '..'} for ident in ids), 'Paper IDs must be safe single path components'
    output = args.output.resolve()
    for entry in papers: check_entry_inputs(entry)
    if output.exists() and not args.resume:
        raise FileExistsError('Preserve existing outputs; use --resume or a new directory: ' + str(output))
    output.mkdir(parents=True, exist_ok=args.resume)
    if args.resume:
        saved = read(output / 'execution_manifest.json')
        assert saved['input_manifest_sha256'] == sha(manifest_path)
        assert saved['runner_sha256'] == sha(__file__)
        if saved.get('native_owner_completion', 'off') != args.native_owner_completion:
            raise ValueError('Native owner completion mode differs from the frozen run')
        if saved['runtime_freeze_sha256']!=sha(output/'runtime_freeze.json'):
            raise ValueError('Frozen runtime manifest changed')
        if sha(output/'input_manifest.json')!=saved['input_manifest_sha256']:
            raise ValueError('Saved input manifest changed')
    else:
        freeze_runtime(output)
        shutil.copyfile(manifest_path, output / 'input_manifest.json')
        save(output / 'execution_manifest.json', dict(created_utc=utc(), paper_count=len(papers),
            paper_ids=ids, input_manifest_path=str(manifest_path), input_manifest_sha256=sha(manifest_path),
            runner_sha256=sha(__file__), runtime_freeze_sha256=sha(output / 'runtime_freeze.json'),
            execution_mode='native_cache_recovery_no_api', external_api_calls=0,
            native_owner_completion=args.native_owner_completion,
            reference_or_score_paths_accepted=False,
            not_fresh_pdf_extraction=True, not_complete158_result_reproduction=True,
            os_hard_isolation=False, python_process_file_and_network_guards=True))
    sys.dont_write_bytecode = True
    accessed, denied = install_cache_guards(output, manifest_path, papers)
    core, common = frozen_engine(output)
    completion = importlib.import_module(core.__package__ + '.native_owner_completion') \
        if args.native_owner_completion == 'v2' else None

    def one(entry):
        ref = entry['reference_no']
        folder = output / 'papers' / ref
        folder.mkdir(parents=True, exist_ok=True)
        status_file = folder / 'status.json'
        check_entry_inputs(entry)
        if args.resume and status_file.is_file():
            old = read(status_file)
            if old['status'] == 'completed' and sha(folder / 'prediction.json') == old['prediction_sha256']:
                assert sha(entry['native_final']['path']) == entry['native_final']['sha256']
                assert sha(entry['stage0']['path']) == entry['stage0']['sha256']
                if sha(folder/'structural_validation.json')!=old['structural_validation_sha256']:
                    raise ValueError('Completed structural validation changed')
                if entry.get('semantic') and sha(folder/'semantic_structural_validation.json')!=old.get('semantic_structural_validation_sha256'):
                    raise ValueError('Completed semantic validation changed')
                return old
        started = utc()
        try:
            for key in ['native_final', 'stage0']:
                assert sha(entry[key]['path']) == entry[key]['sha256'], 'Input changed: ' + key
            original = read(entry['native_final']['path'])
            stage0 = read(entry['stage0']['path'])
            result = core.process_document(original, stage0,
                property_source=entry['native_final'], stage0_source=entry['stage0'])
            if entry.get('semantic'):
                semantic = entry['semantic']
                for witness in semantic.values():
                    if isinstance(witness, dict) and 'path' in witness and 'sha256' in witness:
                        assert sha(witness['path']) == witness['sha256']
                graph = read(semantic['graph']['path'])
                source_packet = read(semantic['source_packet']['path'])
                proposals = read(semantic['native_proposals']['path'])
                assert common.canonical(source_packet) == common.canonical(stage0)
                assert proposals['native_property_source_sha256'] == entry['native_final']['sha256']
                requirements=[dict(source_pointer='/samples/'+str(i),original_sha256=common.canonical(s))
                    for i,s in enumerate(original.get('samples',[])) if s.get('state_description')]
                requirements += [dict(source_pointer='/process_steps/'+str(i),original_sha256=common.canonical(s))
                    for i,s in enumerate(original.get('process_steps',[]))]
                if proposals.get('native_disposition_requirements')!=requirements:
                    raise ValueError('Native disposition requirements differ from original')
                for key in ['polymer_entities','samples','process_steps','evidence']:
                    if key in proposals and proposals[key]!=original.get(key,[]):
                        raise ValueError('Native candidates differ from original: '+key)
                lineage_keys={'graph','first_graph','source_packet','native_proposals','source_inventory','run_log','protocol'}
                lineage_complete=lineage_keys<=set(semantic)
                if lineage_complete:
                    first=json.loads(Path(semantic['first_graph']['path']).read_text(encoding='utf-8-sig'),strict=False)
                    if first.get('reference_no')!=ref or first.get('source_document_sha256')!=semantic['source_packet']['sha256']:
                        raise ValueError('First graph identity/source mismatch')
                    if first.get('schema_version')!='portable_process_semantic_v1':
                        raise ValueError('First graph schema mismatch')
                    for key in ['source_inventory','run_log']:
                        record=read(semantic[key]['path'])
                        if not isinstance(record,dict) or not record or ('reference_no' in record and record['reference_no']!=ref):
                            raise ValueError('Invalid semantic lineage record: '+key)
                checker = importlib.import_module(core.__package__ + '.semantic')
                check = checker.validate(graph, source_packet, semantic['source_packet']['sha256'], proposals, ref)
                save(folder / 'semantic_structural_validation.json', check)
                assert check['passed'] and check['source_read_complete_self_report'], 'Source semantic stage is structurally invalid or incomplete'
                result['source_semantic_graph'] = graph
                result['source_semantic_lineage_complete'] = lineage_complete
                result['first_graph_identity_and_source_checked'] = lineage_complete
                result['historical_first_capture_priority_not_independently_certified'] = True
                result['semantic_stage_input_provenance'] = semantic
                result['active_primary_process_graph'] = 'source_semantic_graph'
                result['native_process_context_retained_as_revision_lineage_not_second_active_graph'] = True
                result['unconfirmed_native_claims_still_active_for_output_support'] = checker.retained_unknown_native_claims(graph, original)
                result['unlisted_property_process_contexts_remain_active'] = True
                result['complete_semantic_source_support_not_certified_by_structural_validation'] = True
                for kind in ['material_identities', 'states', 'operations', 'parameters', 'orders', 'bindings']:
                    result['counts']['semantic_' + kind] = len(graph[kind])
                result['counts']['semantic_unconfirmed_native_claims'] = len(result['unconfirmed_native_claims_still_active_for_output_support'])
            result['reference_no'] = ref
            validation = validate_result(result, original, common)
            if completion is not None:
                result = completion.complete_native_owners(result, original,
                    native_source=entry['native_final'])
                validation['native_owner_completion'] = dict(version=completion.VERSION,
                    additional_owner_contexts=len(result[completion.COLLECTION]),
                    original_prediction_fields_preserved=True,
                    source_file_sha256_rechecked_before_publication=True,
                    scientific_source_support_not_certified=True)
            for key in ['native_final', 'stage0']:
                assert sha(entry[key]['path']) == entry[key]['sha256']
            check_entry_inputs(entry)
            save(folder / 'prediction.json', result)
            save(folder / 'structural_validation.json', validation)
            status = dict(reference_no=ref, status='completed', started_utc=started, ended_utc=utc(),
                prediction_sha256=sha(folder / 'prediction.json'),
                structural_validation_sha256=sha(folder / 'structural_validation.json'),
                counts=result['counts'], external_api_calls=0,
                extraction_semantic_accuracy_not_certified=True)
            if entry.get('semantic'):
                status['semantic_structural_validation_sha256']=sha(folder/'semantic_structural_validation.json')
        except Exception as error:
            status = dict(reference_no=ref, status='failed', started_utc=started, ended_utc=utc(),
                error_type=type(error).__name__, error=str(error), external_api_calls=0)
        save(status_file, status)
        print(json.dumps(dict(reference_no=ref, status=status['status']), ensure_ascii=False), flush=True)
        return status

    with concurrent.futures.ThreadPoolExecutor(max_workers=max(1, args.workers)) as executor:
        statuses = list(executor.map(one, papers))
    totals = Counter()
    for status in statuses:
        if status['status'] == 'completed':
            totals.update(status['counts'])
    failures = [s for s in statuses if s['status'] != 'completed']
    summary = dict(paper_count=len(statuses), completed=len(statuses) - len(failures), failed=len(failures),
        counts=dict(totals), papers=statuses, external_api_calls=0,
        native_property_files_unchanged=not failures,
        reference_coverage=None, output_source_support=None,
        semantic_evaluation_complete=False, whole_research_task_complete=False)
    save(output / 'execution_summary.json', summary)
    save(output / 'process_access_log.json', dict(accesses=dict(sorted(accessed.items())), denied_attempts=denied,
        os_hard_isolation=False, python_audit_hook_is_not_an_os_security_boundary=True,
        no_network_access_permitted=True, reference_files_not_in_input_allowlist=True))
    if not failures:
        save(output / 'freeze.json', dict(files=[dict(path=str(p), sha256=sha(p))
            for p in sorted(output.rglob('*')) if p.is_file() and '__pycache__' not in p.parts
            and p.name != 'freeze.json'], predictions_frozen_before_semantic_scoring=True,
            external_api_calls=0, five_dimension_metrics_computed=False))
    print(json.dumps(dict(event='cache_recovery_finished', papers=len(statuses),
        completed=summary['completed'], failed=len(failures), external_api_calls=0), ensure_ascii=False))
    return 1 if failures else 0


if __name__ == '__main__':
    raise SystemExit(main())
