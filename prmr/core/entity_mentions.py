"""Entity mention access helpers."""

from .entity_candidates import EntityCandidateEngine
from .entity_models import EntityMention


class EntityMentionService(EntityCandidateEngine):
    """Candidate engine view focused on durable exact source mentions."""


__all__ = ["EntityMention", "EntityMentionService"]
