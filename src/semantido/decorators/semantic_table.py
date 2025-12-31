from typing import Optional


def semantic_table(
    description: str,
    synonyms: Optional[list[str]] = None,
    sql_filters: Optional[list[str]] = None,
    application_context: Optional[str] = None,
    business_context: Optional[str] = None,
):
    """
    Decorator for adding semantic information to SQLAlchemy models

    Usage:
        @semantic_table(
            description="User information and login profile",
            synonyms: ["user profile", "client"],
            application_context: "Registered users on the platform")
        class User(Base)
        ...
    """

    def decorator(cls):
        cls.__semantic_description__ = description
        cls.__semantic_synonyms__ = synonyms
        cls.__semantic_sql_filters__ = sql_filters
        cls.__semantic_application_context__ = application_context
        cls.__semantic_business_context__ = business_context
        return cls

    return decorator
