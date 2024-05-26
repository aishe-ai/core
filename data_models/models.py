# from pydantic import FilePath
from langchain.pydantic_v1 import BaseModel, Field, FilePath
from typing import Optional


class EventSource(BaseModel):
    name: str
    id: str


class PromptParameters(BaseModel):
    prompt: str = Field("What are the impression for the opti.node review")
    # space_id: str = Field("~622753c759c0740069daf1e1")
    source: EventSource


class QuestionResponse(BaseModel):
    # answer: str
    question: str
    space_id: str
    # source_document: list
    chat_response: list


# confluence tool input
class ConfluenceToolParams(BaseModel):
    prompt: str = Field(description="Prompt from user")
    url: str = Field(description="URL of confluence page, user must provide it")
    confluence_space_id: str = Field(
        description="Space ID of given url, must be extracted from given URL before tool usage"
    )
    confluence_page_id: Optional[str] = Field(
        description="Page ID of given url, must be extracted from given URL before tool usage, if not found assign None to it"
    )


class WebpageToolParams(BaseModel):
    prompt: str = Field(description="Prompt from user")
    url: str = Field(description="URL of the website, user must provide it")
    ingestion_mode: str = Field(
        default="scrape",
        description="The mode to run the loader in. Default to 'scrape' if unclear!!!. Options include 'scrape' (single url) and 'crawl' (all accessible sub pages). You must return a value for this",
    )


class GitToolParams(BaseModel):
    prompt: str = Field(description="Prompt from user")
    url: str = Field(description="URL of the website, user must provide it")
    project_name: str = Field(
        description="Project name of git repo, must be extracted from given url"
    )
    branch_name: str = Field(
        description="Repo Branch, must be extracted from prompt, if not given/possible use 'main'"
    )


class DeeplDocumentTranslationTool(BaseModel):
    file_path: FilePath = Field(
        description="Filepath of original file, provided by systemmessage, if not provided search it in downloads/ within this project"
    )
    url: str = Field("")
    target_language_abbrevation: str = Field(
        description="Target language provided by user converted to a deepl valid language abbrevation by model(you). Must also be in uppercase"
    )
    slack_channel_id: str = Field(
        description="Source slack channel, provided by default value"
    )


class VectorStoreDocumentTool(BaseModel):
    file_path: FilePath = Field(
        description="Filepath of original file, provided by systemmessage"
    )
    slack_channel_id: str = Field(
        description="Source slack channel, provided by default value"
    )
    prompt: str = Field(description="Prompt from user")


class ImageCreationTool(BaseModel):
    prompt: str = Field(description="Prompt from user")


class ImageEditingTool(BaseModel):
    url: str = Field(
        "Url of an image provided by user, if not provided check for downloaded image in downloads/ within this project"
    )
    prompt: str = Field(
        description="Prompt from user, like describe image. You have return the exact prompt the user, default to 'Describe' if non was given/extractable!",
        default="Describe image!",
    )


class PgVectorToolParams(BaseModel):
    prompt: str = Field(description="Prompt from user")
