import uuid

# needed, dont ask me why
import uuid as uuid_pkg
import random
from typing import List, Optional

from sqlmodel import Field, Relationship, SQLModel, Session, select

from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as SQLAlchemyUUID
from sqlalchemy import Column, ForeignKey, Index, text

from pgvector.sqlalchemy import Vector
from sqlalchemy.orm import joinedload

from sqlalchemy import Table, MetaData
from sqlalchemy.orm import aliased
from sqlmodel import Session, select
from typing import Dict, List


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


def get_member_by_email(db: Session, member_email: str) -> List[Membership]:
    statement = (
        select(Member)
        .where(Member.email == member_email)
        .options(joinedload(Member.memberships).joinedload(Membership.data_source))
    )
    member = db.exec(statement).first()
    return member


def get_embeddings_for_member(
    db: Session, member_email: str, reference_embedding: List[float], k: int = 4
):
    # Query to get memberships and datasources for a member
    memberships_data = db.exec(
        select(Membership, DataSource)
        .join(DataSource, DataSource.uuid == Membership.data_source_uuid)
        .join(Member, Member.uuid == Membership.member_uuid)
        .where(Member.email == member_email)
    ).all()

    embeddings = {}
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
            query = text(
                f"SELECT uuid, embeddings FROM {safe_table_name} "
                # f"ORDER BY embeddings <-> {reference_array_str} "
                f"WHERE embeddings <-> {reference_array_str} < :k"
            )

            result = db.execute(
                query,
                {
                    "document_uuid": membership.document_uuid,  # Assuming you want to compare against a specific document's UUID
                    "k": k,  # Limit of results to return
                },
            ).fetchall()
            embeddings[membership.document_uuid] = [
                {"uuid": row[0], "embeddings": row[1]} for row in result
            ]
    return embeddings


# def get_embeddings_for_member(
#     db: Session, member_email: str, embeddings: List[float], k: int
# ):
#     # Assuming that we have a method in the PGVector class or elsewhere that takes an
#     # embeddings vector and returns a distance SQLAlchemy column object
#     # To avoid circular imports or undefined names, these classes and methods
#     # need to be defined in their respective modules

#     # Initialize PGVector, provide necessary arguments such as connection_string, etc.
#     pgvector_instance = PGVector(...)  # All required parameters should be passed here

#     # Query to get memberships and datasources for a member
#     memberships_data = db.exec(
#         select(Membership, DataSource)
#         .join(DataSource, DataSource.uuid == Membership.data_source_uuid)
#         .join(Member, Member.uuid == Membership.member_uuid)
#         .where(Member.email == member_email)
#     ).all()

#     nearest_embeddings = {}

#     for membership, data_source in memberships_data:
#         # Extract the document table name from the data_source metadata
#         document_table_name = data_source.document_table_metadata.get("name")

#         if document_table_name:
#             # Assume the DocumentModel is a dynamic model for the document's embeddings
#             # You need to implement the function get_dynamic_document_model to retrieve the correct model
#             DocumentModel = get_dynamic_document_model(document_table_name)

#             # Access the distance function from the PGVector instance
#             distance_column = pgvector_instance.distance_strategy(embeddings)

#             # Use the ORM query method to get the distances and order by closest first
#             # Replace CollectionStore and EmbeddingStore with the correct references if they are different
#             results = (
#                 db.query(DocumentModel, distance_column.label("distance"))
#                 .filter(DocumentModel.uuid != membership.document_uuid)
#                 .join(
#                     pgvector_instance.CollectionStore,
#                     DocumentModel.collection_id
#                     == pgvector_instance.CollectionStore.uuid,
#                 )
#                 .order_by("distance")
#                 .limit(k)
#                 .all()
#             )

#             # Store the nearest embeddings for the membership document
#             nearest_embeddings[str(membership.document_uuid)] = [
#                 {
#                     "uuid": row.uuid,
#                     "embeddings": row.embeddings,
#                     "distance": row.distance,
#                 }
#                 for row in results
#             ]

#     return nearest_embeddings


# def get_dynamic_document_model(
#     db: Session, organization_uuid: uuid_pkg.UUID, data_source_uuid: uuid_pkg.UUID
# ) -> Type[BaseDocumentTableTemplate]:
#     # Retrieve the organization and data source records from the database
#     organization = db.exec(
#         select(Organization).where(Organization.uuid == organization_uuid)
#     ).first()
#     data_source = db.exec(
#         select(DataSource).where(DataSource.uuid == data_source_uuid)
#     ).first()

#     if not organization or not data_source:
#         raise ValueError("Organization or data source not found")

#     # Generate the dynamic document table class using the factory
#     DocumentTable = document_table_factory(organ    zation, data_source)

#     # Create the document table in the database if it doesn't exist yet
#     if not db.engine.dialect.has_table(db.engine, DocumentTable.__tablename__):
#         DocumentTable.metadata.create_all(db.engine)

#     return DocumentTable


# def get_embeddings_for_member(
#     db: Session, member_email: str, reference_embedding: List[float], k: int
# ):
#     # Query to get memberships and datasources for a member
#     memberships_data = db.exec(
#         select(Membership, DataSource)
#         .join(DataSource, DataSource.uuid == Membership.data_source_uuid)
#         .join(Member, Member.uuid == Membership.member_uuid)
#         .where(Member.email == member_email)
#     ).all()

#     # Convert reference_embedding to a PostgreSQL array
#     reference_str = "','".join(str(v) for v in reference_embedding)

#     nearest_embeddings = {}

#     for membership, data_source in memberships_data:
#         # Extract the document table name from data_source metadata
#         document_table_name = data_source.document_table_metadata.get("name")

#         if document_table_name:
#             safe_table_name = f'"{document_table_name}"'

#             # Explicitly cast the reference embedding with the correct type for the pgvector comparison
#             subquery_text = f"""
#                 SELECT uuid, embeddings, (embeddings <-> ARRAY[{reference_embedding}]::vector) AS distance
#                 FROM {safe_table_name}
#                 WHERE uuid != :document_uuid
#                 ORDER BY distance
#                 LIMIT :k
#             """

#             result = db.execute(
#                 text(subquery_text),
#                 {"document_uuid": str(membership.document_uuid), "k": k},
#             ).fetchall()

#             nearest_embeddings[str(membership.document_uuid)] = [
#                 {"uuid": row[0], "embeddings": row[1], "distance": row[2]}
#                 for row in result
#             ]

#     return nearest_embeddings


# def get_embeddings_for_member(
#     db: Session, member_email: str, reference_embedding: List[float], k: int = 4
# ):
#     # Query to get memberships and datasources for a member
#     memberships_data = db.exec(
#         select(Membership, DataSource)
#         .join(DataSource, DataSource.uuid == Membership.data_source_uuid)
#         .join(Member, Member.uuid == Membership.member_uuid)
#         .where(Member.email == member_email)
#     ).all()

#     # Convert reference_embedding to a string that pgvector understands
#     reference_as_str = f"ARRAY{reference_embedding}"

#     # Placeholder for nearest embeddings
#     nearest_embeddings = {}

#     for membership, data_source in memberships_data:
#         # Extract the document table name from data_source metadata
#         document_table_name = data_source.document_table_metadata["name"]
#         # Construct and execute a raw SQL query for each document table
#         if document_table_name:
#             safe_table_name = f'"{document_table_name}"'

#             # Ensure casting to the correct array type for pgvector
#             subquery_text = f"""SELECT uuid, embeddings,
#                             (embeddings <-> ARRAY[{reference_str}]::float[]) AS distance
#                      FROM {safe_table_name}
#                      WHERE uuid != :document_uuid
#                      ORDER BY distance
#                      LIMIT :k"""

#             result = db.execute(
#                 text(subquery_text), {"document_uuid": membership.document_uuid, "k": k}
#             ).fetchall()

#             # Record the nearest embeddings for the membership document
#             nearest_embeddings[membership.document_uuid] = [
#                 {
#                     "uuid": row.uuid,
#                     "embeddings": row.embeddings,
#                     "distance": row.distance,
#                 }
#                 for row in result
#             ]

#     return nearest_embeddings

#     # Construct and execute a raw SQL query for each document table
#     if document_table_name:
#         safe_table_name = f'"{document_table_name}"'

#         # Performing a subquery to get the nearest embeddings
#         subquery = text(
#             f"""SELECT uuid, embeddings, (embeddings <-> {reference_as_str}) AS distance
#                  FROM {safe_table_name}
#                  WHERE uuid != :document_uuid
#                  ORDER BY (embeddings <-> {reference_as_str})
#                  LIMIT :k"""
#         )

#         print(subquery)

#         result = db.execute(
#             subquery, {"document_uuid": membership.document_uuid, "k": k}
#         ).fetchall()

#         # Collect the nearest embeddings in the dictionary
#         nearest_embeddings[membership.document_uuid] = [
#             {"uuid": row[0], "embeddings": row[1], "distance": row[2]}
#             for row in result
#         ]

# return nearest_embeddings


# def get_embeddings_for_member1(
#     db: Session, member_email: str
# ) -> Dict[str, List[float]]:
#     embeddings = {}

#     # Fetch memberships and datasources for the member
#     memberships_data = db.exec(
#         select(Membership, DataSource)
#         .join(DataSource, DataSource.uuid == Membership.data_source_uuid)
#         .join(Member, Member.uuid == Membership.member_uuid)
#         .where(Member.email == member_email)
#     ).all()

#     metadata = MetaData()

#     for membership, data_source in memberships_data:
#         document_table_name = data_source.document_table_metadata["name"]

#         # Use SQLAlchemy's Table reflection
#         document_table = Table(document_table_name, metadata, autoload_with=db)
#         Document = aliased(document_table)

#         # Query the document table using the reflected table
#         query = select([Document.c.embeddings]).where(
#             Document.c.uuid == membership.document_uuid
#         )
#         result = db.execute(query).fetchone()
#         print(result)
#         # if result:
#         #     embeddings[str(membership.document_uuid)] = result.embeddings

#     return embeddings


# from typing import List, Any
# import sqlalchemy
# from sqlalchemy.orm import Session
# from sqlalchemy.sql.expression import select, text


# def get_closest_embeddings_for_member(
#     db: Session, member_email: str, reference_embedding, k: int = 4
# ):
#     # Subquery for member's document_uuids
#     member_docs_subq = (
#         select(Membership.__table__.c.document_uuid)
#         .join(
#             Member.__table__,
#             Member.__table__.c.uuid == Membership.__table__.c.member_uuid,
#         )
#         .join(
#             DataSource.__table__,
#             DataSource.__table__.c.uuid == Membership.__table__.c.data_source_uuid,
#         )
#         .where(Member.__table__.c.email == member_email)
#         .subquery()
#     )

#     # Query across all document tables for embeddings accessible by the member
#     accessible_embeddings = []
#     document_tables_meta = MetaData()

#     print(member_docs_subq)

#     data_sources = db.exec(
#         select(DataSource)
#         .join(Membership, Membership.data_source_uuid == DataSource.uuid)
#         .join(Member, Member.uuid == Membership.member_uuid)
#         .where(Member.email == member_email)
#     ).all()
#     print(data_sources)
#     for data_source in data_sources:
#         document_table_name = data_source.document_table_metadata["name"]
#         document_table = Table(
#             document_table_name, document_tables_meta, autoload_with=db
#         )

#         # Construct the vector similarity search query
#         vector_distance_query = (
#             select(
#                 document_table.c.uuid.label("doc_uuid"),
#                 func.vector_distance(
#                     document_table.c.embeddings, reference_embedding
#                 ).label("distance"),
#             )
#             .where(document_table.c.uuid.in_(member_docs_subq))
#             .order_by("distance")
#             .limit(k)
#         )

#         embeddings = db.execute(vector_distance_query).fetchall()
#         accessible_embeddings.extend(embeddings)

#     return accessible_embeddings
#     # # We use a subquery to find the memberships that link members to data sources
# accessible_memberships_subq = (
#     select([Membership.__table__.c.document_uuid])
#     .join(
#         Member.__table__,
#         Member.__table__.c.uuid == Membership.__table__.c.member_uuid,
#     )
#     .join(
#         DataSource.__table__,
#         DataSource.__table__.c.uuid == Membership.__table__.c.data_source_uuid,
#     )
#     .where(Member.__table__.c.email == member_email)
#     .subquery("accessible_memberships")
# )

# # Define an ad hoc table reflecting the document tables because they are dynamic
# document_tables = {}  # Cache document tables to avoid repeated reflection
# closest_embeddings = []

# # Now, query the data source dynamically by joining the data source and membership subquery
# data_source_statement = (
#     select(
#         [
#             DataSource.__table__.c.uuid,
#             DataSource.__table__.c.document_table_metadata,
#         ]
#     )
#     .join_from(
#         DataSource.__table__,
#         accessible_memberships_subq,
#         DataSource.__table__.c.uuid
#         == accessible_memberships_subq.c.data_source_uuid,
#     )
#     .distinct()
# )
# print(data_source_statement)

# for data_source_uuid, metadata in db.execute(data_source_statement):
#     document_table_name = metadata["name"]

#     # Reflect the document table for querying if not already cached
#     if document_table_name not in document_tables:
#         document_tables[document_table_name] = Table(
#             document_table_name, MetaData(), autoload_with=db.bind
#         )

#     document_table = document_tables[document_table_name]

#     # Construct the query to get embeddings and compute distance
#     distance_subquery = (
#         select(
#             [
#                 document_table.c.uuid,
#                 func.vector_distance(
#                     document_table.c.embeddings, reference_embedding
#                 ).label("distance"),
#                 document_table.c.embeddings,
#             ]
#         )
#         .where(document_table.c.uuid == accessible_memberships_subq.c.document_uuid)
#         .order_by("distance")
#         .limit(k)
#         .alias("ordered_distances")
#     )

#     # We execute this query to get the closest embeddings per document table
#     query_results = db.execute(select([distance_subquery])).fetchall()
#     closest_embeddings.extend(query_results)

# # Return a flat list of embeddings and distances
# return closest_embeddings
