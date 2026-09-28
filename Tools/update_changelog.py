#!/usr/bin/env python3
"""
Assemble changelog .yml parts into a changelog file.

Entry IDs are append-only and never renumbered. This is required by the client,
which persists the last-read ID between sessions. Old entries may be pruned, but
surviving IDs remain stable and new entries always use max(existing id) + 1.

usage: update_changelog.py <changelog-file> <parts-dir> --category "Main"
"""

import argparse
import datetime
import os
from typing import Any

import yaml

MAX_ENTRIES = 1500
CATEGORY_MAIN = "Main"


# Prevent PyYAML from turning ISO-8601 strings into datetime instances and then
# serializing them in a different format on every changelog update.
class NoDatesSafeLoader(yaml.SafeLoader):
    @classmethod
    def remove_implicit_resolver(cls, tag_to_remove):
        if "yaml_implicit_resolvers" not in cls.__dict__:
            cls.yaml_implicit_resolvers = cls.yaml_implicit_resolvers.copy()

        for first_letter, mappings in cls.yaml_implicit_resolvers.items():
            cls.yaml_implicit_resolvers[first_letter] = [
                (tag, regexp) for tag, regexp in mappings if tag != tag_to_remove
            ]


NoDatesSafeLoader.remove_implicit_resolver("tag:yaml.org,2002:timestamp")


def entry_sort_key(entry: dict[str, Any]) -> tuple[str, int]:
    return (str(entry.get("time", "")), int(entry.get("id", 0)))


def load_yaml(path: str) -> dict[str, Any]:
    with open(path, "r", encoding="utf-8-sig") as f:
        return yaml.load(f, Loader=NoDatesSafeLoader) or {}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("changelog_file")
    parser.add_argument("parts_dir")
    parser.add_argument("--category", default=CATEGORY_MAIN)
    args = parser.parse_args()
    category = args.category

    current_data = load_yaml(args.changelog_file)
    entries_list: list[dict[str, Any]] = current_data.get("Entries", [])
    max_id = max((int(entry.get("id", 0)) for entry in entries_list), default=0)
    existing_urls = {str(entry["url"]) for entry in entries_list if entry.get("url")}

    if raw is None:
        raw = {}
    current_data: dict[str, Any] = raw

    # Get the existing entries, or an empty list if the key is missing.
    entries_list: List[Any] = current_data.get("Entries", [])
    max_id = max(map(lambda e: e["id"], entries_list), default=0)

    # Cancelled runs and the daily cron re-parse the same PR window; a part
    # already in the file must not append a second copy.
    existing = {(e.get("author"), e.get("time"), e.get("url")) for e in entries_list}

    for partname in os.listdir(args.parts_dir):
        if not partname.endswith(".yml"):
            continue

        partpath = os.path.join(args.parts_dir, partname)
        print(partpath)
        partyaml = load_yaml(partpath)

        # Historical hand-written parts did not always have a category. If the
        # workflow is assembling a specific changelog, an untagged part belongs
        # to that target rather than becoming permanently stuck as "Main".
        part_category = partyaml.get("category", category)
        if part_category != category:
            print(f"Skipping: wrong category ({part_category} vs {category})")
            continue

        author = partyaml["author"]
        time = partyaml.get(
            "time", datetime.datetime.now(datetime.timezone.utc).isoformat()
        )
        changes = partyaml["changes"]
        url = partyaml.get("url")
        labels = partyaml.get("labels", [])

        if (author, time, url) in existing:
            print(f"Skipping: already in changelog ({url})")
            continue

        if not isinstance(changes, list):
            changes = [changes]

        if url and str(url) in existing_urls:
            print(f"Skipping duplicate changelog URL: {url}")
            os.remove(partpath)
            continue

        if changes:
            max_id += 1
            entry: dict[str, Any] = {
                "author": author,
                "time": time,
                "changes": changes,
                "id": max_id,
                "url": url,
            }
            if labels:
                entry["labels"] = labels

            entries_list.append(entry)
            if url:
                existing_urls.add(str(url))

            entries_list.append(
                {
                    "author": author,
                    "time": time,
                    "changes": changes,
                    "id": new_id,
                    "url": url,
                }
            )
            existing.add((author, time, url))
        os.remove(partpath)

    entries_list.sort(key=entry_sort_key)
    print(f"Have {len(entries_list)} changelog entries")

    overflow = len(entries_list) - MAX_ENTRIES
    if overflow > 0:
        print(f"Removing {overflow} old entries while preserving stable IDs.")
        entries_list = entries_list[overflow:]

    new_data = {"Entries": entries_list}
    for key, value in current_data.items():
        if key != "Entries":
            new_data[key] = value

    with open(args.changelog_file, "w", encoding="utf-8-sig") as f:
        yaml.safe_dump(new_data, f, allow_unicode=True, sort_keys=False)


if __name__ == "__main__":
    main()
