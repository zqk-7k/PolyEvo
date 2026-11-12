"""从 PDF 到结构化报告的统一流水线入口。"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path
from typing import Sequence


CODE_ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = CODE_ROOT.parent
OCR_ROOT = CODE_ROOT / "ocr"
EXTRACTION_ROOT = CODE_ROOT / "extraction"
MINERU_SCRIPT = OCR_ROOT / "mineru_batch_parse.py"
BATCH_SCRIPT = EXTRACTION_ROOT / "batch_runner.py"
DEFAULT_CONFIG = EXTRACTION_ROOT / "config" / "pipeline.yaml"

for module_root in (OCR_ROOT, EXTRACTION_ROOT):
    if str(module_root) not in sys.path:
        sys.path.insert(0, str(module_root))

from mineru_batch_parse import normalize_ref_no, select_pdfs  # noqa: E402
from stage_minus1_reorganize_mineru import reorganize_paper  # noqa: E402
from transform_mineru_to_standard import (  # noqa: E402
    ConfiguredMetaExtractor,
    MetaExtractor,
    transform_paper,
)


class PipelineRunnerError(RuntimeError):
    """统一流水线的参数或阶段执行错误。"""


def run_command(command: Sequence[str], *, label: str) -> None:
    print(f"\n[{label}] " + subprocess.list2cmdline(list(command)))
    completed = subprocess.run(list(command), cwd=PROJECT_ROOT, check=False)
    if completed.returncode != 0:
        raise PipelineRunnerError(f"{label} 失败，退出码 {completed.returncode}")


def _batch_ref_nos(mineru_output: Path, batch_id: str) -> list[str]:
    manifest_path = mineru_output / f"batch_{batch_id}_manifest.json"
    status_path = mineru_output / f"batch_{batch_id}_status.json"
    candidates: list[str] = []
    if manifest_path.is_file():
        payload = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
        candidates = [str(value) for value in payload.get("files") or []]
    elif status_path.is_file():
        payload = json.loads(status_path.read_text(encoding="utf-8-sig"))
        results = ((payload.get("data") or {}).get("extract_result") or [])
        candidates = [str(item.get("file_name") or "") for item in results]
    if not candidates:
        raise PipelineRunnerError(
            f"无法从批次清单或状态文件确定文献：batch_id={batch_id}"
        )
    return list(dict.fromkeys(normalize_ref_no(value) for value in candidates))


def build_mineru_command(
    args: argparse.Namespace,
    *,
    input_dir: Path,
    mineru_output: Path,
    ref_nos: Sequence[str],
) -> list[str]:
    command = [
        sys.executable,
        str(MINERU_SCRIPT),
        "--input-dir",
        str(input_dir),
        "--output-dir",
        str(mineru_output),
        "--env-file",
        str(args.env_file.expanduser().resolve()),
        "--model-version",
        args.model_version,
        "--timeout-minutes",
        str(args.timeout_minutes),
    ]
    if args.batch_id:
        command.extend(("--batch-id", args.batch_id))
    else:
        for ref_no in ref_nos:
            command.extend(("--ref-no", ref_no))
    if args.ocr:
        command.append("--ocr")
    if args.language:
        command.extend(("--language", args.language))
    if args.disable_formula:
        command.append("--disable-formula")
    if args.disable_table:
        command.append("--disable-table")
    return command


def build_extraction_command(
    args: argparse.Namespace,
    *,
    processed_output: Path,
    ref_nos: Sequence[str],
) -> list[str]:
    command = [
        sys.executable,
        str(BATCH_SCRIPT),
        "--config",
        str(args.config.expanduser().resolve()),
        "--input-dir",
        str(processed_output / "documents"),
    ]
    for ref_no in ref_nos:
        command.extend(("--ref-no", ref_no))
    optional_paths = (
        ("--output-dir", args.output_dir),
        ("--state-db", args.state_db),
        ("--summary-out", args.summary_out),
    )
    for option, value in optional_paths:
        if value is not None:
            command.extend((option, str(value.expanduser().resolve())))
    if args.workers is not None:
        command.extend(("--workers", str(args.workers)))
    if args.llm_workers is not None:
        command.extend(("--llm-workers", str(args.llm_workers)))
    for flag in ("retry_failed", "retry_interrupted", "recheck_completed", "force"):
        if getattr(args, flag):
            command.append("--" + flag.replace("_", "-"))
    if args.preview:
        command.append("--preview")
    return command


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="串联 MinerU、标准化转换和 Stage 0-6 抽取",
    )
    parser.add_argument("--input-dir", type=Path, required=True, help="PDF 文件夹")
    parser.add_argument("--mineru-output", type=Path)
    parser.add_argument("--organized-root", type=Path, default=PROJECT_ROOT / "wenxian")
    parser.add_argument("--processed-output", type=Path, default=PROJECT_ROOT / "processed_data")
    parser.add_argument("--output-dir", type=Path, help="Stage 0-6 输出目录；默认读取配置")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--env-file", type=Path, default=OCR_ROOT / ".env")

    selection = parser.add_mutually_exclusive_group()
    selection.add_argument("--ref-no", action="append", help="只处理指定文献，可重复")
    selection.add_argument("--ref-list", type=Path, help="每行一个文献编号的清单")
    selection.add_argument("--max-documents", type=int, help="最多处理排序后的前 N 篇")

    parser.add_argument("--batch-id", help="继续已有 MinerU 批次")
    parser.add_argument("--model-version", choices=("pipeline", "vlm"), default="vlm")
    parser.add_argument("--language")
    parser.add_argument("--ocr", action="store_true", help="为扫描型 PDF 启用 OCR")
    parser.add_argument("--disable-formula", action="store_true")
    parser.add_argument("--disable-table", action="store_true")
    parser.add_argument("--timeout-minutes", type=float, default=120.0)

    parser.add_argument("--skip-ocr", action="store_true", help="复用已有 MinerU 结果")
    parser.add_argument("--skip-organize", action="store_true", help="复用已有 Stage -1 结果")
    parser.add_argument("--skip-transform", action="store_true", help="复用已有 document JSON")
    parser.add_argument("--skip-extraction", action="store_true", help="只运行到 document JSON")
    parser.add_argument("--skip-meta", action="store_true", help="标准化时不调用元数据 LLM")
    parser.add_argument("--force-meta", action="store_true")

    parser.add_argument("--workers", type=int)
    parser.add_argument("--llm-workers", type=int)
    parser.add_argument("--state-db", type=Path)
    parser.add_argument("--summary-out", type=Path)
    parser.add_argument("--retry-failed", action="store_true")
    parser.add_argument("--retry-interrupted", action="store_true")
    parser.add_argument("--recheck-completed", action="store_true")
    parser.add_argument("--force", action="store_true")
    parser.add_argument(
        "--preview",
        action="store_true",
        help="Stage 5 后发布 candidate.json 和 report_candidate.html，不执行 Stage 6 严格校验",
    )
    parser.add_argument("--dry-run", action="store_true", help="只打印计划，不执行")
    parser.add_argument("--process-recovery-output", type=Path,
                        help="在独立目录运行通用工艺整理；保留原性质文件")
    parser.add_argument("--process-cache-root", type=Path,
                        help="已有各文献final.json/stage0_blocks.json所在父目录")
    parser.add_argument("--process-recovery-manifest", type=Path,
                        help="显式冻结的工艺输入清单，可包含来源语义图；须与所选论文完全一致")
    parser.add_argument("--process-recovery-only", action="store_true",
                        help="仅对已有缓存执行工艺整理，跳过OCR、标准化和模型抽取")
    parser.add_argument("--process-workflow", choices=("cache-v2", "general158", "complete158", "consistent158", "verified158"), default="cache-v2",
                        help="工艺实现版本；general158包含通用原文语义处理协议")
    parser.add_argument("--process-stage", choices=("prepare", "publish"),
                        help="general158：准备逐篇任务，或接收实际模型响应并发布")
    parser.add_argument("--process-tasks", type=Path, help="general158准备阶段的prepared_tasks.json")
    parser.add_argument("--process-responses", type=Path, help="实际模型逐篇响应所在目录")
    return parser


def run_process_recovery(args: argparse.Namespace, ref_nos: Sequence[str]) -> None:
    """Pass hash-bound cache/semantic inputs to the network-free runner."""
    target = args.process_recovery_output.expanduser().resolve()
    if target.exists():
        raise PipelineRunnerError(f"工艺输出目录已存在，请保留并指定新目录：{target}")
    if args.process_recovery_manifest is not None:
        manifest = args.process_recovery_manifest.expanduser().resolve()
        payload = json.loads(manifest.read_text(encoding="utf-8-sig"))
        ids = [row["reference_no"] for row in payload["papers"]]
        if len(ids) != len(set(ids)) or set(ids) != set(ref_nos):
            raise PipelineRunnerError("显式工艺清单必须与所选论文完全一致，不能删减、追加或重复论文")
    else:
        cache_root = (args.process_cache_root or args.output_dir).expanduser().resolve()
        papers = []
        for ref_no in ref_nos:
            folder = cache_root / ref_no
            final = folder / ("candidate.json" if args.preview else "final.json")
            stage0 = folder / "stage0_blocks.json"
            missing = [str(path) for path in (final, stage0) if not path.is_file()]
            if missing:
                raise PipelineRunnerError("工艺整理缺少原生缓存：" + "、".join(missing))
            def witness(path: Path) -> dict:
                return {"path": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
            papers.append({"reference_no": ref_no, "native_final": witness(final), "stage0": witness(stage0)})
        manifest = target.parent / (target.name + "_input_manifest.json")
        if manifest.exists():
            raise PipelineRunnerError(f"输入清单已存在，不能覆盖：{manifest}")
        manifest.parent.mkdir(parents=True, exist_ok=True)
        manifest_payload = {"papers": papers}
        if args.process_workflow == "cache-v2":
            manifest_payload.update(source="pipeline_process_recovery_hook", no_reference_or_score_inputs=True)
        manifest.write_text(json.dumps(manifest_payload, ensure_ascii=False, indent=2) + "\n",
                            encoding="utf-8")
    command = [sys.executable, "-X", "utf8", str(CODE_ROOT / "process_workflow_runner.py"),
               "--manifest", str(manifest), "--output", str(target),
               "--workers", str(args.workers or 4), "--workflow", args.process_workflow]
    if args.process_stage is not None:
        command += ["--stage", args.process_stage]
    if args.process_tasks is not None:
        command += ["--tasks", str(args.process_tasks)]
    if args.process_responses is not None:
        command += ["--responses", str(args.process_responses)]
    run_command(command, label="通用工艺缓存整理（无API）")


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.process_workflow in {'consistent158','verified158'} and args.process_recovery_manifest is None:
        raise PipelineRunnerError('独立来源检查需要包含source-only种子响应、packet及同源prior的显式工艺清单；consistent158使用complete158种子，verified158使用consistent158种子，不能跳过前序输入。')
    if args.process_recovery_only:
        if args.process_recovery_output is None:
            raise PipelineRunnerError("--process-recovery-only需要--process-recovery-output")
        args.skip_ocr = args.skip_organize = args.skip_transform = args.skip_extraction = args.skip_meta = True
    if args.process_recovery_manifest is not None and args.process_recovery_output is None:
        raise PipelineRunnerError("--process-recovery-manifest需要--process-recovery-output")
    if args.process_recovery_manifest is not None and args.process_cache_root is not None:
        raise PipelineRunnerError("显式工艺清单和--process-cache-root不能同时指定")
    if (args.process_recovery_output is not None and args.process_recovery_manifest is None
            and args.process_cache_root is None and args.output_dir is None):
        raise PipelineRunnerError("工艺整理须显式指定缓存目录或输入清单，不猜测缓存目录")
    input_dir = args.input_dir.expanduser().resolve()
    mineru_output = (
        args.mineru_output.expanduser().resolve()
        if args.mineru_output
        else input_dir / "mineru_output"
    )
    organized_root = args.organized_root.expanduser().resolve()
    processed_output = args.processed_output.expanduser().resolve()

    if args.batch_id and (args.ref_no or args.ref_list or args.max_documents):
        raise PipelineRunnerError("--batch-id 不能与文献选择参数同时使用")
    if args.batch_id:
        ref_nos = []
        if args.skip_ocr:
            ref_nos = _batch_ref_nos(mineru_output, args.batch_id)
    else:
        pdf_files = select_pdfs(
            input_dir,
            ref_nos=args.ref_no,
            ref_list_path=args.ref_list,
            max_documents=args.max_documents,
        )
        ref_nos = [normalize_ref_no(path.name) for path in pdf_files]

    if ref_nos:
        print(f"已选择 {len(ref_nos)} 篇：" + ", ".join(ref_nos))

    mineru_command = build_mineru_command(
        args,
        input_dir=input_dir,
        mineru_output=mineru_output,
        ref_nos=ref_nos,
    )
    if args.dry_run:
        if not ref_nos and args.batch_id:
            print("文献清单将在 MinerU 批次恢复完成后从状态文件读取。")
        if not args.skip_ocr:
            print("[dry-run: MinerU] " + subprocess.list2cmdline(mineru_command))
        if not ref_nos:
            print("[dry-run] 后续命令将在取得批次文献清单后生成。")
            return 0
        extraction_command = build_extraction_command(
            args,
            processed_output=processed_output,
            ref_nos=ref_nos,
        )
        if not args.skip_organize:
            print(f"[dry-run: Stage -1] {len(ref_nos)} 篇 -> {organized_root}")
        if not args.skip_transform:
            print(f"[dry-run: 标准化] {len(ref_nos)} 篇 -> {processed_output / 'documents'}")
        if not args.skip_extraction:
            label = "Stage 0-5 + Candidate" if args.preview else "Stage 0-6"
            print(f"[dry-run: {label}] " + subprocess.list2cmdline(extraction_command))
        if args.process_recovery_output is not None:
            print(f"[dry-run: 通用工艺缓存整理，无API] {len(ref_nos)} 篇 -> {args.process_recovery_output}")
        return 0

    if not args.skip_ocr:
        run_command(mineru_command, label="MinerU")
    if args.batch_id and not ref_nos:
        ref_nos = _batch_ref_nos(mineru_output, args.batch_id)

    if args.batch_id:
        print(f"批次包含 {len(ref_nos)} 篇：" + ", ".join(ref_nos))

    if not args.skip_organize:
        print("\n[Stage -1] 整理 MinerU 产物")
        for ref_no in ref_nos:
            stats = reorganize_paper(mineru_output, organized_root, ref_no)
            errors = stats.get("errors") or []
            if errors:
                raise PipelineRunnerError(f"Stage -1 失败：{ref_no}：{'；'.join(errors)}")
            print(f"[done] {ref_no}")

    if not args.skip_transform:
        print("\n[标准化] 生成 document JSON")
        meta_extractor: MetaExtractor | None = None
        if not args.skip_meta:
            try:
                meta_extractor = ConfiguredMetaExtractor(args.config.expanduser().resolve())
            except Exception as exc:
                raise PipelineRunnerError(
                    "元数据 LLM 初始化失败；如需明确跳过，请使用 --skip-meta"
                ) from exc
        for ref_no in ref_nos:
            output = transform_paper(
                mineru_output,
                organized_root,
                processed_output,
                ref_no,
                force_meta=args.force_meta,
                meta_extractor=meta_extractor,
            )
            if not args.skip_meta:
                try:
                    document = json.loads(output.read_text(encoding="utf-8-sig"))
                    extraction = document["paper"]["metadata_extraction"]
                except (OSError, json.JSONDecodeError, KeyError, TypeError) as exc:
                    raise PipelineRunnerError(
                        f"元数据抽取结果无法审计：{ref_no}"
                    ) from exc
                if extraction.get("status") != "success":
                    error_type = extraction.get("error_type") or "unknown"
                    raise PipelineRunnerError(
                        f"元数据抽取失败：{ref_no}（{error_type}）；"
                        "如需明确跳过，请使用 --skip-meta"
                    )
            print(f"[done] {ref_no} -> {output}")

    if not args.skip_extraction:
        extraction_command = build_extraction_command(
            args,
            processed_output=processed_output,
            ref_nos=ref_nos,
        )
        label = "Stage 0-5 + Candidate" if args.preview else "Stage 0-6"
        run_command(extraction_command, label=label)
    if args.process_recovery_output is not None:
        run_process_recovery(args, ref_nos)
    if args.process_recovery_only:
        print("\n离线工艺缓存整理完成；未执行模型抽取。")
    elif args.preview:
        print("\nPreview 流水线执行完成。")
    else:
        print("\n完整流水线执行完成。")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print("\n用户中止。", file=sys.stderr)
        raise SystemExit(130)
    except Exception as exc:
        print(f"错误：{exc}", file=sys.stderr)
        raise SystemExit(1)
