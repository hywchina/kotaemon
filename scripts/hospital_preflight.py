#!/usr/bin/env python3
"""Validate hospital deployment configuration without contacting model services."""

from __future__ import annotations

import argparse
import os
import shutil
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "libs/ktem"))

from ktem.utils.deployment import (  # noqa: E402
    normalize_deployment_mode,
    validate_model_endpoint,
)

TRUE_VALUES = {"1", "true", "yes", "on"}
PLACEHOLDER_MARKERS = ("<replace", "<your", "placeholder", "changeme")
DISABLED_HOSPITAL_FEATURES = (
    "KH_ENABLE_MCP",
    "KH_ALLOW_REMOTE_HELP",
    "KH_ENABLE_URL_UPLOAD",
    "KH_ENABLE_AGENT_REASONINGS",
    "KH_ENABLE_EXTERNAL_AGENT_TOOLS",
    "KH_GRADIO_SHARE",
    "KH_ENABLE_FIRST_SETUP",
)
PUBLIC_PROVIDER_KEYS = (
    "OPENAI_API_KEY",
    "AZURE_OPENAI_API_KEY",
    "COHERE_API_KEY",
    "MISTRAL_API_KEY",
    "VOYAGE_API_KEY",
    "GOOGLE_API_KEY",
    "GRAPHRAG_API_KEY",
)
REQUIRED_OFFLINE_ASSETS = (
    "libs/ktem/ktem/assets/vendor/d3-7.8.5.min.js",
    "libs/ktem/ktem/assets/vendor/tribute-5.1.3.min.js",
    "libs/ktem/ktem/assets/prebuilt/pdfjs-4.0.379-dist.zip",
    "libs/ktem/ktem/assets/nltk_data/corpora/stopwords/english",
    "libs/ktem/ktem/assets/nltk_data/tokenizers/punkt_tab/english/ortho_context.tab",
)


@dataclass
class PreflightReport:
    passed: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    failures: list[str] = field(default_factory=list)

    def check(self, condition: bool, success: str, failure: str) -> None:
        (self.passed if condition else self.failures).append(
            success if condition else failure
        )


def read_env_file(path: Path) -> dict[str, str]:
    """Read the simple KEY=VALUE subset used by the deployment template."""

    values: dict[str, str] = {}
    if not path.is_file():
        return values
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
            value = value[1:-1]
        values[key.strip()] = value
    return values


def merged_config(env_file: Path) -> dict[str, str]:
    config = read_env_file(env_file)
    config.update({key: value for key, value in os.environ.items() if value is not None})
    return config


def _is_true(value: str | None) -> bool:
    return (value or "").strip().lower() in TRUE_VALUES


def _is_placeholder(value: str | None) -> bool:
    normalized = (value or "").strip().lower()
    return not normalized or any(marker in normalized for marker in PLACEHOLDER_MARKERS)


def validate_configuration(
    config: dict[str, str], *, database_exists: bool
) -> PreflightReport:
    """Validate security and model settings without performing network requests."""

    report = PreflightReport()
    try:
        mode = normalize_deployment_mode(
            config.get("KH_DEPLOYMENT_MODE", "hospital-external")
        )
        report.passed.append(f"部署档位有效：{mode}")
    except ValueError as exc:
        report.failures.append(str(exc))
        return report

    if not mode.startswith("hospital-"):
        report.failures.append("医院部署必须使用 hospital-external 或 hospital-offline。")

    profile = config.get("KH_MODEL_PROFILE", "geekai").strip().lower()
    report.check(
        profile in {"geekai", "lmstudio"},
        f"模型配置档有效：{profile}",
        "KH_MODEL_PROFILE 只能是 geekai 或 lmstudio。",
    )

    password = config.get("KH_FEATURE_USER_MANAGEMENT_PASSWORD", "")
    if database_exists and _is_placeholder(password):
        report.warnings.append("已有用户数据库，未设置启动管理员密码；请确认管理员账号可用。")
    else:
        report.check(
            not _is_placeholder(password) and len(password) >= 12,
            "启动管理员密码已设置。",
            "首次部署必须设置至少 12 位的 KH_FEATURE_USER_MANAGEMENT_PASSWORD。",
        )

    allowlist = {
        host.strip().lower()
        for host in config.get("KH_MODEL_HOST_ALLOWLIST", "geekai.co").split(",")
        if host.strip()
    }
    endpoints: list[tuple[str, str]] = []
    if profile == "geekai":
        report.check(
            not _is_placeholder(config.get("GEEKAI_API_KEY")),
            "GeekAI 密钥已设置。",
            "GEEKAI_API_KEY 未设置或仍是占位值。",
        )
        endpoints.append(
            ("GEEKAI_API_BASE_URL", config.get("GEEKAI_API_BASE_URL", ""))
        )
    elif profile == "lmstudio":
        endpoints.extend(
            [
                (
                    "KH_LOCAL_MODEL_BASE_URL",
                    config.get("KH_LOCAL_MODEL_BASE_URL", ""),
                ),
                ("KH_LOCAL_RERANK_URL", config.get("KH_LOCAL_RERANK_URL", "")),
            ]
        )

    if _is_true(config.get("KH_ENABLE_ASR")):
        asr_endpoint = config.get("KH_ASR_API_BASE_URL", "")
        if asr_endpoint:
            endpoints.append(("KH_ASR_API_BASE_URL", asr_endpoint))
        else:
            report.warnings.append("ASR 已启用但未配置服务地址，将只能使用 Mock Provider。")

    for name, endpoint in endpoints:
        if not endpoint:
            report.failures.append(f"{name} 未配置。")
            continue
        try:
            validate_model_endpoint(mode, endpoint, external_hosts=allowlist)
            report.passed.append(f"{name} 符合网络出口策略。")
        except ValueError as exc:
            report.failures.append(f"{name} 不符合网络出口策略：{exc}")

    for name in DISABLED_HOSPITAL_FEATURES:
        report.check(
            not _is_true(config.get(name)),
            f"{name} 已关闭。",
            f"{name} 必须关闭。",
        )
    if config.get("KH_WEB_SEARCH_COMMAND", "").strip():
        report.failures.append("KH_WEB_SEARCH_COMMAND 必须留空。")

    configured_public_keys = [
        name for name in PUBLIC_PROVIDER_KEYS if not _is_placeholder(config.get(name))
    ]
    if configured_public_keys:
        report.warnings.append(
            "检测到医院配置未使用的公共 Provider 密钥，请从 .env 删除："
            + ", ".join(configured_public_keys)
        )

    return report


def validate_runtime(project_root: Path, report: PreflightReport) -> None:
    missing_assets = [
        relative_path
        for relative_path in REQUIRED_OFFLINE_ASSETS
        if not (project_root / relative_path).is_file()
    ]
    report.check(
        not missing_assets,
        "浏览器、PDF 和分词离线资源完整。",
        "缺少离线资源：" + ", ".join(missing_assets),
    )

    data_dir = project_root / "ktem_app_data"
    try:
        data_dir.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(dir=data_dir):
            pass
        report.passed.append("应用数据目录可写。")
    except OSError as exc:
        report.failures.append(f"应用数据目录不可写：{exc}")

    free_bytes = shutil.disk_usage(data_dir).free
    if free_bytes < 5 * 1024**3:
        report.warnings.append("应用数据盘剩余空间不足 5 GB，请及时扩容或清理。")
    else:
        report.passed.append("应用数据盘剩余空间不少于 5 GB。")


def print_report(report: PreflightReport) -> None:
    for message in report.passed:
        print(f"[PASS] {message}")
    for message in report.warnings:
        print(f"[WARN] {message}")
    for message in report.failures:
        print(f"[FAIL] {message}")
    print(
        "[SUMMARY] "
        f"通过 {len(report.passed)} 项，警告 {len(report.warnings)} 项，"
        f"失败 {len(report.failures)} 项。"
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="医院内网部署启动前自检")
    parser.add_argument(
        "--env-file",
        type=Path,
        default=PROJECT_ROOT / ".env",
        help="环境变量文件路径，默认使用项目根目录 .env",
    )
    args = parser.parse_args()

    config = merged_config(args.env_file)
    database_exists = (PROJECT_ROOT / "ktem_app_data/user_data/sql.db").is_file()
    report = validate_configuration(config, database_exists=database_exists)
    validate_runtime(PROJECT_ROOT, report)
    print_report(report)
    return 1 if report.failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
