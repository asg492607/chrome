"""
Sovereign Knowledge Graph Engine (Sprint 56 - Phase II Sovereign Search Engine).
Implements entity extraction, subject-predicate-object semantic triples (Subject -> Predicate -> Object),
relation graph linking, and knowledge graph querying.
"""

import os
import sys
from typing import Dict, List, Optional, Set, Tuple, Any

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))


class Entity:
    """Represents a named entity in the Sovereign Knowledge Graph."""

    def __init__(self, entity_id: str, name: str, category: str, properties: Optional[Dict[str, Any]] = None):
        self.entity_id = entity_id
        self.name = name
        self.category = category # "Person", "Organization", "Location", "Technology", "Concept"
        self.properties = properties or {}

    def to_dict(self) -> Dict[str, Any]:
        return {
            "entityId": self.entity_id,
            "name": self.name,
            "category": self.category,
            "properties": self.properties
        }

    def __repr__(self) -> str:
        return f"Entity('{self.name}', category='{self.category}')"


class Triple:
    """Represents a Subject-Predicate-Object semantic knowledge graph relation triple."""

    def __init__(self, subject: str, predicate: str, object_: str, confidence: float = 1.0):
        self.subject = subject.strip().lower()
        self.predicate = predicate.strip().lower()
        self.object_ = object_.strip().lower()
        self.confidence = confidence

    def to_dict(self) -> Dict[str, Any]:
        return {
            "subject": self.subject,
            "predicate": self.predicate,
            "object": self.object_,
            "confidence": self.confidence
        }

    def __repr__(self) -> str:
        return f"Triple('{self.subject}' -> '{self.predicate}' -> '{self.object_}')"


class KnowledgeGraphEngine:
    """Core Knowledge Graph engine managing entities, triples, and semantic graph queries."""

    def __init__(self):
        self.entities: Dict[str, Entity] = {} # name_lower -> Entity
        self.triples: List[Triple] = []

    def add_entity(self, entity: Entity) -> None:
        """Registers a named entity into the graph."""
        self.entities[entity.name.lower()] = entity

    def add_triple(self, subject: str, predicate: str, object_: str, confidence: float = 1.0) -> Triple:
        """Adds a semantic triple relation into the graph."""
        triple = Triple(subject, predicate, object_, confidence)
        self.triples.append(triple)
        return triple

    def extract_entities(self, text: str) -> List[Entity]:
        """Extracts known entities mentioned in raw text."""
        text_lower = text.lower()
        extracted = []
        for name_lower, entity in self.entities.items():
            if name_lower in text_lower:
                extracted.append(entity)
        return extracted

    def query_triples(
        self,
        subject: Optional[str] = None,
        predicate: Optional[str] = None,
        object_: Optional[str] = None
    ) -> List[Triple]:
        """Queries triples matching specified subject, predicate, or object filters."""
        subj_clean = subject.lower().strip() if subject else None
        pred_clean = predicate.lower().strip() if predicate else None
        obj_clean = object_.lower().strip() if object_ else None

        results = []
        for t in self.triples:
            if subj_clean and t.subject != subj_clean:
                continue
            if pred_clean and t.predicate != pred_clean:
                continue
            if obj_clean and t.object_ != obj_clean:
                continue
            results.append(t)
        return results

    def get_entity_card(self, entity_name: str) -> Optional[Dict[str, Any]]:
        """Constructs an entity knowledge card for search result display."""
        clean_q = entity_name.lower().strip()
        if not clean_q:
            return None

        # 1. Exact match
        entity = self.entities.get(clean_q)

        # 2. Substring match (query in entity name or entity name in query)
        if not entity:
            for name_lower, ent in self.entities.items():
                if clean_q in name_lower or name_lower in clean_q:
                    entity = ent
                    break

        # 3. Triple relation match (if query appears in subject, predicate, or object)
        if not entity:
            for t in self.triples:
                if clean_q in t.subject or clean_q in t.object_:
                    entity = self.entities.get(t.subject)
                    if entity:
                        break

        if not entity:
            return None

        related_triples = self.query_triples(subject=entity.name)
        relations = [{"predicate": t.predicate, "object": t.object_} for t in related_triples]

        return {
            "entity": entity.to_dict(),
            "relations": relations
        }
