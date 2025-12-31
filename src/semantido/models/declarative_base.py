from sqlalchemy.orm import DeclarativeBase

from semantido.models.semantic_base import SemanticBase


class Base(DeclarativeBase):
    pass


class SemanticDeclarativeBase(SemanticBase, DeclarativeBase):
    pass
