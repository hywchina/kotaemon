import importlib.util
import sys
from pathlib import Path

SCRIPT_PATH = Path(__file__).parents[3] / "scripts/hospital_preflight.py"
SPEC = importlib.util.spec_from_file_location("hospital_preflight", SCRIPT_PATH)
hospital_preflight = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
sys.modules[SPEC.name] = hospital_preflight
SPEC.loader.exec_module(hospital_preflight)


def hospital_config(**overrides):
    config = {
        "KH_DEPLOYMENT_MODE": "hospital-external",
        "KH_MODEL_PROFILE": "geekai",
        "KH_MODEL_HOST_ALLOWLIST": "geekai.co",
        "KH_FEATURE_USER_MANAGEMENT_PASSWORD": "strong-password-123",
        "GEEKAI_API_KEY": "sk-valid-for-test",
        "GEEKAI_API_BASE_URL": "https://geekai.co/api/v1",
        "KH_ENABLE_MCP": "false",
        "KH_ALLOW_REMOTE_HELP": "false",
        "KH_ENABLE_URL_UPLOAD": "false",
        "KH_ENABLE_AGENT_REASONINGS": "false",
        "KH_ENABLE_EXTERNAL_AGENT_TOOLS": "false",
        "KH_GRADIO_SHARE": "false",
        "KH_ENABLE_FIRST_SETUP": "false",
    }
    config.update(overrides)
    return config


def test_valid_hospital_external_configuration_passes():
    report = hospital_preflight.validate_configuration(
        hospital_config(), database_exists=False
    )

    assert report.failures == []


def test_preflight_rejects_placeholders_and_enabled_public_features():
    report = hospital_preflight.validate_configuration(
        hospital_config(
            GEEKAI_API_KEY="<REPLACE_WITH_API_KEY>",
            KH_FEATURE_USER_MANAGEMENT_PASSWORD="admin",
            KH_ENABLE_MCP="true",
        ),
        database_exists=False,
    )

    assert any("GEEKAI_API_KEY" in failure for failure in report.failures)
    assert any("12 位" in failure for failure in report.failures)
    assert any("KH_ENABLE_MCP" in failure for failure in report.failures)


def test_preflight_rejects_public_endpoint_in_offline_mode():
    report = hospital_preflight.validate_configuration(
        hospital_config(KH_DEPLOYMENT_MODE="hospital-offline"),
        database_exists=False,
    )

    assert any("GEEKAI_API_BASE_URL" in failure for failure in report.failures)
