import importlib.util
import sqlite3
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
        "KH_FEATURE_USER_MANAGEMENT": "true",
        "KH_FEATURE_USER_MANAGEMENT_ADMIN": "admin",
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
        hospital_config(), database_has_user=False
    )

    assert report.failures == []


def test_preflight_rejects_placeholders_and_enabled_public_features():
    report = hospital_preflight.validate_configuration(
        hospital_config(
            GEEKAI_API_KEY="<REPLACE_WITH_API_KEY>",
            KH_FEATURE_USER_MANAGEMENT_PASSWORD="admin",
            KH_ENABLE_MCP="true",
        ),
        database_has_user=False,
    )

    assert any("GEEKAI_API_KEY" in failure for failure in report.failures)
    assert any("12 位" in failure for failure in report.failures)
    assert any("KH_ENABLE_MCP" in failure for failure in report.failures)


def test_preflight_rejects_public_endpoint_in_offline_mode():
    report = hospital_preflight.validate_configuration(
        hospital_config(KH_DEPLOYMENT_MODE="hospital-offline"),
        database_has_user=False,
    )

    assert any("GEEKAI_API_BASE_URL" in failure for failure in report.failures)


def test_existing_user_allows_bootstrap_password_to_be_removed():
    report = hospital_preflight.validate_configuration(
        hospital_config(KH_FEATURE_USER_MANAGEMENT_PASSWORD=""),
        database_has_user=True,
    )

    assert not any("启动管理员密码" in failure for failure in report.failures)
    assert any("已有用户账号" in warning for warning in report.warnings)


def test_sso_does_not_require_a_bootstrap_password():
    report = hospital_preflight.validate_configuration(
        hospital_config(KH_SSO_ENABLED="true", KH_FEATURE_USER_MANAGEMENT_PASSWORD=""),
        database_has_user=False,
    )

    assert not any("启动管理员密码" in failure for failure in report.failures)
    assert any("SSO" in passed for passed in report.passed)


def test_hospital_deployment_requires_user_management():
    report = hospital_preflight.validate_configuration(
        hospital_config(KH_FEATURE_USER_MANAGEMENT="false"),
        database_has_user=False,
    )

    assert any("KH_FEATURE_USER_MANAGEMENT" in failure for failure in report.failures)


def test_default_environment_template_has_no_public_provider_defaults():
    values = hospital_preflight.read_env_file(
        Path(__file__).parents[3] / ".env.example"
    )

    assert values["KH_DEPLOYMENT_MODE"] == "hospital-external"
    assert values["KH_MODEL_PROFILE"] == "geekai"
    assert not set(hospital_preflight.PUBLIC_PROVIDER_KEYS).intersection(values)


def test_database_user_detection_ignores_an_empty_database(tmp_path):
    database_path = tmp_path / "sql.db"
    with sqlite3.connect(database_path) as connection:
        connection.execute("CREATE TABLE user (id TEXT PRIMARY KEY)")

    assert not hospital_preflight.database_has_users(database_path)

    with sqlite3.connect(database_path) as connection:
        connection.execute("INSERT INTO user (id) VALUES ('admin-id')")

    assert hospital_preflight.database_has_users(database_path)
