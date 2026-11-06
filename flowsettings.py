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

KH_APP_VERSION = config("KH_APP_VERSION", "v1.0.0")  # 应用版本
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
KH_ENABLE_MCP_MANAGEMENT = config("KH_ENABLE_MCP_MANAGEMENT", default=False, cast=bool)
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
# 设置默认回答模式
KH_CHAT_EMPTY_MSG_PLACEHOLDER = config("KH_CHAT_EMPTY_MSG_PLACEHOLDER", "(根据当前可参考的医学资料，暂无明确证据支持对此问题给出结论。为了安全起见，建议您咨询专业医生，进行进一步检查或评估。)")


# Model defaults used by the medical deployment.
LM_STUDIO_BASE_URL = config("LM_STUDIO_BASE_URL", default="http://host.docker.internal:1234/v1")
LM_STUDIO_API_KEY = config("LM_STUDIO_API_KEY", default="lm-studio")
KH_LLMS["lmstudio-gpt-oss-20b"] = {
    "spec": {
        "__type__": "kotaemon.llms.ChatOpenAI",
        "base_url": LM_STUDIO_BASE_URL,
        "model": config("LM_STUDIO_CHAT_MODEL", default="openai/gpt-oss-20b"),
        "api_key": LM_STUDIO_API_KEY,
    },
    "default": True,
}
KH_EMBEDDINGS["lmstudio-text-embedding-bge-m3"] = {
    "spec": {
        "__type__": "kotaemon.embeddings.OpenAIEmbeddings",
        "base_url": LM_STUDIO_BASE_URL,
        "model": config("LM_STUDIO_EMBEDDING_MODEL", default="text-embedding-bge-m3"),
        "api_key": LM_STUDIO_API_KEY,
    },
    "default": True,
}
KH_RERANKINGS["local-bge-reranker-v2-m3"] = {
    "spec": {
        "__type__": "kotaemon.rerankings.TeiFastReranking",
        "endpoint_url": config("RERANK_URL", default="http://localhost:8001/rerank"),
    },
    "default": True,
}

KH_REASONINGS = [  # 推理配置
    "ktem.reasoning.simple.FullQAPipeline",
    "ktem.reasoning.simple.FullDecomposeQAPipeline",
    # "ktem.reasoning.react.ReactAgentPipeline",
    # "ktem.reasoning.rewoo.RewooAgentPipeline",
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
