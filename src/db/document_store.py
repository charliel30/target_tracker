"""
document_store.py — Simple JSON file-based store for raw temporal target data.

This is the most straightforward of the three stores. It keeps a nested dict
on disk and exposes basic query helpers — no embeddings, no SQL, just JSON.

Structure on disk:
{
    "Viktor Petrov": {
        "suspicious_activity":    [ {...}, ... ],
        "nonsuspicious_activity": [ {...}, ... ],
        "whereabouts":            [ {...}, ... ],
        "prior":                  [ {...}, ... ],
    },
    ...
}
"""

import json
import os


class DocumentStore:
    """
    Stores raw temporal data for each target as a nested JSON dict.

    All writes go straight to disk so the file is always up to date.
    Reads are served from the in-memory dict for speed.
    """

    def __init__(self, store_path: str):
        # Where the JSON file lives on disk
        self.store_path = store_path

        # In-memory copy of the store: { target_name: { category: [entries] } }
        self.data: dict = {}

        # Load any previously saved data from disk
        self._load()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def load_targets(self, targets: dict) -> None:
        """
        Extract temporal data from the targets dict and save it to the store.
        Replaces any existing data.
        """
        self.data = {}

        for target_name, info in targets.items():
            self.data[target_name] = {
                # Each category maps to a list of raw dicts from the source data
                "suspicious_activity":    info.get("suspicious_activities", []),
                "nonsuspicious_activity": info.get("nonsuspicious_activities", []),
                "whereabouts":            info.get("known_whereabouts", []),
                "prior":                  info.get("priors", []),
            }

        self._save()

    def add_entry(self, target_name: str, category: str, data: dict) -> None:
        """
        Append a single entry under target_name / category.
        Creates the target or category bucket if it doesn't exist yet.
        """
        # Make sure the target exists in the store
        if target_name not in self.data:
            self.data[target_name] = {}

        # Make sure the category list exists under this target
        if category not in self.data[target_name]:
            self.data[target_name][category] = []

        self.data[target_name][category].append(data)
        self._save()

    def get_entries(self, target_name: str, category: str = None):
        """
        Return entries for a target, optionally filtered to one category.

        - No category → returns the full dict of { category: [entries] }
        - With category → returns the list of entries for that category
        - Unknown target or category → returns {} or [] respectively
        """
        target_data = self.data.get(target_name, {})

        if category is None:
            return target_data

        return target_data.get(category, [])

    def search_text(self, query: str) -> list:
        """
        Case-insensitive substring search across all entry descriptions.

        Looks inside the "description" field (activities, priors) and the
        "city" field (whereabouts). Returns a flat list of matches in the form:
            { "target_name": str, "category": str, "entry": dict }
        """
        query_lower = query.lower()
        results = []

        for target_name, categories in self.data.items():
            for category, entries in categories.items():
                for entry in entries:
                    # Build a single searchable string from the entry's text fields
                    searchable = " ".join(
                        str(v) for v in entry.values() if isinstance(v, str)
                    ).lower()

                    if query_lower in searchable:
                        results.append({
                            "target_name": target_name,
                            "category": category,
                            "entry": entry,
                        })

        return results

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def _save(self) -> None:
        """Write the current in-memory data to the JSON file."""
        parent = os.path.dirname(self.store_path)
        if parent:
            os.makedirs(parent, exist_ok=True)
        with open(self.store_path, "w") as f:
            json.dump(self.data, f, indent=2)

    def _load(self) -> None:
        """Read the JSON file into memory if it exists."""
        if os.path.exists(self.store_path):
            with open(self.store_path, "r") as f:
                self.data = json.load(f)
