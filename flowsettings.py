import os  # 导入操作系统模块
from importlib.metadata import version  # 导入用于获取包版本的模块
from inspect import currentframe, getframeinfo  # 导入用于获取当前帧信息的模块
from pathlib import Path  # 导入用于处理文件路径的模块

from decouple import config  # 导入用于读取配置的模块
from ktem.utils.lang import SUPPORTED_LANGUAGE_MAP  # 导入支持的语言映射
from theflow.settings.default import *  # 导入默认设置

cur_frame = currentframe()  # 获取当前帧
if cur_frame is None:  # 如果无法获取当前帧，抛出异常
    raise ValueError("Cannot get the current frame.")
this_file = getframeinfo(cur_frame).filename  # 获取当前文件名
this_dir = Path(this_file).parent  # 获取当前文件所在目录

# change this if your app use a different name
KH_PACKAGE_NAME = "kotaemon_app"  # 应用包名称


# 修改版本号，主版本号.次版本号.修订号
    # 示例
    # 1.0.0 → 第一个正式版本
    # 1.1.0 → 新增功能
    # 1.1.1 → 修复小问题
    # 2.0.0 → 不兼容旧版的大更新

KH_APP_VERSION = config("KH_APP_VERSION", "v0.5.2")  # 应用版本
if not KH_APP_VERSION:  # 如果版本未设置，尝试获取包版本
    try:
        # Caution: This might produce the wrong version
        # https://stackoverflow.com/a/59533071
        KH_APP_VERSION = version(KH_PACKAGE_NAME)
    except Exception:
        KH_APP_VERSION = "local"

KH_GRADIO_SHARE = config("KH_GRADIO_SHARE", default=False, cast=bool)  # Gradio共享设置
KH_ENABLE_FIRST_SETUP = config("KH_ENABLE_FIRST_SETUP", default=True, cast=bool)  # 启用首次设置
KH_DEMO_MODE = config("KH_DEMO_MODE", default=False, cast=bool)  # 演示模式
KH_OLLAMA_URL = config("KH_OLLAMA_URL", default="http://localhost:11434/v1/")  # Ollama URL

# App can be ran from anywhere and it's not trivial to decide where to store app data.
# So let's use the same directory as the flowsetting.py file.
KH_APP_DATA_DIR = this_dir / "ktem_app_data"  # 应用数据目录
KH_APP_DATA_EXISTS = KH_APP_DATA_DIR.exists()  # 检查应用数据目录是否存在
KH_APP_DATA_DIR.mkdir(parents=True, exist_ok=True)  # 创建应用数据目录

# User data directory
KH_USER_DATA_DIR = KH_APP_DATA_DIR / "user_data"  # 用户数据目录
KH_USER_DATA_DIR.mkdir(parents=True, exist_ok=True)  # 创建用户数据目录

# markdown output directory
KH_MARKDOWN_OUTPUT_DIR = KH_APP_DATA_DIR / "markdown_cache_dir"  # Markdown输出目录
KH_MARKDOWN_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)  # 创建Markdown输出目录

# chunks output directory
KH_CHUNKS_OUTPUT_DIR = KH_APP_DATA_DIR / "chunks_cache_dir"  # 块输出目录
KH_CHUNKS_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)  # 创建块输出目录

# zip output directory
KH_ZIP_OUTPUT_DIR = KH_APP_DATA_DIR / "zip_cache_dir"  # ZIP输出目录
KH_ZIP_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)  # 创建ZIP输出目录

# zip input directory
KH_ZIP_INPUT_DIR = KH_APP_DATA_DIR / "zip_cache_dir_in"  # ZIP输入目录
KH_ZIP_INPUT_DIR.mkdir(parents=True, exist_ok=True)  # 创建ZIP输入目录

# HF models can be big, let's store them in the app data directory so that it's easier
# for users to manage their storage.
# ref: https://huggingface.co/docs/huggingface_hub/en/guides/manage-cache
os.environ["HF_HOME"] = str(KH_APP_DATA_DIR / "huggingface")  # Hugging Face主目录
os.environ["HF_HUB_CACHE"] = str(KH_APP_DATA_DIR / "huggingface")  # Hugging Face缓存目录

# doc directory
KH_DOC_DIR = this_dir / "docs"  # 文档目录

KH_MODE = "dev"  # 应用模式
KH_SSO_ENABLED = config("KH_SSO_ENABLED", default=False, cast=bool)  # 单点登录启用

KH_FEATURE_CHAT_SUGGESTION = config(  # 聊天建议功能
    "KH_FEATURE_CHAT_SUGGESTION", default=False, cast=bool
)
KH_FEATURE_USER_MANAGEMENT = config(  # 用户管理功能
    "KH_FEATURE_USER_MANAGEMENT", default=True, cast=bool
)
KH_USER_CAN_SEE_PUBLIC = None  # 用户是否可以查看公共内容
KH_FEATURE_USER_MANAGEMENT_ADMIN = str(  # 用户管理管理员
    config("KH_FEATURE_USER_MANAGEMENT_ADMIN", default="admin")
)
KH_FEATURE_USER_MANAGEMENT_PASSWORD = str(  # 用户管理密码
    config("KH_FEATURE_USER_MANAGEMENT_PASSWORD", default="admin")
)
KH_ENABLE_ALEMBIC = False  # 是否启用Alembic
KH_DATABASE = f"sqlite:///{KH_USER_DATA_DIR / 'sql.db'}"  # 数据库路径
KH_FILESTORAGE_PATH = str(KH_USER_DATA_DIR / "files")  # 文件存储路径
KH_WEB_SEARCH_BACKEND = (  # 网络搜索后端
    "kotaemon.indices.retrievers.tavily_web_search.WebSearch"
    # "kotaemon.indices.retrievers.jina_web_search.WebSearch"
)

KH_DOCSTORE = {  # 文档存储配置
    # "__type__": "kotaemon.storages.ElasticsearchDocumentStore",
    # "__type__": "kotaemon.storages.SimpleFileDocumentStore",
    "__type__": "kotaemon.storages.LanceDBDocumentStore",
    "path": str(KH_USER_DATA_DIR / "docstore"),
}
KH_VECTORSTORE = {  # 向量存储配置
    # "__type__": "kotaemon.storages.LanceDBVectorStore",
    "__type__": "kotaemon.storages.ChromaVectorStore",
    # "__type__": "kotaemon.storages.MilvusVectorStore",
    # "__type__": "kotaemon.storages.QdrantVectorStore",
    "path": str(KH_USER_DATA_DIR / "vectorstore"),
}
KH_LLMS = {}  # 语言模型配置
KH_EMBEDDINGS = {}  # 嵌入配置
KH_RERANKINGS = {}  # 重排序配置


"""temp settings for LLMs and embeddings"""
# Ollama语言模型配置
KH_LLMS["ollama-qwen3:0.6b"] = {  # Ollama语言模型配置
    "spec": {
        "__type__": "kotaemon.llms.ChatOpenAI",
        "base_url": "http://localhost:11434/v1",
        "model": "qwen3:0.6b",
        "api_key": "ollama",
    },
    "default": False,
}

KH_EMBEDDINGS["ollama-bge-large:335m"] = {  # Ollama嵌入配置
    "spec": {
        "__type__": "kotaemon.embeddings.OpenAIEmbeddings",
        "base_url": "http://localhost:11434/v1",
        "model": "qwen3:0.6b",
        "api_key": "ollama",
    },
    "default": False,
}

# 类openai api llm 与 embeddings
KH_LLMS["无问芯穹-deepseek-r1"] = {  # OpenAI语言模型配置
    "spec": {
        "__type__": "kotaemon.llms.ChatOpenAI",
        "temperature": 0.5,
        "base_url": "https://cloud.infini-ai.com/maas/v1",
        "api_key": "sk-7xet3afg2b7fumjl",
        "model": "deepseek-r1",
        "timeout": 30,
    },
    "default": False,
}

KH_LLMS["无问芯穹-gpt-4o"] = {  # OpenAI语言模型配置
    "spec": {
        "__type__": "kotaemon.llms.ChatOpenAI",
        "temperature": 0.5,
        "base_url": "https://cloud.infini-ai.com/maas/v1",
        "api_key": "sk-7xet3afg2b7fumjl",
        "model": "gpt-4o",
        "timeout": 30,
    },
    "default": True,
}

KH_LLMS["无问芯穹-baichuan-m2-32b"] = {  # OpenAI语言模型配置
    "spec": {
        "__type__": "kotaemon.llms.ChatOpenAI",
        "temperature": 0.5,
        "base_url": "https://cloud.infini-ai.com/maas/v1",
        "api_key": "sk-7xet3afg2b7fumjl",
        "model": "baichuan-m2-32b",
        "timeout": 30,
    },
    "default": False,
}

KH_EMBEDDINGS["无问芯穹-bge-m3"] = {  # OpenAI嵌入配置
    "spec": {
        "__type__": "kotaemon.embeddings.OpenAIEmbeddings",
        "base_url": "https://cloud.infini-ai.com/maas/v1",
        "api_key": "sk-7xet3afg2b7fumjl",
        "model": "bge-m3",
        "timeout": 30,
        # "context_length": 8191, # 我也不知道
    },
    "default": True,
}

# reranking model
KH_RERANKINGS["local-bge-reranker-v2-m3"] = {  
    "spec": {
        "__type__": "kotaemon.rerankings.TeiFastReranking",
        "endpoint_url": "http://localhost:8001/rerank",
    },
    "default": True,
}


"""end of temp settings for LLMs and embeddings"""

# # populate options from config
# if config("AZURE_OPENAI_API_KEY", default="") and config(  # Azure OpenAI API配置
#     "AZURE_OPENAI_ENDPOINT", default=""
# ):
#     if config("AZURE_OPENAI_CHAT_DEPLOYMENT", default=""):  # Azure OpenAI聊天部署配置
#         KH_LLMS["azure"] = {  # Azure语言模型配置
#             "spec": {
#                 "__type__": "kotaemon.llms.AzureChatOpenAI",
#                 "temperature": 0,
#                 "azure_endpoint": config("AZURE_OPENAI_ENDPOINT", default=""),
#                 "api_key": config("AZURE_OPENAI_API_KEY", default=""),
#                 "api_version": config("OPENAI_API_VERSION", default="")
#                 or "2024-02-15-preview",
#                 "azure_deployment": config("AZURE_OPENAI_CHAT_DEPLOYMENT", default=""),
#                 "timeout": 20,
#             },
#             "default": False,
#         }
#     if config("AZURE_OPENAI_EMBEDDINGS_DEPLOYMENT", default=""):
#         KH_EMBEDDINGS["azure"] = {  # Azure嵌入配置
#             "spec": {
#                 "__type__": "kotaemon.embeddings.AzureOpenAIEmbeddings",
#                 "azure_endpoint": config("AZURE_OPENAI_ENDPOINT", default=""),
#                 "api_key": config("AZURE_OPENAI_API_KEY", default=""),
#                 "api_version": config("OPENAI_API_VERSION", default="")
#                 or "2024-02-15-preview",
#                 "azure_deployment": config(
#                     "AZURE_OPENAI_EMBEDDINGS_DEPLOYMENT", default=""
#                 ),
#                 "timeout": 10,
#             },
#             "default": False,
#         }

OPENAI_DEFAULT = "<YOUR_OPENAI_KEY>"  # OpenAI默认API密钥
OPENAI_API_KEY = config("OPENAI_API_KEY", default=OPENAI_DEFAULT)  # OpenAI API密钥
GOOGLE_API_KEY = config("GOOGLE_API_KEY", default="")  # Google API密钥
IS_OPENAI_DEFAULT = len(OPENAI_API_KEY) > 0 and OPENAI_API_KEY != OPENAI_DEFAULT  # 是否使用OpenAI默认密钥

# if OPENAI_API_KEY:  # 如果设置了OpenAI API密钥
#     KH_LLMS["openai"] = {  # OpenAI语言模型配置
#         "spec": {
#             "__type__": "kotaemon.llms.ChatOpenAI",
#             "temperature": 0,
#             "base_url": config("OPENAI_API_BASE", default="")
#             or "https://api.openai.com/v1",
#             "api_key": OPENAI_API_KEY,
#             "model": config("OPENAI_CHAT_MODEL", default="gpt-4o-mini"),
#             "timeout": 20,
#         },
#         "default": IS_OPENAI_DEFAULT,
#     }
#     KH_EMBEDDINGS["openai"] = {  # OpenAI嵌入配置
#         "spec": {
#             "__type__": "kotaemon.embeddings.OpenAIEmbeddings",
#             "base_url": config("OPENAI_API_BASE", default="https://api.openai.com/v1"),
#             "api_key": OPENAI_API_KEY,
#             "model": config(
#                 "OPENAI_EMBEDDINGS_MODEL", default="text-embedding-3-large"
#             ),
#             "timeout": 10,
#             "context_length": 8191,
#         },
#         "default": IS_OPENAI_DEFAULT,
#     }

# VOYAGE_API_KEY = config("VOYAGE_API_KEY", default="")  # Voyage API密钥
# if VOYAGE_API_KEY:  # 如果设置了Voyage API密钥
#     KH_EMBEDDINGS["voyageai"] = {  # Voyage嵌入配置
#         "spec": {
#             "__type__": "kotaemon.embeddings.VoyageAIEmbeddings",
#             "api_key": VOYAGE_API_KEY,
#             "model": config("VOYAGE_EMBEDDINGS_MODEL", default="voyage-3-large"),
#         },
#         "default": False,
#     }
#     KH_RERANKINGS["voyageai"] = {  # Voyage重排序配置
#         "spec": {
#             "__type__": "kotaemon.rerankings.VoyageAIReranking",
#             "model_name": "rerank-2",
#             "api_key": VOYAGE_API_KEY,
#         },
#         "default": False,
#     }

# if config("LOCAL_MODEL", default=""):  # 如果设置了本地模型
#     KH_LLMS["ollama"] = {  # Ollama语言模型配置
#         "spec": {
#             "__type__": "kotaemon.llms.ChatOpenAI",
#             "base_url": KH_OLLAMA_URL,
#             "model": config("LOCAL_MODEL", default="qwen2.5:7b"),
#             "api_key": "ollama",
#         },
#         "default": False,
#     }
#     KH_LLMS["ollama-long-context"] = {  # Ollama长上下文语言模型配置
#         "spec": {
#             "__type__": "kotaemon.llms.LCOllamaChat",
#             "base_url": KH_OLLAMA_URL.replace("v1/", ""),
#             "model": config("LOCAL_MODEL", default="qwen2.5:7b"),
#             "num_ctx": 8192,
#         },
#         "default": False,
#     }

#     KH_EMBEDDINGS["ollama"] = {  # Ollama嵌入配置
#         "spec": {
#             "__type__": "kotaemon.embeddings.OpenAIEmbeddings",
#             "base_url": KH_OLLAMA_URL,
#             "model": config("LOCAL_MODEL_EMBEDDINGS", default="nomic-embed-text"),
#             "api_key": "ollama",
#         },
#         "default": False,
#     }
#     KH_EMBEDDINGS["fast_embed"] = {  # 快速嵌入配置
#         "spec": {
#             "__type__": "kotaemon.embeddings.FastEmbedEmbeddings",
#             "model_name": "BAAI/bge-base-en-v1.5",
#         },
#         "default": False,
#     }

# # additional LLM configurations
# KH_LLMS["claude"] = {  # Claude语言模型配置
#     "spec": {
#         "__type__": "kotaemon.llms.chats.LCAnthropicChat",
#         "model_name": "claude-3-5-sonnet-20240620",
#         "api_key": "your-key",
#     },
#     "default": False,
# }
# KH_LLMS["google"] = {  # Google语言模型配置
#     "spec": {
#         "__type__": "kotaemon.llms.chats.LCGeminiChat",
#         "model_name": "gemini-1.5-flash",
#         "api_key": GOOGLE_API_KEY,
#     },
#     "default": not IS_OPENAI_DEFAULT,
# }
# KH_LLMS["groq"] = {  # Groq语言模型配置
#     "spec": {
#         "__type__": "kotaemon.llms.ChatOpenAI",
#         "base_url": "https://api.groq.com/openai/v1",
#         "model": "llama-3.1-8b-instant",
#         "api_key": "your-key",
#     },
#     "default": False,
# }
# KH_LLMS["cohere"] = {  # Cohere语言模型配置
#     "spec": {
#         "__type__": "kotaemon.llms.chats.LCCohereChat",
#         "model_name": "command-r-plus-08-2024",
#         "api_key": config("COHERE_API_KEY", default="your-key"),
#     },
#     "default": False,
# }
# KH_LLMS["mistral"] = {  # Mistral语言模型配置
#     "spec": {
#         "__type__": "kotaemon.llms.ChatOpenAI",
#         "base_url": "https://api.mistral.ai/v1",
#         "model": "ministral-8b-latest",
#         "api_key": config("MISTRAL_API_KEY", default="your-key"),
#     },
#     "default": False,
# }

# # additional embeddings configurations
# KH_EMBEDDINGS["cohere"] = {  # Cohere嵌入配置
#     "spec": {
#         "__type__": "kotaemon.embeddings.LCCohereEmbeddings",
#         "model": "embed-multilingual-v3.0",
#         "cohere_api_key": config("COHERE_API_KEY", default="your-key"),
#         "user_agent": "default",
#     },
#     "default": False,
# }
# KH_EMBEDDINGS["google"] = {  # Google嵌入配置
#     "spec": {
#         "__type__": "kotaemon.embeddings.LCGoogleEmbeddings",
#         "model": "models/text-embedding-004",
#         "google_api_key": GOOGLE_API_KEY,
#     },
#     "default": not IS_OPENAI_DEFAULT,
# }
# KH_EMBEDDINGS["mistral"] = {  # Mistral嵌入配置
#     "spec": {
#         "__type__": "kotaemon.embeddings.LCMistralEmbeddings",
#         "model": "mistral-embed",
#         "api_key": config("MISTRAL_API_KEY", default="your-key"),
#     },
#     "default": False,
# }
# # KH_EMBEDDINGS["huggingface"] = {
#     "spec": {
#         "__type__": "kotaemon.embeddings.LCHuggingFaceEmbeddings",
#         "model_name": "sentence-transformers/all-mpnet-base-v2",
#     },
#     "default": False,
# }

# default reranking models
# KH_RERANKINGS["cohere"] = {  # Cohere重排序配置
#     "spec": {
#         "__type__": "kotaemon.rerankings.CohereReranking",
#         "model_name": "rerank-multilingual-v2.0",
#         "cohere_api_key": config("COHERE_API_KEY", default=""),
#     },
#     "default": False,
# }

KH_REASONINGS = [  # 推理配置
    "ktem.reasoning.simple.FullQAPipeline",
    "ktem.reasoning.simple.FullDecomposeQAPipeline",
    "ktem.reasoning.react.ReactAgentPipeline",
    "ktem.reasoning.rewoo.RewooAgentPipeline",
]
KH_REASONINGS_USE_MULTIMODAL = config("USE_MULTIMODAL", default=False, cast=bool)  # 是否使用多模态推理
KH_VLM_ENDPOINT = "{0}/openai/deployments/{1}/chat/completions?api-version={2}".format(  # VLM端点配置
    config("AZURE_OPENAI_ENDPOINT", default=""),
    config("OPENAI_VISION_DEPLOYMENT_NAME", default="gpt-4o"),
    config("OPENAI_API_VERSION", default=""),
)


SETTINGS_APP: dict[str, dict] = {}  # 应用设置


SETTINGS_REASONING = {  # 推理设置
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

"""GraphRAG settings
`USE_GLOBAL_GRAPHRAG` 参数用于控制在全局范围内使用 GraphRAG 索引。当该参数为 `True` 时，所有文件的索引将共享一个全局的图 ID，这可能提高索引和检索的效率。在 `lightrag_pipelines.py` 和 `nano_pipelines.py` 文件中，该参数用于决定 `store_file_id_with_graph_id` 方法是否使用集合范围的图 ID 来记录所有文件。

"""
USE_GLOBAL_GRAPHRAG = config("USE_GLOBAL_GRAPHRAG", default=False, cast=bool)  # 是否使用全局GraphRAG
USE_NANO_GRAPHRAG = config("USE_NANO_GRAPHRAG", default=False, cast=bool)  # 是否使用NanoGraphRAG
USE_LIGHTRAG = config("USE_LIGHTRAG", default=False, cast=bool)  # 是否使用LightRAG
USE_MS_GRAPHRAG = config("USE_MS_GRAPHRAG", default=False, cast=bool)  # 是否使用MSGraphRAG

GRAPHRAG_INDEX_TYPES = []  # GraphRAG索引类型

if USE_MS_GRAPHRAG:
    GRAPHRAG_INDEX_TYPES.append("ktem.index.file.graph.GraphRAGIndex")
if USE_NANO_GRAPHRAG:
    GRAPHRAG_INDEX_TYPES.append("ktem.index.file.graph.NanoGraphRAGIndex")
if USE_LIGHTRAG:
    GRAPHRAG_INDEX_TYPES.append("ktem.index.file.graph.LightRAGIndex")

KH_INDEX_TYPES = [  # 索引类型
    "ktem.index.file.FileIndex",
    *GRAPHRAG_INDEX_TYPES,
]

GRAPHRAG_INDICES = [  # GraphRAG索引
    {
        "name": graph_type.split(".")[-1].replace("Index", "")
        + " Collection",  # get last name
        "config": {
            # "supported_file_types": (
            #     ".png, .jpeg, .jpg, .tiff, .tif, .pdf, .xls, .xlsx, .doc, .docx, "
            #     ".pptx, .csv, .html, .mhtml, .txt, .md, .zip"
            # ),
            "supported_file_types": (
                ".pdf, .txt, .md, .doc, .docx, .xls, .xlsx, .csv"
            ),
            "private": True,
        },
        "index_type": graph_type,
    }
    for graph_type in GRAPHRAG_INDEX_TYPES
]

KH_INDICES = [  # 索引配置
    {
        "name": "文件管理", # File Collection
        "config": {
            "supported_file_types": (
                ".pdf, .txt, .md, .doc, .docx, .xls, .xlsx, .csv"
            ),
            "private": True,
        },
        "index_type": "ktem.index.file.FileIndex",
    },
    *GRAPHRAG_INDICES,
]
