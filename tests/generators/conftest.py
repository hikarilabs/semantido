import pytest
from sqlalchemy import Column, Integer, String, ForeignKey
from sqlalchemy.orm import relationship

from semantido import semantic_table, SemanticDeclarativeBase
from semantido.generators.semantic_layer import PrivacyLevel


@semantic_table(
    description="Standard user account table",
)
class User(SemanticDeclarativeBase):
    """Test User model."""

    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    username = Column(String(50))

    # Custom semantic metadata via class attributes
    username_description = "The unique login name of the user"
    username_privacy_level = PrivacyLevel.PUBLIC

    posts = relationship("Post", back_populates="author")


@semantic_table(
    description="User blog posts",
)
class Post(SemanticDeclarativeBase):
    """Test Post model."""

    __tablename__ = "posts"

    id = Column(Integer, primary_key=True)
    title = Column(String(100))
    user_id = Column(Integer, ForeignKey("users.id"))

    title_description = "The title of the blog post"
    title_privacy_level = PrivacyLevel.PUBLIC

    author = relationship("User", back_populates="posts")
    author_relationship_description = "The user who wrote this post"


@pytest.fixture
def models():
    """Fixture providing the test models."""
    return {"User": User, "Post": Post}
