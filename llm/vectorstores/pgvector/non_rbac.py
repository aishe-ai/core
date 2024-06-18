import os
import logging
import enum
from typing import (
    Any,
    Callable,
    List,
    Optional,
    Tuple,
)

import sqlalchemy
from sqlmodel import create_engine, Session
from sqlalchemy import text


from langchain.embeddings.base import Embeddings
from langchain_community.vectorstores.pgvector import PGVector
from langchain_community.embeddings.openai import OpenAIEmbeddings
from langchain.docstore.document import Document
from langchain.memory import ConversationBufferMemory
from langchain.chains import ConversationalRetrievalChain

from llm.vectorstores.pgvector.data_model import (
    get_nearest_docs,
)
from llm.config import GPT_3_5_CHAT_MODEL, CONNECTION_STRING


class DistanceStrategy(str, enum.Enum):
    """Enumerator of the Distance strategies."""

    EUCLIDEAN = "l2"
    COSINE = "cosine"
    MAX_INNER_PRODUCT = "inner"


DEFAULT_DISTANCE_STRATEGY = DistanceStrategy.COSINE
_LANGCHAIN_DEFAULT_COLLECTION_NAME = "langchain"

NON_RBAC_TABLE_NAME = os.environ.get("NON_RBAC_TABLE_NAME", "document")


def get_nearest_docs(
    db: Session, reference_embedding: List[float], max_results: int = 10
):
    # Flatten the reference_embedding into a comma-separated string and cast it as a PostgreSQL vector type
    reference_embeddings_str = ",".join(map(str, reference_embedding))
    reference_array_str = f"ARRAY[{reference_embeddings_str}]::vector"

    # Query to get the nearest documents based on cosine similarity
    # 1 - (embeddings <=> reference_array_str) to calculate cosine similarity
    query = text(
        f"""
        SELECT page_content, context_data, (1 - (embeddings <=> {reference_array_str})) AS similarity 
        FROM {NON_RBAC_TABLE_NAME}
        ORDER BY similarity ASC
        LIMIT {max_results}
        """
    )
    results = db.execute(query).fetchall()

    docs = []
    for row in results:
        doc = Document(
            page_content=str(row),
            metadata={
                "source": {"name": "postgres vector db", "table": NON_RBAC_TABLE_NAME}
            },
        )
        print(doc)
        docs.append(doc)

    return docs


class NonRBACVectorStore(PGVector):
    def __init__(
        self,
        connection_string: str = CONNECTION_STRING,
        embedding_function: Embeddings = OpenAIEmbeddings(),
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

    def connect(self) -> sqlalchemy.engine.Connection:
        engine = create_engine(self.connection_string)
        conn = engine.connect()
        self._bind = engine
        self._dbapi_connection = conn
        return conn

    def similarity_search(
        self,
        query: str,
        k: int = 4,
        filter: Optional[dict] = None,
        **kwargs: Any,
    ) -> List[Document]:
        """Run similarity search with PGVector with distance.

        Args:
            query (str): Query text to search for.
            k (int): Number of results to return. Defaults to 4.
            filter (Optional[Dict[str, str]]): Filter by metadata. Defaults to None.

        Returns:
            List of Documents most similar to the query.
        """
        return self.run_similarity_search(
            query=query,
            k=k,
            filter=filter,
        )

    def run_similarity_search(
        self,
        query: str,
        k: int = 4,
        filter: Optional[dict] = None,
    ) -> List[Tuple[Document, float]]:
        reference_embedding = self.embedding_function.embed_query(text=query)

        docs = []
        with Session(self._conn) as session:
            # print(query, filter)

            docs = get_nearest_docs(session, reference_embedding)
        print(len(docs))
        return docs


# Add write functionality as needed

if __name__ == "__main__":
    print(CONNECTION_STRING)
    non_rbac_vector_store = NonRBACVectorStore()

    prompt = "Return the oldest person"

    memory = ConversationBufferMemory(
        memory_key="chat_history",
        input_key="question",
        output_key="answer",
        return_messages=True,
    )

    llm = GPT_3_5_CHAT_MODEL

    retriever = non_rbac_vector_store.as_retriever()

    conversation_qa_chain = ConversationalRetrievalChain.from_llm(
        llm,
        retriever=retriever,
        memory=memory,
        return_source_documents=True,
    )

    conversation_result = conversation_qa_chain({"question": prompt})

    print(conversation_result["answer"])
