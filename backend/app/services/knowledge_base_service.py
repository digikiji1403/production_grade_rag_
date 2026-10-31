
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.db.models import KnowledgeBase


def create_knowledge_base(
    db: Session,
    owner_id: UUID,
    name: str,
    description: str | None,
) -> KnowledgeBase:
    knowledge_base = KnowledgeBase(
        owner_id=owner_id,
        name=name.strip(),
        description=description,
    )

    db.add(knowledge_base)
    db.commit()
    db.refresh(knowledge_base)

    return knowledge_base


def list_knowledge_bases(
    db: Session,
    owner_id: UUID,
) -> list[KnowledgeBase]:
    statement = (
        select(KnowledgeBase)
        .where(KnowledgeBase.owner_id == owner_id)
        .order_by(KnowledgeBase.created_at.desc())
    )

    return list(db.scalars(statement).all())


def get_knowledge_base(
    db: Session,
    knowledge_base_id: UUID,
    owner_id: UUID,
) -> KnowledgeBase | None:
    statement = select(KnowledgeBase).where(
        KnowledgeBase.id == knowledge_base_id,
        KnowledgeBase.owner_id == owner_id,
    )

    return db.scalar(statement)


def update_knowledge_base(
    db: Session,
    knowledge_base: KnowledgeBase,
    updates: dict,
) -> KnowledgeBase:
    for field, value in updates.items():
        if field == "name":
            value = value.strip()

        setattr(knowledge_base, field, value)

    db.commit()
    db.refresh(knowledge_base)

    return knowledge_base


def delete_knowledge_base(
    db: Session,
    knowledge_base: KnowledgeBase,
) -> None:
    db.delete(knowledge_base)
    db.commit()
