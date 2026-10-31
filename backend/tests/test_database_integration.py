
import pytest
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from backend.app.db.session import engine
from backend.app.db.models import User, KnowledgeBase, Document


@pytest.fixture
def db_session():
    # Safety check: never run these tests against the development database.
    if engine.url.database != "ragforge_test":
        pytest.fail(
            f"Integration tests require ragforge_test, "
            f"but connected to {engine.url.database}"
        )

    connection = engine.connect()
    transaction = connection.begin()

    session = Session(
        bind=connection,
        join_transaction_mode="create_savepoint",
    )

    try:
        yield session
    finally:
        session.close()
        transaction.rollback()
        connection.close()



def test_database_relationships_and_cascade_delete(db_session):
    # 1. Create a user.
    user = User(
        email="integration-test@ragforge.local",
        hashed_password="test-hash",
    )
    db_session.add(user)
    db_session.flush()

    # Save the ID before any deletion or expiration.
    user_id = user.id

    # 2. Create a knowledge base owned by that user.
    knowledge_base = KnowledgeBase(
        owner_id=user_id,
        name="Integration Test KB",
        description="Temporary test knowledge base",
    )
    db_session.add(knowledge_base)
    db_session.flush()

    knowledge_base_id = knowledge_base.id

    # 3. Create a document inside the knowledge base.
    document = Document(
        knowledge_base_id=knowledge_base_id,
        filename="sample.pdf",
        storage_path="test/sample.pdf",
        content_type="application/pdf",
        size_bytes=1024,
        checksum="a" * 64,
    )
    db_session.add(document)
    db_session.flush()

    document_id = document.id

    # 4. Verify records and relationships.
    assert db_session.get(User, user_id) is not None

    saved_kb = db_session.get(KnowledgeBase, knowledge_base_id)
    assert saved_kb is not None
    assert saved_kb.owner_id == user_id

    saved_document = db_session.get(Document, document_id)
    assert saved_document is not None
    assert saved_document.knowledge_base_id == knowledge_base_id

    # 5. Delete the user directly in SQL.
    db_session.execute(
        delete(User)
        .where(User.id == user_id)
        .execution_options(synchronize_session=False)
    )
    db_session.flush()
    db_session.expire_all()

    # 6. Verify PostgreSQL cascaded the deletion.
    assert db_session.get(User, user_id) is None
    assert db_session.get(KnowledgeBase, knowledge_base_id) is None
    assert db_session.get(Document, document_id) is None


from sqlalchemy.exc import IntegrityError


def test_knowledge_base_requires_existing_user(db_session):
    # Generate an ID that does not belong to an existing user.
    import uuid

    invalid_user_id = uuid.uuid4()

    knowledge_base = KnowledgeBase(
        owner_id=invalid_user_id,
        name="Invalid Knowledge Base",
        description="This should not be inserted",
    )

    db_session.add(knowledge_base)

    # PostgreSQL should reject the insert because the user does not exist.
    with pytest.raises(IntegrityError):
        db_session.flush()

    db_session.rollback()
