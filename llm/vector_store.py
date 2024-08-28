from langchain_community.vectorstores import Chroma
from langchain_openai import OpenAIEmbeddings


def new_vector_store(documents):
    return Chroma.from_documents(documents, OpenAIEmbeddings())
