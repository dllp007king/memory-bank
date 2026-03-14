"""
Migration script to add relation history tracking fields

Adds: status, is_current, superseded_by, supersedes_target, old_confidence, replacement_reason
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from memory_bank.lance_crud import get_crud


def migrate_add_relation_history_fields(db_path: str = None, dry_run: bool = True):
    """
    为现有关系添加历史追踪字段

    Args:
        db_path: LanceDB database path
        dry_run: If True, don't make changes

    Returns:
        Number of relations updated
    """
    import datetime
    import uuid

    crud = get_crud()
    if db_path:
        crud.db_path = db_path

    # Get all relations
    relations = crud.list_relations(limit=10000)

    updated_count = 0

    for relation in relations:
        needs_update = False

        # Check if fields exist (default values indicate missing fields)
        if not hasattr(relation, 'status') or relation.status == "":
            relation.status = "ACTIVE"
            needs_update = True

        if not hasattr(relation, 'is_current'):
            relation.is_current = True
            needs_update = True

        if not hasattr(relation, 'superseded_by') or relation.superseded_by == "":
            relation.superseded_by = ""
            needs_update = True

        if not hasattr(relation, 'supersedes_target') or relation.supersedes_target == "":
            relation.supersedes_target = ""
            needs_update = True

        if not hasattr(relation, 'old_confidence'):
            relation.old_confidence = 0.0
            needs_update = True

        if not hasattr(relation, 'replacement_reason') or relation.replacement_reason == "":
            relation.replacement_reason = ""
            needs_update = True

        if not hasattr(relation, 'version'):
            relation.version = 1
            needs_update = True

        if needs_update:
            relation.updated_at = datetime.datetime.now().isoformat()
            updated_count += 1

            if not dry_run:
                # Delete old record and insert new one
                table = crud._get_relations_table()
                table.delete(f"id = '{relation.id}'")
                table.add([relation.to_dict()])

    return updated_count


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Migrate relations to add history tracking fields")
    parser.add_argument("--dry-run", action="store_true", help="Don't make changes")
    parser.add_argument("--db-path", help="LanceDB database path")

    args = parser.parse_args()

    print("=" * 50)
    print("Relation History Migration")
    print("=" * 50)

    count = migrate_add_relation_history_fields(
        db_path=args.db_path,
        dry_run=args.dry_run
    )

    if args.dry_run:
        print(f"[DRY RUN] Would update {count} relations")
        print("Run with --no-dry-run to apply changes")
    else:
        print(f"Updated {count} relations")
