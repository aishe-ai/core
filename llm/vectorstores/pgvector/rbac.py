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
from sqlmodel import Session

from langchain.embeddings.base import Embeddings
from langchain.vectorstores.pgvector import PGVector
from langchain.embeddings.openai import OpenAIEmbeddings
from langchain.docstore.document import Document
from langchain.memory import ConversationBufferMemory
from langchain.chat_models import ChatOpenAI
from langchain.chains import ConversationalRetrievalChain

from data_model import (
    get_memberships_by_email,
    get_nearest_docs,
)


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
        embedding_function: Embeddings,
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
        engine = sqlalchemy.create_engine(self.connection_string)
        conn = engine.connect()
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
        member_email = filter["user"]
        embedding = self.embedding_function.embed_query(text=query)

        docs = []
        with Session(self._conn) as session:
            memberships = get_memberships_by_email(session, member_email)
            print(query, member_email, len(memberships))

            docs = get_nearest_docs(session, member_email, embedding)
        print(docs)
        return docs


# Add write functionality as needed


rbac_vector_store = RBACVector(
    connection_string=CONNECTION_STRING,
    embedding_function=OpenAIEmbeddings(),
)

prompt = "Summerize given context to you"

memory = ConversationBufferMemory(
    memory_key="chat_history",
    input_key="question",
    output_key="answer",
    return_messages=True,
)

llm = ChatOpenAI(model_name="gpt-4", temperature=1)
# result = llm.invoke("hello")
# print(result)


retriever = rbac_vector_store.as_retriever()
retriever.search_kwargs = {"filter": {"user": "testmember@example.com"}}


conversation_qa_chain = ConversationalRetrievalChain.from_llm(
    llm,
    retriever=retriever,
    memory=memory,
    return_source_documents=True,
)
conversation_result = conversation_qa_chain({"question": prompt})

print(conversation_result["answer"])
