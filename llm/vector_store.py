from langchain_community.vectorstores import Chroma
from langchain_openai import OpenAIEmbeddings
from langchain_community.vectorstores.pgvector import PGVector


def new_vector_store(documents):
    return Chroma.from_documents(documents, OpenAIEmbeddings())
