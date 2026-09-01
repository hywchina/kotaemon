import os
import warnings
from importlib.metadata import version
from inspect import currentframe, getframeinfo
from pathlib import Path

# Known warnings from pinned optional dependencies. Both are emitted while modules
# are imported and do not affect the configured LanceDB or PDF functionality.
warnings.filterwarnings(
    "ignore",
    message='Field "model_name" in ColPaliEmbeddings has conflict.*',
    category=UserWarning,
)
warnings.filterwarnings(
    "ignore",
    message="ARC4 has been moved to cryptography.*",
)

from decouple import config  # noqa: E402
from ktem.utils.deployment import (  # noqa: E402
    normalize_deployment_mode,
    validate_model_endpoint,
)
from ktem.utils.lang import SUPPORTED_LANGUAGE_MAP  # noqa: E402
from theflow.settings.default import *  # noqa

cur_frame = currentframe()
if cur_frame is None:
    raise ValueError("Cannot get the current frame.")
this_file = getframeinfo(cur_frame).filename
this_dir = Path(this_file).parent

# change this if your app use a different name
KH_PACKAGE_NAME = "kotaemon_app"

KH_APP_VERSION = config("KH_APP_VERSION", None)
if not KH_APP_VERSION:
    try:
        # Caution: This might produce the wrong version
        # https://stackoverflow.com/a/59533071
        KH_APP_VERSION = version(KH_PACKAGE_NAME)
    except Exception:
        KH_APP_VERSION = "local"

KH_GRADIO_SHARE = config("KH_GRADIO_SHARE", default=False, cast=bool)
KH_ENABLE_FIRST_SETUP = config("KH_ENABLE_FIRST_SETUP", default=True, cast=bool)
KH_DEMO_MODE = config("KH_DEMO_MODE", default=False, cast=bool)
KH_OLLAMA_URL = config("KH_OLLAMA_URL", default="http://localhost:11434/v1/")
KH_APP_NAME = config("KH_APP_NAME", default="AI 辅助诊断系统")
KH_DEPLOYMENT_MODE = normalize_deployment_mode(
    config("KH_DEPLOYMENT_MODE", default="hospital-external")
)
KH_HOSPITAL_MODE = KH_DEPLOYMENT_MODE.startswith("hospital-")
KH_OFFLINE_MODE = KH_DEPLOYMENT_MODE == "hospital-offline"
# MCP is intentionally unavailable in the hospital build.
KH_ENABLE_MCP = False
KH_ALLOW_REMOTE_HELP = config(
    "KH_ALLOW_REMOTE_HELP", default=not KH_HOSPITAL_MODE, cast=bool
)
KH_MODEL_HOST_ALLOWLIST = {
    host.strip().lower()
    for host in config("KH_MODEL_HOST_ALLOWLIST", default="geekai.co").split(",")
    if host.strip()
}

if KH_HOSPITAL_MODE:
    KH_GRADIO_SHARE = False
    KH_ENABLE_FIRST_SETUP = False
    os.environ.setdefault("ANONYMIZED_TELEMETRY", "False")
    os.environ.setdefault("CHROMA_TELEMETRY_IMPL", "")
    os.environ.setdefault("HAYSTACK_TELEMETRY_ENABLED", "False")
    os.environ.setdefault("GRADIO_ANALYTICS_ENABLED", "False")
    os.environ.setdefault("SCARF_NO_ANALYTICS", "true")
    os.environ.setdefault("DO_NOT_TRACK", "1")
    os.environ.setdefault("HF_HUB_OFFLINE", "1")
    os.environ.setdefault("HF_DATASETS_OFFLINE", "1")
    os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
    os.environ.setdefault("KH_DISABLE_TOKENIZER_DOWNLOADS", "true")
    os.environ.setdefault(
        "NLTK_DATA", str(this_dir / "libs/ktem/ktem/assets/nltk_data")
    )

# App can be ran from anywhere and it's not trivial to decide where to store app data.
# So let's use the same directory as the flowsetting.py file.
KH_APP_DATA_DIR = this_dir / "ktem_app_data"
KH_APP_DATA_EXISTS = KH_APP_DATA_DIR.exists()
KH_APP_DATA_DIR.mkdir(parents=True, exist_ok=True)

# User data directory
KH_USER_DATA_DIR = KH_APP_DATA_DIR / "user_data"
KH_USER_DATA_DIR.mkdir(parents=True, exist_ok=True)

# markdown output directory
KH_MARKDOWN_OUTPUT_DIR = KH_APP_DATA_DIR / "markdown_cache_dir"
KH_MARKDOWN_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# chunks output directory
KH_CHUNKS_OUTPUT_DIR = KH_APP_DATA_DIR / "chunks_cache_dir"
KH_CHUNKS_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# zip output directory
KH_ZIP_OUTPUT_DIR = KH_APP_DATA_DIR / "zip_cache_dir"
KH_ZIP_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# zip input directory
KH_ZIP_INPUT_DIR = KH_APP_DATA_DIR / "zip_cache_dir_in"
KH_ZIP_INPUT_DIR.mkdir(parents=True, exist_ok=True)

# HF models can be big, let's store them in the app data directory so that it's easier
# for users to manage their storage.
# ref: https://huggingface.co/docs/huggingface_hub/en/guides/manage-cache
os.environ["HF_HOME"] = str(KH_APP_DATA_DIR / "huggingface")
os.environ["HF_HUB_CACHE"] = str(KH_APP_DATA_DIR / "huggingface")

# doc directory
KH_DOC_DIR = this_dir / "docs"

KH_MODE = "dev"
KH_SSO_ENABLED = config("KH_SSO_ENABLED", default=False, cast=bool)

KH_FEATURE_CHAT_SUGGESTION = config(
    "KH_FEATURE_CHAT_SUGGESTION", default=False, cast=bool
)
KH_FEATURE_USER_MANAGEMENT = config(
    "KH_FEATURE_USER_MANAGEMENT", default=True, cast=bool
)
KH_SHARED_FILE_COLLECTION = config("KH_SHARED_FILE_COLLECTION", default=True, cast=bool)
KH_USER_CAN_SEE_PUBLIC = None
KH_FEATURE_USER_MANAGEMENT_ADMIN = str(
    config("KH_FEATURE_USER_MANAGEMENT_ADMIN", default="admin")
)
KH_FEATURE_USER_MANAGEMENT_PASSWORD = str(
    config("KH_FEATURE_USER_MANAGEMENT_PASSWORD", default="")
)
KH_ENABLE_ALEMBIC = False
KH_DATABASE = f"sqlite:///{KH_USER_DATA_DIR / 'sql.db'}"
KH_FILESTORAGE_PATH = str(KH_USER_DATA_DIR / "files")
KH_CHAT_EMPTY_MSG_PLACEHOLDER = config(
    "KH_CHAT_EMPTY_MSG_PLACEHOLDER",
    default=(
        "根据当前可参考的医学资料，暂无明确证据支持对此问题给出结论。"
        "为了安全起见，建议您咨询专业医生，进行进一步检查或评估。"
    ),
)
KH_WEB_SEARCH_COMMAND = config("KH_WEB_SEARCH_COMMAND", default="")
KH_ENABLE_URL_UPLOAD = config("KH_ENABLE_URL_UPLOAD", default=False, cast=bool)
if KH_HOSPITAL_MODE:
    KH_WEB_SEARCH_COMMAND = ""
    KH_ENABLE_URL_UPLOAD = False
# Realtime ASR now lives in the chat composer instead of a standalone page.
KH_ENABLE_ASR = config("KH_ENABLE_ASR", default=True, cast=bool)
KH_ASR_PROVIDER = config("KH_ASR_PROVIDER", default="mock")
KH_ASR_API_BASE_URL = config("KH_ASR_API_BASE_URL", default="")
KH_ASR_API_KEY = config("KH_ASR_API_KEY", default="")
KH_ASR_MODEL = config("KH_ASR_MODEL", default="")
KH_ASR_TIMEOUT = config("KH_ASR_TIMEOUT", default=60, cast=float)
KH_ASR_MOCK_INTERVAL_SECONDS = config(
    "KH_ASR_MOCK_INTERVAL_SECONDS", default=0.55, cast=float
)
KH_ASR_MOCK_SEED_VOICEPRINTS = config(
    "KH_ASR_MOCK_SEED_VOICEPRINTS", default=True, cast=bool
)
KH_ASR_VAD_RMS_THRESHOLD = config(
    "KH_ASR_VAD_RMS_THRESHOLD", default=500.0, cast=float
)
KH_ASR_VAD_SILENCE_MS = config("KH_ASR_VAD_SILENCE_MS", default=700, cast=int)
KH_ASR_MIN_SPEECH_MS = config("KH_ASR_MIN_SPEECH_MS", default=400, cast=int)
KH_CHAT_IMAGE_MAX_FILES = config("KH_CHAT_IMAGE_MAX_FILES", default=4, cast=int)
KH_CHAT_IMAGE_MAX_SIZE_MB = config("KH_CHAT_IMAGE_MAX_SIZE_MB", default=8, cast=int)
KH_CHAT_IMAGE_MAX_PIXELS = config(
    "KH_CHAT_IMAGE_MAX_PIXELS", default=25000000, cast=int
)
KH_WEB_SEARCH_BACKEND = None if KH_HOSPITAL_MODE else (
    "kotaemon.indices.retrievers.tavily_web_search.WebSearch"
    # "kotaemon.indices.retrievers.jina_web_search.WebSearch"
)

KH_DOCSTORE = {
    # "__type__": "kotaemon.storages.ElasticsearchDocumentStore",
    # "__type__": "kotaemon.storages.SimpleFileDocumentStore",
    "__type__": "kotaemon.storages.LanceDBDocumentStore",
    "path": str(KH_USER_DATA_DIR / "docstore"),
}
KH_VECTORSTORE = {
    # "__type__": "kotaemon.storages.LanceDBVectorStore",
    "__type__": "kotaemon.storages.ChromaVectorStore",
    # "__type__": "kotaemon.storages.MilvusVectorStore",
    # "__type__": "kotaemon.storages.QdrantVectorStore",
    "path": str(KH_USER_DATA_DIR / "vectorstore"),
}
KH_LLMS = {}
KH_EMBEDDINGS = {}
KH_RERANKINGS = {}

# populate options from config
if config("AZURE_OPENAI_API_KEY", default="") and config(
    "AZURE_OPENAI_ENDPOINT", default=""
):
    if config("AZURE_OPENAI_CHAT_DEPLOYMENT", default=""):
        KH_LLMS["azure"] = {
            "spec": {
                "__type__": "kotaemon.llms.AzureChatOpenAI",
                "temperature": 0,
                "azure_endpoint": config("AZURE_OPENAI_ENDPOINT", default=""),
                "api_key": config("AZURE_OPENAI_API_KEY", default=""),
                "api_version": config("OPENAI_API_VERSION", default="")
                or "2024-02-15-preview",
                "azure_deployment": config("AZURE_OPENAI_CHAT_DEPLOYMENT", default=""),
                "timeout": 20,
            },
            "default": False,
        }
    if config("AZURE_OPENAI_EMBEDDINGS_DEPLOYMENT", default=""):
        KH_EMBEDDINGS["azure"] = {
            "spec": {
                "__type__": "kotaemon.embeddings.AzureOpenAIEmbeddings",
                "azure_endpoint": config("AZURE_OPENAI_ENDPOINT", default=""),
                "api_key": config("AZURE_OPENAI_API_KEY", default=""),
                "api_version": config("OPENAI_API_VERSION", default="")
                or "2024-02-15-preview",
                "azure_deployment": config(
                    "AZURE_OPENAI_EMBEDDINGS_DEPLOYMENT", default=""
                ),
                "timeout": 10,
            },
            "default": False,
        }

OPENAI_DEFAULT = "<YOUR_OPENAI_KEY>"
OPENAI_API_KEY = config("OPENAI_API_KEY", default=OPENAI_DEFAULT)
GOOGLE_API_KEY = config("GOOGLE_API_KEY", default="your-key")
IS_OPENAI_DEFAULT = len(OPENAI_API_KEY) > 0 and OPENAI_API_KEY != OPENAI_DEFAULT

if OPENAI_API_KEY:
    KH_LLMS["openai"] = {
        "spec": {
            "__type__": "kotaemon.llms.ChatOpenAI",
            "temperature": 0,
            "base_url": config("OPENAI_API_BASE", default="")
            or "https://api.openai.com/v1",
            "api_key": OPENAI_API_KEY,
            "model": config("OPENAI_CHAT_MODEL", default="gpt-4o-mini"),
            "timeout": 20,
        },
        "default": IS_OPENAI_DEFAULT,
    }
    KH_EMBEDDINGS["openai"] = {
        "spec": {
            "__type__": "kotaemon.embeddings.OpenAIEmbeddings",
            "base_url": config("OPENAI_API_BASE", default="https://api.openai.com/v1"),
            "api_key": OPENAI_API_KEY,
            "model": config(
                "OPENAI_EMBEDDINGS_MODEL", default="text-embedding-3-large"
            ),
            "timeout": 10,
            "context_length": 8191,
        },
        "default": IS_OPENAI_DEFAULT,
    }

VOYAGE_API_KEY = config("VOYAGE_API_KEY", default="")
if VOYAGE_API_KEY:
    KH_EMBEDDINGS["voyageai"] = {
        "spec": {
            "__type__": "kotaemon.embeddings.VoyageAIEmbeddings",
            "api_key": VOYAGE_API_KEY,
            "model": config("VOYAGE_EMBEDDINGS_MODEL", default="voyage-3-large"),
        },
        "default": False,
    }
    KH_RERANKINGS["voyageai"] = {
        "spec": {
            "__type__": "kotaemon.rerankings.VoyageAIReranking",
            "model_name": "rerank-2",
            "api_key": VOYAGE_API_KEY,
        },
        "default": False,
    }

if config("LOCAL_MODEL", default=""):
    KH_LLMS["ollama"] = {
        "spec": {
            "__type__": "kotaemon.llms.ChatOpenAI",
            "base_url": KH_OLLAMA_URL,
            "model": config("LOCAL_MODEL", default="qwen2.5:7b"),
            "api_key": "ollama",
        },
        "default": False,
    }
    KH_LLMS["ollama-long-context"] = {
        "spec": {
            "__type__": "kotaemon.llms.LCOllamaChat",
            "base_url": KH_OLLAMA_URL.replace("v1/", ""),
            "model": config("LOCAL_MODEL", default="qwen2.5:7b"),
            "num_ctx": 8192,
        },
        "default": False,
    }

    KH_EMBEDDINGS["ollama"] = {
        "spec": {
            "__type__": "kotaemon.embeddings.OpenAIEmbeddings",
            "base_url": KH_OLLAMA_URL,
            "model": config("LOCAL_MODEL_EMBEDDINGS", default="nomic-embed-text"),
            "api_key": "ollama",
        },
        "default": False,
    }
    KH_EMBEDDINGS["fast_embed"] = {
        "spec": {
            "__type__": "kotaemon.embeddings.FastEmbedEmbeddings",
            "model_name": "BAAI/bge-base-en-v1.5",
        },
        "default": False,
    }

# additional LLM configurations
KH_LLMS["claude"] = {
    "spec": {
        "__type__": "kotaemon.llms.chats.LCAnthropicChat",
        "model_name": "claude-3-5-sonnet-20240620",
        "api_key": "your-key",
    },
    "default": False,
}
KH_LLMS["google"] = {
    "spec": {
        "__type__": "kotaemon.llms.chats.LCGeminiChat",
        "model_name": "gemini-1.5-flash",
        "api_key": GOOGLE_API_KEY,
    },
    "default": not IS_OPENAI_DEFAULT,
}
KH_LLMS["groq"] = {
    "spec": {
        "__type__": "kotaemon.llms.ChatOpenAI",
        "base_url": "https://api.groq.com/openai/v1",
        "model": "llama-3.1-8b-instant",
        "api_key": "your-key",
    },
    "default": False,
}
KH_LLMS["cohere"] = {
    "spec": {
        "__type__": "kotaemon.llms.chats.LCCohereChat",
        "model_name": "command-r-plus-08-2024",
        "api_key": config("COHERE_API_KEY", default="your-key"),
    },
    "default": False,
}
KH_LLMS["mistral"] = {
    "spec": {
        "__type__": "kotaemon.llms.ChatOpenAI",
        "base_url": "https://api.mistral.ai/v1",
        "model": "ministral-8b-latest",
        "api_key": config("MISTRAL_API_KEY", default="your-key"),
    },
    "default": False,
}

# additional embeddings configurations
KH_EMBEDDINGS["cohere"] = {
    "spec": {
        "__type__": "kotaemon.embeddings.LCCohereEmbeddings",
        "model": "embed-multilingual-v3.0",
        "cohere_api_key": config("COHERE_API_KEY", default="your-key"),
        "user_agent": "default",
    },
    "default": False,
}
KH_EMBEDDINGS["google"] = {
    "spec": {
        "__type__": "kotaemon.embeddings.LCGoogleEmbeddings",
        "model": "models/text-embedding-004",
        "google_api_key": GOOGLE_API_KEY,
    },
    "default": not IS_OPENAI_DEFAULT,
}
KH_EMBEDDINGS["mistral"] = {
    "spec": {
        "__type__": "kotaemon.embeddings.LCMistralEmbeddings",
        "model": "mistral-embed",
        "api_key": config("MISTRAL_API_KEY", default="your-key"),
    },
    "default": False,
}
# KH_EMBEDDINGS["huggingface"] = {
#     "spec": {
#         "__type__": "kotaemon.embeddings.LCHuggingFaceEmbeddings",
#         "model_name": "sentence-transformers/all-mpnet-base-v2",
#     },
#     "default": False,
# }

# default reranking models
KH_RERANKINGS["cohere"] = {
    "spec": {
        "__type__": "kotaemon.rerankings.CohereReranking",
        "model_name": "rerank-v4.0-fast",
        "cohere_api_key": config("COHERE_API_KEY", default=""),
    },
    "default": True,
}

# Select one managed deployment profile. `KH_USE_LOCAL_MODEL_PROFILE` remains a
# compatibility fallback for existing deployments that have not set the new
# `KH_MODEL_PROFILE` variable.
KH_MODEL_PROFILE = config("KH_MODEL_PROFILE", default="").strip().lower()
if not KH_MODEL_PROFILE:
    KH_MODEL_PROFILE = (
        "lmstudio"
        if config("KH_USE_LOCAL_MODEL_PROFILE", default=False, cast=bool)
        else "geekai"
    )
if KH_MODEL_PROFILE not in {
    "geekai",
    "openai-compatible",
    "lmstudio",
    "official",
}:
    raise ValueError(
        "KH_MODEL_PROFILE must be one of: geekai, openai-compatible, "
        "lmstudio, official"
    )

KH_USE_GEEKAI_MODEL_PROFILE = KH_MODEL_PROFILE == "geekai"
KH_USE_OPENAI_COMPATIBLE_MODEL_PROFILE = KH_MODEL_PROFILE in {
    "geekai",
    "openai-compatible",
}
KH_USE_LOCAL_MODEL_PROFILE = KH_MODEL_PROFILE == "lmstudio"

if KH_USE_OPENAI_COMPATIBLE_MODEL_PROFILE:
    for model_group in (KH_LLMS, KH_EMBEDDINGS, KH_RERANKINGS):
        for model_config in model_group.values():
            model_config["default"] = False

    if KH_USE_GEEKAI_MODEL_PROFILE:
        compatible_name = "geekai"
        compatible_api_base = config(
            "GEEKAI_API_BASE_URL", default="https://geekai.co/api/v1"
        ).rstrip("/")
        compatible_api_key = config(
            "GEEKAI_API_KEY", default="your-geekai-api-key"
        )
        compatible_chat_model = config(
            "GEEKAI_CHAT_MODEL", default="qwen3-vl-flash"
        )
        compatible_chat_timeout = config(
            "GEEKAI_CHAT_TIMEOUT", default=120, cast=int
        )
        compatible_embedding_model = config(
            "GEEKAI_EMBEDDING_MODEL", default="qwen3-vl-embedding"
        )
        compatible_embedding_input_format = config(
            "GEEKAI_EMBEDDING_INPUT_FORMAT", default="typed_text"
        )
        compatible_embedding_batch_size = config(
            "GEEKAI_EMBEDDING_BATCH_SIZE", default=16, cast=int
        )
        compatible_embedding_timeout = config(
            "GEEKAI_EMBEDDING_TIMEOUT", default=60, cast=int
        )
        compatible_rerank_url = f"{compatible_api_base}/rerank"
        compatible_rerank_model = config(
            "GEEKAI_RERANK_MODEL", default="qwen3-rerank"
        )
        compatible_rerank_response_mapping = config(
            "GEEKAI_RERANK_RESPONSE_MAPPING", default="document"
        )
        compatible_rerank_timeout = config(
            "GEEKAI_RERANK_TIMEOUT", default=60, cast=int
        )
    else:
        compatible_name = "openai-compatible"
        compatible_api_base = config(
            "OPENAI_COMPATIBLE_API_BASE_URL",
            default="http://model-gateway:8000/v1",
        ).rstrip("/")
        compatible_api_key = config(
            "OPENAI_COMPATIBLE_API_KEY", default="local-api-key"
        )
        compatible_chat_model = config(
            "OPENAI_COMPATIBLE_CHAT_MODEL", default="qwen3-vl"
        )
        compatible_chat_timeout = config(
            "OPENAI_COMPATIBLE_CHAT_TIMEOUT", default=120, cast=int
        )
        compatible_embedding_model = config(
            "OPENAI_COMPATIBLE_EMBEDDING_MODEL", default="qwen3-vl-embedding"
        )
        compatible_embedding_input_format = config(
            "OPENAI_COMPATIBLE_EMBEDDING_INPUT_FORMAT", default="openai"
        )
        compatible_embedding_batch_size = config(
            "OPENAI_COMPATIBLE_EMBEDDING_BATCH_SIZE", default=16, cast=int
        )
        compatible_embedding_timeout = config(
            "OPENAI_COMPATIBLE_EMBEDDING_TIMEOUT", default=60, cast=int
        )
        compatible_rerank_url = config(
            "OPENAI_COMPATIBLE_RERANK_URL",
            default=f"{compatible_api_base}/rerank",
        )
        compatible_rerank_model = config(
            "OPENAI_COMPATIBLE_RERANK_MODEL", default="qwen3-rerank"
        )
        compatible_rerank_response_mapping = config(
            "OPENAI_COMPATIBLE_RERANK_RESPONSE_MAPPING", default="auto"
        )
        compatible_rerank_timeout = config(
            "OPENAI_COMPATIBLE_RERANK_TIMEOUT", default=60, cast=int
        )

    validate_model_endpoint(
        KH_DEPLOYMENT_MODE,
        compatible_api_base,
        external_hosts=KH_MODEL_HOST_ALLOWLIST,
    )
    validate_model_endpoint(
        KH_DEPLOYMENT_MODE,
        compatible_rerank_url,
        external_hosts=KH_MODEL_HOST_ALLOWLIST,
    )
    KH_LLMS[compatible_name] = {
        "spec": {
            "__type__": "kotaemon.llms.ChatOpenAI",
            "base_url": compatible_api_base,
            "model": compatible_chat_model,
            "api_key": compatible_api_key,
            "timeout": compatible_chat_timeout,
        },
        "default": True,
        "managed": True,
    }
    KH_EMBEDDINGS[compatible_name] = {
        "spec": {
            "__type__": "kotaemon.embeddings.OpenAICompatibleEmbeddings",
            "endpoint_url": f"{compatible_api_base}/embeddings",
            "model": compatible_embedding_model,
            "api_key": compatible_api_key,
            "input_format": compatible_embedding_input_format,
            "batch_size": compatible_embedding_batch_size,
            "timeout": compatible_embedding_timeout,
        },
        "default": True,
        "managed": True,
    }
    KH_RERANKINGS[compatible_name] = {
        "spec": {
            "__type__": "kotaemon.rerankings.OpenAICompatibleReranking",
            "endpoint_url": compatible_rerank_url,
            "model_name": compatible_rerank_model,
            "api_key": compatible_api_key,
            "response_mapping": compatible_rerank_response_mapping,
            "timeout": compatible_rerank_timeout,
        },
        "default": True,
        "managed": True,
    }

if KH_USE_LOCAL_MODEL_PROFILE:
    for model_group in (KH_LLMS, KH_EMBEDDINGS, KH_RERANKINGS):
        for model_config in model_group.values():
            model_config["default"] = False

    local_model_base_url = config(
        "KH_LOCAL_MODEL_BASE_URL", default="http://host.docker.internal:1234/v1"
    )
    validate_model_endpoint(KH_DEPLOYMENT_MODE, local_model_base_url)
    local_model_api_key = config("KH_LOCAL_MODEL_API_KEY", default="lmstudio")
    KH_LLMS["lmstudio"] = {
        "spec": {
            "__type__": "kotaemon.llms.ChatOpenAI",
            "base_url": local_model_base_url,
            "model": config("KH_LOCAL_CHAT_MODEL", default="openai/gpt-oss-20b"),
            "api_key": local_model_api_key,
        },
        "default": True,
    }
    KH_EMBEDDINGS["lmstudio"] = {
        "spec": {
            "__type__": "kotaemon.embeddings.OpenAIEmbeddings",
            "base_url": local_model_base_url,
            "model": config(
                "KH_LOCAL_EMBEDDING_MODEL", default="text-embedding-bge-m3"
            ),
            "api_key": local_model_api_key,
        },
        "default": True,
    }
    KH_RERANKINGS["local-bge-reranker-v2-m3"] = {
        "spec": {
            "__type__": "kotaemon.rerankings.TeiFastReranking",
            "endpoint_url": config(
                "KH_LOCAL_RERANK_URL", default="http://localhost:8001/rerank"
            ),
        },
        "default": True,
    }

if KH_HOSPITAL_MODE:
    if KH_MODEL_PROFILE == "official":
        raise ValueError("The official public-provider profile is disabled in hospital mode")
    allowed_model_names = {
        compatible_name
        if KH_USE_OPENAI_COMPATIBLE_MODEL_PROFILE
        else "lmstudio"
    }
    allowed_rerank_names = (
        {compatible_name}
        if KH_USE_OPENAI_COMPATIBLE_MODEL_PROFILE
        else {"local-bge-reranker-v2-m3"}
    )
    KH_LLMS = {
        name: value for name, value in KH_LLMS.items() if name in allowed_model_names
    }
    KH_EMBEDDINGS = {
        name: value
        for name, value in KH_EMBEDDINGS.items()
        if name in allowed_model_names
    }
    KH_RERANKINGS = {
        name: value
        for name, value in KH_RERANKINGS.items()
        if name in allowed_rerank_names
    }

KH_REASONINGS = [
    "ktem.reasoning.simple.FullQAPipeline",
    "ktem.reasoning.simple.FullDecomposeQAPipeline",
]
if not KH_HOSPITAL_MODE and config(
    "KH_ENABLE_AGENT_REASONINGS", default=False, cast=bool
):
    KH_REASONINGS.extend(
        [
            "ktem.reasoning.react.ReactAgentPipeline",
            "ktem.reasoning.rewoo.RewooAgentPipeline",
        ]
    )
KH_ENABLE_EXTERNAL_AGENT_TOOLS = config(
    "KH_ENABLE_EXTERNAL_AGENT_TOOLS", default=False, cast=bool
) and not KH_HOSPITAL_MODE
KH_REASONINGS_USE_MULTIMODAL = config("USE_MULTIMODAL", default=False, cast=bool)
KH_VLM_ENDPOINT = "{0}/openai/deployments/{1}/chat/completions?api-version={2}".format(
    config("AZURE_OPENAI_ENDPOINT", default=""),
    config("OPENAI_VISION_DEPLOYMENT_NAME", default="gpt-4o"),
    config("OPENAI_API_VERSION", default=""),
)


SETTINGS_APP: dict[str, dict] = {}


SETTINGS_REASONING = {
    "use": {
        "name": "Reasoning options",
        "value": None,
        "choices": [],
        "component": "radio",
    },
    "lang": {
        "name": "Language",
        "value": "zh",
        "choices": [(lang, code) for code, lang in SUPPORTED_LANGUAGE_MAP.items()],
        "component": "dropdown",
    },
    "max_context_length": {
        "name": "Max context length (LLM)",
        "value": 32000,
        "component": "number",
    },
}

USE_GLOBAL_GRAPHRAG = config("USE_GLOBAL_GRAPHRAG", default=False, cast=bool)
USE_NANO_GRAPHRAG = config("USE_NANO_GRAPHRAG", default=False, cast=bool)
USE_LIGHTRAG = config("USE_LIGHTRAG", default=False, cast=bool)
USE_MS_GRAPHRAG = config("USE_MS_GRAPHRAG", default=False, cast=bool)

KH_SUPPORTED_FILE_TYPES = config(
    "KH_SUPPORTED_FILE_TYPES",
    default=".pdf, .txt, .md, .doc, .docx, .xls, .xlsx, .csv",
)
KH_FILE_LOADER_MODES = config("KH_FILE_LOADER_MODES", default="default")

GRAPHRAG_INDEX_TYPES = []

if USE_MS_GRAPHRAG:
    GRAPHRAG_INDEX_TYPES.append("ktem.index.file.graph.GraphRAGIndex")
if USE_NANO_GRAPHRAG:
    GRAPHRAG_INDEX_TYPES.append("ktem.index.file.graph.NanoGraphRAGIndex")
if USE_LIGHTRAG:
    GRAPHRAG_INDEX_TYPES.append("ktem.index.file.graph.LightRAGIndex")

KH_INDEX_TYPES = [
    "ktem.index.file.FileIndex",
    *GRAPHRAG_INDEX_TYPES,
]

GRAPHRAG_INDICES = [
    {
        "name": graph_type.split(".")[-1].replace("Index", "")
        + " Collection",  # get last name
        "config": {
            "supported_file_types": KH_SUPPORTED_FILE_TYPES,
            "private": True,
        },
        "index_type": graph_type,
    }
    for graph_type in GRAPHRAG_INDEX_TYPES
]

KH_INDICES = [
    {
        "name": "文件管理",
        "config": {
            "supported_file_types": KH_SUPPORTED_FILE_TYPES,
            "private": True,
        },
        "index_type": "ktem.index.file.FileIndex",
    },
    *GRAPHRAG_INDICES,
]
