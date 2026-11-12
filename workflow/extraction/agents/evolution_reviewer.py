"""Independent, fail-closed review Agent for controlled extraction evolution.

The reviewer evaluates one already-locked workflow candidate.  It never applies a
patch and never decides the final release: an ``approve`` decision only permits
the deterministic Harness to run.  Credentials remain inside :class:`LLMClient`
and are deliberately absent from every returned artifact.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
from collections.abc import Mapping, Sequence
from decimal import Decimal
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from llm_client import (
    DEFAULT_CONFIG_PATH,
    LLMClient,
    load_pipeline_config,
    summarize_client_calls,
)
from prompt_loader import PromptLoader, RenderedPrompt


AGENT_STAGE = "evolution_reviewer"
PROMPT_ID = "polymer.evolution.review"
SCHEMA_VERSION = "evolution_reviewer_schema.v1"
ARTIFACT_SCHEMA_VERSION = "evolution_reviewer_artifact.v1"
DEFAULT_ENV_PATH = Path(__file__).resolve().parents[2] / ".env"
DEFAULT_CLAUDE_CODE_BASE_URL = "https://gocollm.pro"
DEFAULT_CLAUDE_CODE_MODEL = "claude-opus-5"

ReviewDecision = Literal["approve", "reject", "disputed"]
IssueSeverity = Literal["critical", "major", "minor"]
IssueCategory = Literal[
    "scientific_semantics",
    "evidence_support",
    "sample_binding",
    "value_or_unit",
    "scope_or_gold_leakage",
    "regression_risk",
    "test_coverage",
    "implementation_safety",
    "runtime_failure",
    "other",
]


_SENSITIVE_FIELD_NAMES = frozenset({
    "api_key",
    "apikey",
    "authorization",
    "x_api_key",
    "anthropic_api_key",
    "gocollm_api_key",
    "claude_code_api_key",
    "dmx_api_key",
    "llm_api_key",
    "openai_api_key",
    "access_token",
    "bearer_token",
    "password",
    "secret",
})


class ClaudeCodeCLIError(RuntimeError):
    """A secret-free, phase-classified Claude Code transport failure."""

    def __init__(
        self,
        message: str,
        *,
        error_code: str,
        diagnostics: Mapping[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.error_code = error_code
        self.safe_diagnostics = dict(diagnostics or {})


class EvolutionReviewIssue(BaseModel):
    """One independently identified defect or residual concern."""

    model_config = ConfigDict(extra="forbid")

    issue_id: str = Field(min_length=1, max_length=96)
    category: IssueCategory
    severity: IssueSeverity
    summary: str = Field(min_length=1, max_length=1500)
    evidence_ids: list[str] = Field(default_factory=list)
    affected_artifact_ids: list[str] = Field(default_factory=list)
    recommendation: str = Field(min_length=1, max_length=1500)

    @model_validator(mode="after")
    def require_evidence_for_scientific_issue(self) -> "EvolutionReviewIssue":
        if self.category != "runtime_failure" and not self.evidence_ids:
            raise ValueError("non-runtime review issue requires at least one evidence_id")
        return self


class EvolutionReviewResponse(BaseModel):
    """Strict Claude response contract used before deterministic release tests."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["evolution_reviewer_schema.v1"] = SCHEMA_VERSION
    review_id: str = Field(min_length=1, max_length=160)
    decision: ReviewDecision
    issues: list[EvolutionReviewIssue] = Field(default_factory=list)
    rationale: str = Field(min_length=1, max_length=5000)
    requires_expert_review: bool

    @model_validator(mode="after")
    def enforce_decision_policy(self) -> "EvolutionReviewResponse":
        has_critical = any(item.severity == "critical" for item in self.issues)
        if self.decision == "approve" and has_critical:
            raise ValueError("critical issue forbids approval")
        if self.decision == "approve" and self.requires_expert_review:
            raise ValueError("approve cannot require expert review")
        if self.decision == "disputed" and not self.requires_expert_review:
            raise ValueError("disputed decision requires expert review")
        if self.decision != "disputed" and self.requires_expert_review:
            raise ValueError("expert review must use the disputed decision")
        if self.decision in {"reject", "disputed"} and not self.issues:
            raise ValueError("reject or disputed decision requires at least one issue")
        return self


def _normalized_field_name(value: Any) -> str:
    return str(value).strip().casefold().replace("-", "_")


def _assert_no_secret_fields(value: Any, *, path: str = "request") -> None:
    """Reject accidental credential-bearing inputs before an external call."""

    if isinstance(value, Mapping):
        for key, item in value.items():
            normalized = _normalized_field_name(key)
            if normalized in _SENSITIVE_FIELD_NAMES:
                raise ValueError(f"sensitive field is forbidden in reviewer input: {path}.{key}")
            _assert_no_secret_fields(item, path=f"{path}.{key}")
    elif isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        for index, item in enumerate(value):
            _assert_no_secret_fields(item, path=f"{path}[{index}]")


def load_dmx_api_key_env(env_path: Path | None = DEFAULT_ENV_PATH) -> bool:
    """Load only DMX_API_KEY from an ignored local .env without exposing it.

    An already defined process variable always wins.  The function intentionally
    returns only readiness, never the credential value.
    """

    if os.environ.get("DMX_API_KEY", "").strip():
        return True
    if env_path is None or not env_path.is_file():
        return False
    for raw_line in env_path.read_text(encoding="utf-8-sig").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        name, value = line.split("=", 1)
        if name.strip() != "DMX_API_KEY":
            continue
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]
        if value:
            os.environ["DMX_API_KEY"] = value
            return True
        return False
    return False


def load_claude_code_api_env(env_path: Path | None = DEFAULT_ENV_PATH) -> bool:
    """Load a Claude Code credential without ever returning its value.

    ``ANTHROPIC_API_KEY`` is the credential consumed by ``claude --bare``.
    For local convenience an ignored ``.env`` may instead define
    ``GOCOLLM_API_KEY``; that value is copied only into the current process.
    No credential is written to a command line, artifact, or child output.
    """

    if os.environ.get("ANTHROPIC_API_KEY", "").strip():
        return True
    if os.environ.get("GOCOLLM_API_KEY", "").strip():
        os.environ["ANTHROPIC_API_KEY"] = os.environ["GOCOLLM_API_KEY"].strip()
        return True
    if env_path is None or not env_path.is_file():
        return False
    for raw_line in env_path.read_text(encoding="utf-8-sig").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        name, value = line.split("=", 1)
        if name.strip() not in {"ANTHROPIC_API_KEY", "GOCOLLM_API_KEY"}:
            continue
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]
        if value:
            os.environ["ANTHROPIC_API_KEY"] = value
            return True
        return False
    return False


def resolve_claude_code_executable(explicit: Path | str | None = None) -> Path:
    """Resolve the native Claude Code executable, never a shell wrapper."""

    candidates: list[Path] = []
    if explicit is not None:
        candidates.append(Path(explicit))
    configured = os.environ.get("CLAUDE_CODE_EXECUTABLE", "").strip()
    if configured:
        candidates.append(Path(configured))
    discovered = shutil.which("claude.exe")
    if discovered:
        candidates.append(Path(discovered))
    appdata = os.environ.get("APPDATA", "").strip()
    if appdata:
        candidates.append(
            Path(appdata)
            / "npm"
            / "node_modules"
            / "@anthropic-ai"
            / "claude-code"
            / "bin"
            / "claude.exe"
        )
    for candidate in candidates:
        resolved = candidate.expanduser().resolve()
        if resolved.is_file() and resolved.suffix.casefold() == ".exe":
            return resolved
    raise ClaudeCodeCLIError(
        "Claude Code native executable is unavailable",
        error_code="cli_executable_unavailable",
        diagnostics={"phase": "resolve_executable"},
    )


def build_review_request(
    *,
    review_id: str,
    candidate_change: Mapping[str, Any],
    evidence: Sequence[Mapping[str, Any]],
    diagnostics: Mapping[str, Any] | None = None,
    release_policy: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Build the bounded request and freeze the evidence-ID whitelist."""

    normalized_review_id = str(review_id).strip()
    if not normalized_review_id:
        raise ValueError("review_id is required")
    if len(normalized_review_id) > 160:
        raise ValueError("review_id exceeds 160 characters")
    evidence_rows: list[dict[str, Any]] = []
    evidence_ids: list[str] = []
    for index, source in enumerate(evidence):
        if not isinstance(source, Mapping):
            raise ValueError(f"evidence[{index}] must be a mapping")
        row = dict(source)
        evidence_id = str(row.get("evidence_id") or "").strip()
        if not evidence_id:
            raise ValueError(f"evidence[{index}] is missing evidence_id")
        if evidence_id in evidence_ids:
            raise ValueError(f"duplicate evidence_id: {evidence_id}")
        row["evidence_id"] = evidence_id
        evidence_ids.append(evidence_id)
        evidence_rows.append(row)

    request = {
        "input_schema_version": "evolution_reviewer_input.v1",
        "review_id": normalized_review_id,
        "candidate_change": dict(candidate_change),
        "diagnostics": dict(diagnostics or {}),
        "release_policy": dict(release_policy or {}),
        "allowed_evidence_ids": evidence_ids,
        "evidence": evidence_rows,
        "review_boundary": {
            "reviewer_may_apply_changes": False,
            "reviewer_may_release": False,
            "holdout_answers_available": False,
            "approval_only_allows_deterministic_harness": True,
        },
    }
    _assert_no_secret_fields(request)
    # Fail before the model call if a caller supplied a non-JSON runtime object.
    json.dumps(request, ensure_ascii=False, sort_keys=True)
    return request


def validate_review_response(
    data: Mapping[str, Any],
    request: Mapping[str, Any],
) -> EvolutionReviewResponse:
    """Validate response structure, review identity and all evidence references."""

    response = EvolutionReviewResponse.model_validate(data)
    if response.review_id != request.get("review_id"):
        raise ValueError("review_id mismatch")
    if any(item.category == "runtime_failure" for item in response.issues):
        raise ValueError("runtime_failure is reserved for deterministic fail-closed artifacts")
    allowed = {str(value) for value in request.get("allowed_evidence_ids") or []}
    referenced = {
        evidence_id
        for issue in response.issues
        for evidence_id in issue.evidence_ids
    }
    unknown = sorted(referenced - allowed)
    if unknown:
        raise ValueError(f"reviewer referenced unknown evidence IDs: {unknown}")
    return response


def _settings(config_path: Path) -> dict[str, Any]:
    config = load_pipeline_config(config_path)
    stages = config.get("stages") or {}
    value = stages.get(AGENT_STAGE) if isinstance(stages, Mapping) else None
    return dict(value) if isinstance(value, Mapping) else {}


def _json_safe(value: Any) -> Any:
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, Mapping):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    return value


def _safe_runtime_summary(client: LLMClient | None, history_start: int) -> dict[str, Any]:
    if client is None:
        return {"usage": None, "cost": {"status": "unavailable"}}
    try:
        call_history = getattr(client, "call_history", [])
        call_count = max(0, len(call_history) - history_start)
        usage, cost = summarize_client_calls(
            client,
            history_start,
            call_count=call_count,
        )
    except Exception:
        usage, cost = None, {"status": "unavailable"}
    resolved = getattr(client, "resolved", None)
    return _json_safe({
        "provider": getattr(resolved, "provider", None),
        "model": getattr(resolved, "model", None),
        "usage": usage,
        "cost": cost,
    })


def _failed_closed_response(review_id: str, error_type: str) -> EvolutionReviewResponse:
    safe_review_id = str(review_id).strip()[:160] or "unknown-review"
    return EvolutionReviewResponse(
        review_id=safe_review_id,
        decision="reject",
        issues=[EvolutionReviewIssue(
            issue_id="reviewer_runtime_failure",
            category="runtime_failure",
            severity="critical",
            summary="Independent reviewer did not produce a valid, verified decision.",
            evidence_ids=[],
            affected_artifact_ids=[],
            recommendation=(
                "Do not promote the candidate; repair the reviewer run and "
                "review again."
            ),
        )],
        rationale=(
            "Fail-closed policy rejected promotion because independent review failed "
            f"({error_type})."
        ),
        requires_expert_review=False,
    )


def _request_digest(request: Mapping[str, Any] | None) -> str | None:
    if request is None:
        return None
    serialized = json.dumps(
        request,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def _safe_error_code(error: Exception) -> str | None:
    value = getattr(error, "error_code", None)
    if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9_.-]{1,64}", value):
        return None
    return value


def _safe_validation_errors(error: Exception) -> list[dict[str, Any]]:
    if not hasattr(error, "errors"):
        return []
    try:
        rows = error.errors(include_input=False, include_context=False)
    except Exception:
        return []
    safe: list[dict[str, Any]] = []
    for row in rows[:20]:
        safe.append({
            "type": str(row.get("type") or "validation_error")[:96],
            "loc": [str(item)[:96] for item in row.get("loc") or []],
            "msg": str(row.get("msg") or "invalid response")[:240],
        })
    return safe


def _safe_cli_diagnostics(error: Exception) -> dict[str, Any]:
    value = getattr(error, "safe_diagnostics", None)
    if not isinstance(value, Mapping):
        return {}
    allowed = {
        "phase",
        "exit_code",
        "timed_out",
        "stdout_bytes",
        "stderr_bytes",
        "stdout_json",
        "is_error",
        "api_error_status_present",
        "structured_output_present",
        "model_usage_present",
    }
    return {
        str(key): _json_safe(item)
        for key, item in value.items()
        if str(key) in allowed
    }


def _nonnegative_int(value: Any) -> int:
    if isinstance(value, bool):
        return 0
    try:
        return max(0, int(value))
    except (TypeError, ValueError):
        return 0


def run_evolution_review_cli(
    *,
    review_id: str,
    candidate_change: Mapping[str, Any],
    evidence: Sequence[Mapping[str, Any]],
    diagnostics: Mapping[str, Any] | None = None,
    release_policy: Mapping[str, Any] | None = None,
    env_path: Path | None = DEFAULT_ENV_PATH,
    prompt_loader: PromptLoader | None = None,
    cli_executable: Path | str | None = None,
    cli_model: str = DEFAULT_CLAUDE_CODE_MODEL,
    cli_base_url: str = DEFAULT_CLAUDE_CODE_BASE_URL,
    cli_timeout_seconds: int = 600,
    subprocess_runner: Any = subprocess.run,
) -> dict[str, Any]:
    """Run one locked review through Claude Code CLI and fail closed.

    The frozen review request is sent over stdin so large evidence bundles do
    not enter the Windows command line.  The API key is inherited only through
    the child environment.  ``--bare`` disables keychain/session/customization
    discovery, while an empty tool list prevents the reviewer from inspecting
    anything outside the enumerated request.
    """

    request: dict[str, Any] | None = None
    rendered: RenderedPrompt | None = None
    runtime: dict[str, Any] = {
        "transport": "claude-code-cli",
        "provider": "gocollm",
        "model": cli_model,
        "usage": None,
        "cost": {"status": "unavailable", "currency": "USD"},
        "call_count": 0,
    }
    try:
        request = build_review_request(
            review_id=review_id,
            candidate_change=candidate_change,
            evidence=evidence,
            diagnostics=diagnostics,
            release_policy=release_policy,
        )
        rendered = (prompt_loader or PromptLoader()).render_stage_prompt(
            PROMPT_ID,
            EvolutionReviewResponse,
            expected_stage=AGENT_STAGE,
            expected_output_schema=SCHEMA_VERSION,
        )
        if not load_claude_code_api_env(env_path):
            raise ClaudeCodeCLIError(
                "Claude Code credential is unavailable",
                error_code="cli_credential_unavailable",
                diagnostics={"phase": "load_credential"},
            )
        executable = resolve_claude_code_executable(cli_executable)
        model = str(cli_model).strip()
        base_url = str(cli_base_url).strip().rstrip("/")
        if not model or not base_url.startswith("https://"):
            raise ClaudeCodeCLIError(
                "Claude Code runtime configuration is invalid",
                error_code="cli_runtime_config_invalid",
                diagnostics={"phase": "validate_runtime"},
            )
        timeout_seconds = int(cli_timeout_seconds)
        if timeout_seconds < 1:
            raise ClaudeCodeCLIError(
                "Claude Code timeout is invalid",
                error_code="cli_timeout_invalid",
                diagnostics={"phase": "validate_runtime"},
            )

        schema_json = json.dumps(
            EvolutionReviewResponse.model_json_schema(),
            ensure_ascii=False,
            separators=(",", ":"),
        )
        command = [
            str(executable),
            "--bare",
            "--print",
            "--model",
            model,
            "--permission-mode",
            "plan",
            "--output-format",
            "json",
            "--json-schema",
            schema_json,
            "--no-session-persistence",
            "--disable-slash-commands",
            "--tools=",
            "--system-prompt",
            rendered.text,
        ]
        child_env = dict(os.environ)
        child_env["ANTHROPIC_BASE_URL"] = base_url
        # ``--bare`` reads only ANTHROPIC_API_KEY; never place it in ``command``.
        creationflags = (
            getattr(subprocess, "CREATE_NO_WINDOW", 0) if os.name == "nt" else 0
        )
        try:
            completed = subprocess_runner(
                command,
                input=json.dumps(
                    request,
                    ensure_ascii=False,
                    separators=(",", ":"),
                ),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=timeout_seconds,
                check=False,
                env=child_env,
                cwd=str(Path.cwd()),
                creationflags=creationflags,
            )
        except subprocess.TimeoutExpired as exc:
            raise ClaudeCodeCLIError(
                "Claude Code review timed out",
                error_code="cli_timeout",
                diagnostics={
                    "phase": "invoke",
                    "timed_out": True,
                    "stdout_bytes": len((exc.stdout or "").encode("utf-8")),
                    "stderr_bytes": len((exc.stderr or "").encode("utf-8")),
                },
            ) from None

        stdout = completed.stdout or ""
        stderr = completed.stderr or ""
        base_diagnostics = {
            "phase": "decode_wrapper",
            "exit_code": int(completed.returncode),
            "timed_out": False,
            "stdout_bytes": len(stdout.encode("utf-8")),
            "stderr_bytes": len(stderr.encode("utf-8")),
        }
        if completed.returncode != 0:
            raise ClaudeCodeCLIError(
                "Claude Code returned a non-zero exit status",
                error_code="cli_nonzero_exit",
                diagnostics=base_diagnostics,
            )
        try:
            wrapper = json.loads(stdout)
        except json.JSONDecodeError:
            raise ClaudeCodeCLIError(
                "Claude Code wrapper output is not JSON",
                error_code="cli_wrapper_invalid_json",
                diagnostics=base_diagnostics | {"stdout_json": False},
            ) from None
        if not isinstance(wrapper, Mapping):
            raise ClaudeCodeCLIError(
                "Claude Code wrapper output is not an object",
                error_code="cli_wrapper_invalid_type",
                diagnostics=base_diagnostics | {"stdout_json": True},
            )
        wrapper_diagnostics = base_diagnostics | {
            "stdout_json": True,
            "is_error": wrapper.get("is_error") is True,
            "api_error_status_present": wrapper.get("api_error_status") is not None,
            "structured_output_present": isinstance(
                wrapper.get("structured_output"), Mapping
            ),
            "model_usage_present": isinstance(wrapper.get("modelUsage"), Mapping),
        }
        if wrapper.get("is_error") is True or wrapper.get("api_error_status") is not None:
            raise ClaudeCodeCLIError(
                "Claude Code reported an API error",
                error_code="cli_api_error",
                diagnostics=wrapper_diagnostics,
            )
        model_usage = wrapper.get("modelUsage")
        if not isinstance(model_usage, Mapping) or model not in model_usage:
            raise ClaudeCodeCLIError(
                "Claude Code did not attest the requested model",
                error_code="cli_model_identity_missing",
                diagnostics=wrapper_diagnostics,
            )
        structured_output = wrapper.get("structured_output")
        if not isinstance(structured_output, Mapping):
            raise ClaudeCodeCLIError(
                "Claude Code omitted structured output",
                error_code="cli_structured_output_missing",
                diagnostics=wrapper_diagnostics,
            )
        validated = validate_review_response(structured_output, request)

        raw_usage = wrapper.get("usage") or {}
        usage = {
            "input_tokens": _nonnegative_int(raw_usage.get("input_tokens")),
            "output_tokens": _nonnegative_int(raw_usage.get("output_tokens")),
            "cache_creation_input_tokens": _nonnegative_int(
                raw_usage.get("cache_creation_input_tokens")
            ),
            "cache_read_input_tokens": _nonnegative_int(
                raw_usage.get("cache_read_input_tokens")
            ),
        }
        usage["billable_input_tokens"] = (
            usage["input_tokens"]
            + usage["cache_creation_input_tokens"]
            + usage["cache_read_input_tokens"]
        )
        usage["total_tokens"] = usage["billable_input_tokens"] + usage["output_tokens"]
        reported_cost = wrapper.get("total_cost_usd")
        cost = {
            "status": "cli_reported" if isinstance(reported_cost, (int, float)) else "unavailable",
            "currency": "USD",
            "total_cost": str(reported_cost) if isinstance(reported_cost, (int, float)) else None,
            "interpretation": (
                "Claude Code wrapper value; third-party gateway billing remains external"
            ),
        }
        runtime = {
            "transport": "claude-code-cli",
            "provider": "gocollm",
            "model": model,
            "model_usage_keys": sorted(str(key) for key in model_usage),
            "usage": usage,
            "cost": cost,
            "call_count": 1,
            "duration_ms": _nonnegative_int(wrapper.get("duration_ms")),
            "duration_api_ms": _nonnegative_int(wrapper.get("duration_api_ms")),
            "num_turns": _nonnegative_int(wrapper.get("num_turns")),
            "executable": {
                "name": executable.name,
                "sha256": hashlib.sha256(executable.read_bytes()).hexdigest(),
            },
            "controls": {
                "bare": True,
                "tools_disabled": True,
                "session_persistence": False,
                "permission_mode": "plan",
                "request_via_stdin": True,
            },
        }
        artifact = {
            "schema_version": ARTIFACT_SCHEMA_VERSION,
            "status": "succeeded",
            "authoritative": False,
            "review_id": validated.review_id,
            "release_allowed": validated.decision == "approve",
            "response": validated.model_dump(mode="json"),
            "request": {
                "sha256": _request_digest(request),
                "candidate_id": candidate_change.get("candidate_id"),
                "allowed_evidence_ids": list(request["allowed_evidence_ids"]),
            },
            "prompt": {
                "id": rendered.prompt_id,
                "version": rendered.version,
                "sha256": rendered.sha256,
            },
            "runtime": runtime,
        }
        _assert_no_secret_fields(artifact, path="artifact")
        return artifact
    except Exception as exc:
        response = _failed_closed_response(str(review_id).strip(), type(exc).__name__)
        artifact = {
            "schema_version": ARTIFACT_SCHEMA_VERSION,
            "status": "failed_closed",
            "authoritative": False,
            "review_id": response.review_id,
            "release_allowed": False,
            "response": response.model_dump(mode="json"),
            "failure": {
                "error_type": type(exc).__name__,
                "error_code": _safe_error_code(exc),
                "validation_errors": _safe_validation_errors(exc),
                "diagnostics": _safe_cli_diagnostics(exc),
            },
            "request": {
                "sha256": _request_digest(request),
                "candidate_id": (
                    (request.get("candidate_change") or {}).get("candidate_id")
                    if request is not None
                    else None
                ),
                "allowed_evidence_ids": (
                    list(request.get("allowed_evidence_ids") or [])
                    if request is not None
                    else []
                ),
            },
            "prompt": (
                {
                    "id": rendered.prompt_id,
                    "version": rendered.version,
                    "sha256": rendered.sha256,
                }
                if rendered is not None
                else None
            ),
            "runtime": runtime,
        }
        _assert_no_secret_fields(artifact, path="artifact")
        return artifact


def run_evolution_review(
    *,
    review_id: str,
    candidate_change: Mapping[str, Any],
    evidence: Sequence[Mapping[str, Any]],
    diagnostics: Mapping[str, Any] | None = None,
    release_policy: Mapping[str, Any] | None = None,
    config_path: Path = DEFAULT_CONFIG_PATH,
    env_path: Path | None = DEFAULT_ENV_PATH,
    client: LLMClient | None = None,
    prompt_loader: PromptLoader | None = None,
) -> dict[str, Any]:
    """Run Claude review and return a secret-free, fail-closed audit artifact."""

    request: dict[str, Any] | None = None
    rendered: RenderedPrompt | None = None
    local_client = client
    history_start = 0
    try:
        request = build_review_request(
            review_id=review_id,
            candidate_change=candidate_change,
            evidence=evidence,
            diagnostics=diagnostics,
            release_policy=release_policy,
        )
        rendered = (prompt_loader or PromptLoader()).render_stage_prompt(
            PROMPT_ID,
            EvolutionReviewResponse,
            expected_stage=AGENT_STAGE,
            expected_output_schema=SCHEMA_VERSION,
        )
        if local_client is None:
            # LLMClient reads provider credentials from the process environment;
            # provider=dmx therefore uses DMX_API_KEY and never pipeline.yaml.
            load_dmx_api_key_env(env_path)
            local_client = LLMClient.from_pipeline_config(
                stage=AGENT_STAGE,
                config_path=config_path,
            )
        history_start = len(getattr(local_client, "call_history", []))
        settings = _settings(config_path)
        result = local_client.call_json(
            rendered.text,
            json.dumps(request, ensure_ascii=False, separators=(",", ":")),
            max_tokens=max(512, int(settings.get("max_tokens") or 8192)),
        )
        validated = validate_review_response(result.data, request)
        runtime = _safe_runtime_summary(local_client, history_start)
        runtime["provider"] = result.provider
        runtime["model"] = result.model
        artifact = {
            "schema_version": ARTIFACT_SCHEMA_VERSION,
            "status": "succeeded",
            "authoritative": False,
            "review_id": validated.review_id,
            "release_allowed": validated.decision == "approve",
            "response": validated.model_dump(mode="json"),
            "request": {
                "sha256": _request_digest(request),
                "candidate_id": candidate_change.get("candidate_id"),
                "allowed_evidence_ids": list(request["allowed_evidence_ids"]),
            },
            "prompt": {
                "id": rendered.prompt_id,
                "version": rendered.version,
                "sha256": rendered.sha256,
            },
            "runtime": runtime,
        }
        _assert_no_secret_fields(artifact, path="artifact")
        return artifact
    except Exception as exc:
        response = _failed_closed_response(str(review_id).strip(), type(exc).__name__)
        artifact = {
            "schema_version": ARTIFACT_SCHEMA_VERSION,
            "status": "failed_closed",
            "authoritative": False,
            "review_id": response.review_id,
            "release_allowed": False,
            "response": response.model_dump(mode="json"),
            # Error messages and raw model output are deliberately omitted: they
            # are unnecessary for the gate and could echo caller-supplied data.
            "failure": {
                "error_type": type(exc).__name__,
                "error_code": _safe_error_code(exc),
                "validation_errors": _safe_validation_errors(exc),
            },
            "request": {
                "sha256": _request_digest(request),
                "candidate_id": (
                    (request.get("candidate_change") or {}).get("candidate_id")
                    if request is not None
                    else None
                ),
                "allowed_evidence_ids": (
                    list(request.get("allowed_evidence_ids") or [])
                    if request is not None
                    else []
                ),
            },
            "prompt": (
                {
                    "id": rendered.prompt_id,
                    "version": rendered.version,
                    "sha256": rendered.sha256,
                }
                if rendered is not None
                else None
            ),
            "runtime": _safe_runtime_summary(local_client, history_start),
        }
        _assert_no_secret_fields(artifact, path="artifact")
        return artifact
