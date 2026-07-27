from enum import StrEnum

import sqlalchemy as sa

from sqlalchemy.dialects.postgresql import JSONB

# PostgreSQL uses JSONB; test and lightweight databases keep SQLAlchemy JSON.
CompatibleJSONB = sa.JSON().with_variant(JSONB, 'postgresql')


class ContentStatus(StrEnum):
    """Versioned content lifecycle."""

    draft = 'draft'
    published = 'published'
    retired = 'retired'


class BankKind(StrEnum):
    """Question bank usage type."""

    practice = 'practice'
    paper = 'paper'
    mock = 'mock'


class QuestionType(StrEnum):
    """Built-in question interaction types."""

    single_choice = 'single_choice'
    multiple_choice = 'multiple_choice'
    true_false = 'true_false'
    fill_blank = 'fill_blank'
    short_answer = 'short_answer'
    composite = 'composite'
    interactive = 'interactive'


class Visibility(StrEnum):
    """Ownership-aware content visibility."""

    private = 'private'
    internal = 'internal'
    public = 'public'


class QuestionOrigin(StrEnum):
    """How a stable question entered the platform."""

    curated = 'curated'
    imported = 'imported'
    user_created = 'user_created'
    generated = 'generated'
