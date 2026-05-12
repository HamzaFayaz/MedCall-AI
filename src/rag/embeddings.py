from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from src.config import config


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_QUERY_TASK = (
    "Given a patient-facing hospital policy, FAQ, or care-routing question, "
    "retrieve the relevant approved Mercy General knowledge base passage."
)


EmbeddingInputType = Literal["document", "query"]


@dataclass(frozen=True)
class EmbeddingConfig:
    model_id: str = config.RAG_EMBEDDING_MODEL_ID
    model_path: Path = PROJECT_ROOT / config.RAG_EMBEDDING_MODEL_PATH
    dimension: int = config.RAG_EMBEDDING_DIMENSION
    max_length: int = config.RAG_EMBEDDING_MAX_LENGTH
    batch_size: int = config.RAG_EMBEDDING_BATCH_SIZE
    device: str = "cpu"


def _format_query(text: str, task_description: str = DEFAULT_QUERY_TASK) -> str:
    return f"Instruct: {task_description}\nQuery: {text}"


class QwenEmbeddingAdapter:
    """Local Qwen3 embedding adapter used by ingestion and retrieval."""

    def __init__(self, embedding_config: EmbeddingConfig | None = None) -> None:
        self.config = embedding_config or EmbeddingConfig()
        self._tokenizer = None
        self._model = None

    @property
    def dimension(self) -> int:
        return self.config.dimension

    @property
    def model_id(self) -> str:
        return self.config.model_id

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return self._embed_texts(texts, input_type="document")

    def embed_query(self, query: str) -> list[float]:
        return self._embed_texts([query], input_type="query")[0]

    def _embed_texts(
        self,
        texts: list[str],
        input_type: EmbeddingInputType,
    ) -> list[list[float]]:
        if not texts:
            return []

        prepared_texts = [
            _format_query(text) if input_type == "query" else text
            for text in texts
        ]

        self._load_model()

        embeddings: list[list[float]] = []
        for start in range(0, len(prepared_texts), self.config.batch_size):
            batch = prepared_texts[start : start + self.config.batch_size]
            embeddings.extend(self._embed_batch(batch))

        return embeddings

    def _load_model(self) -> None:
        if self._tokenizer is not None and self._model is not None:
            return

        if not self.config.model_path.exists():
            raise FileNotFoundError(
                "Local embedding model folder is missing. "
                f"Expected: {self.config.model_path}. "
                "Run `python scripts/download_embedding_model.py` first."
            )

        try:
            import torch
            from transformers import AutoModel, AutoTokenizer
        except ImportError as exc:
            raise RuntimeError(
                "Embedding dependencies are missing. Install requirements with "
                "`pip install -r requirements.txt`."
            ) from exc

        self._torch = torch
        self._tokenizer = AutoTokenizer.from_pretrained(
            self.config.model_path,
            padding_side="left",
            local_files_only=True,
        )
        self._model = AutoModel.from_pretrained(
            self.config.model_path,
            local_files_only=True,
        )
        self._model.to(self.config.device)
        self._model.eval()

    def _embed_batch(self, texts: list[str]) -> list[list[float]]:
        import torch.nn.functional as functional

        encoded = self._tokenizer(
            texts,
            padding=True,
            truncation=True,
            max_length=self.config.max_length,
            return_tensors="pt",
        )
        encoded = encoded.to(self._model.device)

        with self._torch.no_grad():
            outputs = self._model(**encoded)
            pooled = self._last_token_pool(
                outputs.last_hidden_state,
                encoded["attention_mask"],
            )
            normalized = functional.normalize(pooled, p=2, dim=1)

        if normalized.shape[1] < self.config.dimension:
            raise ValueError(
                f"Model returned {normalized.shape[1]} dimensions, "
                f"but {self.config.dimension} were requested."
            )

        vectors = normalized[:, : self.config.dimension]
        return vectors.cpu().float().tolist()

    def _last_token_pool(self, last_hidden_states, attention_mask):
        left_padding = attention_mask[:, -1].sum() == attention_mask.shape[0]
        if left_padding:
            return last_hidden_states[:, -1]

        sequence_lengths = attention_mask.sum(dim=1) - 1
        batch_size = last_hidden_states.shape[0]
        return last_hidden_states[
            self._torch.arange(batch_size, device=last_hidden_states.device),
            sequence_lengths,
        ]


def get_embedding_adapter() -> QwenEmbeddingAdapter:
    return QwenEmbeddingAdapter()
