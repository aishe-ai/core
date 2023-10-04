from langchain.vectorstores import Chroma
from langchain.embeddings.openai import OpenAIEmbeddings


def new_vector_store(documents):
    return Chroma.from_documents(documents, OpenAIEmbeddings())
