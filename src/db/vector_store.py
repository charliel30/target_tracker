"""
vector_store.py — In-memory vector store for semantic search over target data.

Generates embeddings via the OpenAI API and compares them using cosine
similarity. All entries are kept in memory and persisted to a JSON file so
they survive restarts.

Example query: "targets caught stealing electronics in Texas"

NOTE: When using Ollama as the LLM provider, the embeddings endpoint may not
be supported by the local model. The store will raise an error in that case.
For full semantic search, switch the provider to "openai" in config.yaml.
"""

import hashlib
import json
import math
import os
from typing import Optional

from src.config import config, get_openai_client
from src.logging_config import get_agent_logger

log = get_agent_logger("VectorStore")


class VectorStore:
    """
    Semantic search over target data using OpenAI embeddings + cosine similarity.

    Each entry in the store is a small piece of text derived from a target's
    temporal data (an activity description, a whereabouts note, a prior).
    Querying embeds the query string and ranks all entries by similarity.

    Embeddings are cached: on startup, we hash the source targets data and
    compare it to the hash stored alongside the vector store file. If they
    match, we skip the expensive embedding generation and load from cache.
    """

    def __init__(self, store_path: str):
        # Where we persist the store on disk (relative to project root)
        self.store_path = store_path

        # Path for the hash file that tracks whether embeddings are stale
        self._hash_path = store_path + ".hash"

        # In-memory list of entries. Each entry is a dict:
        #   { "target_name": str, "category": str, "text": str, "embedding": list[float] }
        self.entries: list[dict] = []

        # Load any previously saved entries from disk
        self._load()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def load_targets(self, targets: dict) -> None:
        """
        Ingest the full targets dict and generate an embedding for each
        piece of temporal data (activities, whereabouts, priors, major events).

        Skips regeneration if the targets data hasn't changed since the last
        run (compares a SHA-256 hash of the serialised targets dict).
        """
        # Check if we can skip — hash the targets data deterministically
        current_hash = self._hash_targets(targets)
        saved_hash = self._load_hash()

        if current_hash == saved_hash and self.entries:
            log.info(
                f"Targets data unchanged (hash {current_hash[:12]}…) — "
                f"reusing {len(self.entries)} cached embeddings."
            )
            return

        log.info("Targets data changed or no cache — generating embeddings...")
        self.entries = []

        for target_name, data in targets.items():
            # --- Suspicious activities ---
            for activity in data.get("suspicious_activities", []):
                text = (
                    f"{target_name} suspicious activity on "
                    f"{activity.get('timestamp', 'unknown date')}: "
                    f"{activity.get('description', '')}"
                )
                embedding = await self._embed(text)
                self.entries.append({
                    "target_name": target_name,
                    "category": "suspicious_activity",
                    "text": text,
                    "embedding": embedding,
                })

            # --- Non-suspicious activities ---
            for activity in data.get("nonsuspicious_activities", []):
                text = (
                    f"{target_name} activity on "
                    f"{activity.get('timestamp', 'unknown date')}: "
                    f"{activity.get('description', '')}"
                )
                embedding = await self._embed(text)
                self.entries.append({
                    "target_name": target_name,
                    "category": "nonsuspicious_activity",
                    "text": text,
                    "embedding": embedding,
                })

            # --- Known whereabouts ---
            for whereabout in data.get("known_whereabouts", []):
                text = (
                    f"{target_name} was in {whereabout.get('city', 'unknown')} "
                    f"from {whereabout.get('start_date', '?')} "
                    f"to {whereabout.get('end_date', '?')}."
                )
                embedding = await self._embed(text)
                self.entries.append({
                    "target_name": target_name,
                    "category": "whereabouts",
                    "text": text,
                    "embedding": embedding,
                })

            # --- Criminal priors ---
            for prior in data.get("priors", []):
                text = (
                    f"{target_name} prior on {prior.get('date', 'unknown date')}: "
                    f"{prior.get('description', '')}"
                )
                embedding = await self._embed(text)
                self.entries.append({
                    "target_name": target_name,
                    "category": "prior",
                    "text": text,
                    "embedding": embedding,
                })

            # --- Major events (deaths, arrests, destruction, etc.) ---
            for event in data.get("major_events", []):
                text = (
                    f"{target_name} major event ({event.get('event_type', 'unknown')}) "
                    f"on {event.get('date', 'unknown date')}: "
                    f"{event.get('description', '')}"
                )
                embedding = await self._embed(text)
                self.entries.append({
                    "target_name": target_name,
                    "category": "major_event",
                    "text": text,
                    "embedding": embedding,
                })

        self._save()
        self._save_hash(current_hash)
        log.info(f"Cached {len(self.entries)} embeddings (hash {current_hash[:12]}…).")

    async def add_entry(self, target_name: str, category: str, text: str) -> None:
        """
        Add a single searchable entry (e.g., a newly ingested activity).
        Generates an embedding for the text and appends it to the store.
        """
        embedding = await self._embed(text)
        self.entries.append({
            "target_name": target_name,
            "category": category,
            "text": text,
            "embedding": embedding,
        })
        self._save()

    async def search(self, query: str, top_k: int = 10) -> list:
        """
        Embed the query, then rank all stored entries by cosine similarity.
        Returns the top_k most similar entries (without their raw embeddings).
        """
        if not self.entries:
            return []

        query_embedding = await self._embed(query)

        # Score every entry
        scored = []
        for entry in self.entries:
            score = self._cosine_similarity(query_embedding, entry["embedding"])
            scored.append({
                "target_name": entry["target_name"],
                "category": entry["category"],
                "text": entry["text"],
                "score": round(score, 4),
            })

        # Sort descending by score and return the top_k
        scored.sort(key=lambda x: x["score"], reverse=True)
        return scored[:top_k]

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _cosine_similarity(self, a: list, b: list) -> float:
        """
        Cosine similarity between two vectors using only the math module.
        Returns a value between -1 and 1 (1 = identical direction).
        """
        dot_product = sum(x * y for x, y in zip(a, b))
        magnitude_a = math.sqrt(sum(x * x for x in a))
        magnitude_b = math.sqrt(sum(x * x for x in b))

        if magnitude_a == 0 or magnitude_b == 0:
            return 0.0

        return dot_product / (magnitude_a * magnitude_b)

    async def _embed(self, text: str) -> list:
        """
        Call the OpenAI embeddings API and return the embedding vector.

        Uses text-embedding-3-small for OpenAI. For Ollama, the embeddings
        endpoint may not be available — see the module-level note.
        """
        client = get_openai_client()

        # Use a fixed embedding model for OpenAI; for Ollama we fall back to
        # whatever model is configured (though results may vary).
        model = config.llm.embedding_model

        response = await client.embeddings.create(input=text, model=model)
        return response.data[0].embedding

    def _save(self) -> None:
        """Persist the current entries to the JSON file on disk."""
        parent = os.path.dirname(self.store_path)
        if parent:
            os.makedirs(parent, exist_ok=True)
        with open(self.store_path, "w") as f:
            json.dump(self.entries, f)

    def _load(self) -> None:
        """Load entries from the JSON file if it exists."""
        if os.path.exists(self.store_path):
            with open(self.store_path, "r") as f:
                self.entries = json.load(f)

    # ------------------------------------------------------------------
    # Hash-based cache invalidation
    # ------------------------------------------------------------------

    @staticmethod
    def _hash_targets(targets: dict) -> str:
        """SHA-256 hash of the targets dict (deterministic via sort_keys)."""
        raw = json.dumps(targets, sort_keys=True).encode()
        return hashlib.sha256(raw).hexdigest()

    def _load_hash(self) -> str | None:
        """Read the previously saved hash, or None if no cache exists."""
        if os.path.exists(self._hash_path):
            with open(self._hash_path, "r") as f:
                return f.read().strip()
        return None

    def _save_hash(self, hash_value: str) -> None:
        """Write the hash alongside the vector store file."""
        parent = os.path.dirname(self._hash_path)
        if parent:
            os.makedirs(parent, exist_ok=True)
        with open(self._hash_path, "w") as f:
            f.write(hash_value)
