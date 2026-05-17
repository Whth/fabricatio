from fabricatio_core.utils import cfg

cfg(["rag"])
from fabricatio_rag.capabilities.rag import RAG

from fabricatio_novel.capabilities.novel import NovelCompose


class NovelComposeRAG(NovelCompose, RAG): ...
