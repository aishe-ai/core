import os
import logging
import enum
from typing import Callable, Optional

import sqlalchemy
from langchain.embeddings.base import Embeddings
from langchain.vectorstores.pgvector import PGVector
from langchain.embeddings.openai import OpenAIEmbeddings


class DistanceStrategy(str, enum.Enum):
    """Enumerator of the Distance strategies."""

    EUCLIDEAN = "l2"
    COSINE = "cosine"
    MAX_INNER_PRODUCT = "inner"


DEFAULT_DISTANCE_STRATEGY = DistanceStrategy.COSINE
_LANGCHAIN_DEFAULT_COLLECTION_NAME = "langchain"

CONNECTION_STRING = PGVector.connection_string_from_db_params(
    driver=os.environ.get("PGVECTOR_DRIVER", "psycopg2"),
    host=os.environ.get("PGVECTOR_HOST", "localhost"),
    port=int(os.environ.get("PGVECTOR_PORT", "5432")),
    database=os.environ.get("PGVECTOR_DATABASE", "aisheAI"),
    user=os.environ.get("POSTGRES_USER", "aisheAI"),
    password=os.environ.get("POSTGRES_PASSWORD", "password"),
)


class RBACVector(PGVector):
    def __init__(
        self,
        connection_string: str,
        embedding_function: Embeddings = None,
        collection_name: str = _LANGCHAIN_DEFAULT_COLLECTION_NAME,
        collection_metadata: Optional[dict] = None,
        distance_strategy: DistanceStrategy = DEFAULT_DISTANCE_STRATEGY,
        pre_delete_collection: bool = False,
        logger: Optional[logging.Logger] = None,
        relevance_score_fn: Optional[Callable[[float], float]] = None,
    ) -> None:
        self.connection_string = connection_string
        self.embedding_function = embedding_function
        self.collection_name = collection_name
        self.collection_metadata = collection_metadata
        self._distance_strategy = distance_strategy
        self.pre_delete_collection = pre_delete_collection
        self.logger = logger or logging.getLogger(__name__)
        self.override_relevance_score_fn = relevance_score_fn
        self.__post_init__()

    # Custom initialization logic
    def __post_init__(self):
        self._conn = self.connect()
        # self.create_vector_extension()
        # from langchain.vectorstores._pgvector_data_models import (
        #     CollectionStore,
        #     EmbeddingStore,
        # )

        # self.CollectionStore = CollectionStore
        # self.EmbeddingStore = EmbeddingStore

    def connect(self) -> sqlalchemy.engine.Connection:
        engine = sqlalchemy.create_engine(self.connection_string)
        conn = engine.connect()
        return conn

    def similarity_search(self, query, k=10, filter=None):
        # Custom logic for similarity search
        # Implement your custom SQL logic here
        pass

    def similarity_search_by_vector(self, embedding, k=10, filter=None):
        # Custom logic for similarity search by vector
        # Implement your custom SQL logic here
        pass

    # Add write functionality as needed


rbac_vector = RBACVector(
    CONNECTION_STRING,
    # OpenAIEmbeddings(),
    # collection_name="your_collection_name",  # Optional: specify your collection name
    # Add other optional parameters as needed
)
