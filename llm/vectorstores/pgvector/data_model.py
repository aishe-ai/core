import uuid
import os

# needed, dont ask me why
import uuid as uuid_pkg
import random
from typing import List, Optional

from sqlmodel import Field, Relationship, SQLModel, Session, select

from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as SQLAlchemyUUID
from sqlalchemy import Column, ForeignKey, Index, text

from pgvector.sqlalchemy import Vector

from langchain.docstore.document import Document

NON_RBAC_TABLE_NAME = os.environ.get("NON_RBAC_TABLE_NAME", "document")


class Organization(SQLModel, table=True):
    uuid: uuid_pkg.UUID = Field(primary_key=True)
    name: str
    description: Optional[str] = None
    data_sources: List["DataSource"] = Relationship(back_populates="organization")
    members: List["Member"] = Relationship(back_populates="organization")


class DataSource(SQLModel, table=True):
    uuid: uuid_pkg.UUID = Field(primary_key=True)
    organization_uuid: uuid_pkg.UUID = Field(foreign_key="organization.uuid")
    name: str
    description: Optional[str] = None
    bot_auth_data: dict = Field(sa_column=Column(JSONB))
    document_table_metadata: dict = Field(sa_column=Column(JSONB))
    airbyte_meta_data: dict = Field(sa_column=Column(JSONB))
    organization: Organization = Relationship(back_populates="data_sources")
    memberships: List["Membership"] = Relationship(back_populates="data_source")


class Member(SQLModel, table=True):
    uuid: uuid_pkg.UUID = Field(primary_key=True)
    organization_uuid: uuid_pkg.UUID = Field(foreign_key="organization.uuid")
    email: str
    name: str
    organization: Organization = Relationship(back_populates="members")
    memberships: List["Membership"] = Relationship(back_populates="member")


class Membership(SQLModel, table=True):
    uuid: uuid_pkg.UUID = Field(primary_key=True)
    data_source_uuid: uuid_pkg.UUID = Field(foreign_key="datasource.uuid")
    member_uuid: uuid_pkg.UUID = Field(foreign_key="member.uuid")
    document_uuid: uuid_pkg.UUID  # No foreign key here, as it's dynamic
    data_source_meta_data: dict = Field(sa_column=Column(JSONB))
    data_source: DataSource = Relationship(back_populates="memberships")
    member: Member = Relationship(back_populates="memberships")
    # 'document' relationship will be added dynamically


class BaseDocumentTableTemplate(SQLModel, table=False):
    # Common fields
    uuid: uuid_pkg.UUID = Field(primary_key=True)
    name: str
    description: Optional[str] = None
    url: Optional[str] = None
    context_data: dict = Field(sa_column=Column(JSONB))
    data_source_uuid: uuid_pkg.UUID = Field(
        sa_column=Column(
            SQLAlchemyUUID, ForeignKey("datasource.uuid", ondelete="CASCADE")
        )
    )
    # hardcoded because not setable in openai api
    embeddings: List[float] = Field(sa_column=Column(Vector(1536)))
    content: Optional[str] = None
    # Add other common fields or relationships here


def create_data_source(name: str, organization: Organization, document_table_name=""):
    return DataSource(
        uuid=str(uuid.uuid4()),
        name=name,
        description=f"Airbyte Data Source",
        bot_auth_data={},  # Assuming this is the correct format for your JSONB field
        document_table_metadata={name: document_table_name},
        airbyte_meta_data={},  # Assuming a default empty dict, adjust as needed
        organization_uuid=organization.uuid,
    )


def create_mock_organization(org_name=None, member_name=None, member_email=None):
    # Use provided values or generate random ones
    org_name = org_name or f"Organization {random.randint(1, 1000)}"
    member_name = member_name or f"Member {random.randint(1, 1000)}"
    member_email = member_email or f"user{random.randint(1, 1000)}@example.com"

    # Create an Organization instance
    organization = Organization(
        uuid=str(uuid.uuid4()),
        name=org_name,
        description=f"Description {random.randint(1, 1000)}",
    )

    # Create a Member instance
    member = Member(
        uuid=str(uuid.uuid4()),
        email=member_email,
        name=member_name,
        organization_uuid=organization.uuid,
    )

    # Create a DataSource instance
    data_source = DataSource(
        uuid=str(uuid.uuid4()),
        name=f"DataSource {random.randint(1, 1000)}",
        description=f"Description {random.randint(1, 1000)}",
        bot_auth_data={},  # Assuming JSONB field
        document_table_metadata={},  # Assuming JSONB field
        airbyte_meta_data={},  # Assuming JSONB field
        organization_uuid=organization.uuid,
    )

    # Create a dynamically named DocumentTable instance
    document_table = document_table_factory(organization, data_source)

    # Create a Membership instance
    membership = Membership(
        uuid=str(uuid.uuid4()),
        data_source_uuid=data_source.uuid,
        member_uuid=member.uuid,
        document_uuid=document_table.uuid,  # Assuming this is the correct field
        data_source_meta_data={},  # Assuming JSONB field
    )

    return organization, member


def create_document(organization, data_source, raw_document):
    # Use the factory function to get the correct table class
    DocumentTable = document_table_factory(organization, data_source)

    # Convert UUIDs to strings
    uuid_str = str(uuid.uuid4())
    data_source_uuid_str = str(data_source.uuid)

    return DocumentTable(
        uuid=uuid_str,
        # TODO: fix weird error
        # data_source_uuid=data_source.uuid,
        name="Test document",
        description="Airbyte Data Source Document",
        url="",
        context_data={},
        embeddings=raw_document.embedding,
        content=raw_document.page_content,
    )


def document_table_factory(organization, data_source) -> SQLModel:
    # You can add or override other fields specific to this table if needed
    class DocumentTableTemplate(BaseDocumentTableTemplate, table=True):
        __tablename__ = f"document_table__{organization.name}_{data_source.name}"  #
        __table_args__ = {"extend_existing": True}  # Add this line
        data_source_uuid: uuid_pkg.UUID = Field(
            sa_column=Column(
                SQLAlchemyUUID, ForeignKey("datasource.uuid", ondelete="CASCADE")
            )
        )

    # Define the pgvector index for the subclass
    Index(
        f"embedding_idx_{organization.name}_{data_source.name}",
        DocumentTableTemplate.embeddings,
        postgresql_using="hnsw",
        postgresql_with={"m": 16, "ef_construction": 200},
        postgresql_ops={"embeddings": "vector_l2_ops"},
    )

    return DocumentTableTemplate


def get_memberships_by_email(db: Session, member_email: str) -> List[Membership]:
    return db.exec(
        select(Membership, DataSource)
        .join(DataSource, DataSource.uuid == Membership.data_source_uuid)
        .join(Member, Member.uuid == Membership.member_uuid)
        .where(Member.email == member_email)
    ).all()


def get_nearest_rbac_docs(
    db: Session, member_email: str, reference_embedding: List[float], k: int = 0.8
):
    # Query to get memberships and datasources for a member
    memberships_data = get_memberships_by_email(db, member_email)
    docs = []

    for membership, data_source in memberships_data:
        # Extract the document table name from data_source metadata
        document_table_name = data_source.document_table_metadata["name"]

        # Construct and execute a raw SQL query for each document table
        if document_table_name:
            safe_table_name = f'"{document_table_name}"'

            # Flatten the reference_embedding into a comma-separated string and cast it as a PostgreSQL vector type
            reference_embeddings_str = ",".join(map(str, reference_embedding))
            reference_array_str = f"ARRAY[{reference_embeddings_str}]::vector"

            # Here we insert the reference embedding string and limit into the SQL statement
            # We use 1 - (embeddings <=> reference_array_str) to calculate cosine similarity
            query = text(
                f"SELECT content, context_data FROM {safe_table_name} "
                f"WHERE uuid = :document_uuid AND "
                f"(1 - (embeddings <=> {reference_array_str})) < :k"
            )

            results = db.execute(
                query,
                {
                    "document_uuid": membership.document_uuid,
                    "k": k,
                },
            ).fetchall()

            for row in results:
                doc = Document(
                    page_content=row[0],
                    metadata=row[1],
                    # {"source": "downloads/meetups.pdf", "page": 0}
                )
                docs.append(doc)
    return docs


def get_nearest_docs(db: Session, reference_embedding: List[float], k: int = 0.8):
    # Query to get memberships and datasources for a member
    docs = []

    # Flatten the reference_embedding into a comma-separated string and cast it as a PostgreSQL vector type
    reference_embeddings_str = ",".join(map(str, reference_embedding))
    reference_array_str = f"ARRAY[{reference_embeddings_str}]::vector"

    # Here we insert the reference embedding string and limit into the SQL statement
    # We use 1 - (embeddings <=> reference_array_str) to calculate cosine similarity
    query = text(
        f"SELECT page_content, context_data FROM {NON_RBAC_TABLE_NAME} "
        f"WHERE (1 - (embeddings <=> {reference_array_str})) < :k "
        f"LIMIT 20"
    )

    results = db.execute(
        query,
        {
            "k": k,
        },
    ).fetchall()

    for row in results:
        doc = Document(
            page_content=row[0],
            metadata=row[1],
            # {"source": "downloads/meetups.pdf", "page": 0}
        )
        docs.append(doc)

    return docs
