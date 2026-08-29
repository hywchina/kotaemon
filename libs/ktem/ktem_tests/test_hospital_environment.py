import os
import subprocess
import sys
from pathlib import Path


def test_hospital_settings_disable_framework_downloads():
    project_root = Path(__file__).parents[3]
    environment = os.environ.copy()
    environment.update(
        {
            "KH_DEPLOYMENT_MODE": "hospital-external",
            "KH_MODEL_PROFILE": "geekai",
            "GEEKAI_API_KEY": "test-only",
        }
    )
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "import os; "
                "from theflow.settings import settings; "
                "assert settings.KH_HOSPITAL_MODE; "
                "required = ('GRADIO_ANALYTICS_ENABLED', 'HF_DATASETS_OFFLINE', "
                "'HF_HUB_OFFLINE', 'TRANSFORMERS_OFFLINE'); "
                "assert all(os.environ.get(name) in {'1', 'False'} "
                "for name in required)"
            ),
        ],
        cwd=project_root,
        env=environment,
        capture_output=True,
        text=True,
        timeout=20,
    )

    assert result.returncode == 0, result.stderr
