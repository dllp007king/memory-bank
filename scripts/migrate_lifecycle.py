"""
Migration script to add lifecycle fields to existing memories

Adds: decay_rate, lifecycle_state, superseded_by, access_count, last_accessed_at
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from memory_bank.lance_crud import get_crud
from memory_bank.lifecycle import infer_decay_rate, DEFAULT_DECAY_RATE


def migrate_add_lifecycle_fields(db_path: str = None, dry_run: bool = True):
    """
    为现有记忆添加生命周期字段

    Args:
        db_path: LanceDB database path
        dry_run: If True, don't make changes

    Returns:
        Number of memories updated
    """
    import datetime

    crud = get_crud()
    if db_path:
        crud.db_path = db_path

    # Get all memories
    memories = crud.list_memories(limit=10000)

    updated_count = 0

    for memory in memories:
        needs_update = False

        # Check if fields exist in the underlying data
        # (Some fields may be present but with None values)
        if not hasattr(memory, 'decay_rate') or memory.decay_rate == DEFAULT_DECAY_RATE:
            # Infer from content
            inferred = infer_decay_rate(memory.content)
            memory.decay_rate = inferred
            needs_update = True

        if not hasattr(memory, 'lifecycle_state') or memory.lifecycle_state == "":
            memory.lifecycle_state = "ACTIVE"
            needs_update = True

        if not hasattr(memory, 'access_count'):
            memory.access_count = 0
            needs_update = True

        if needs_update:
            memory.updated_at = datetime.datetime.now().isoformat()
            updated_count += 1

            if not dry_run:
                # Re-insert with new fields
                table = crud._get_memories_table()
                table.delete(f"id = '{memory.id}'")
                table.add([memory.to_dict()])

    return updated_count


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Migrate memories to add lifecycle fields")
    parser.add_argument("--dry-run", action="store_true", help="Don't make changes")
    parser.add_argument("--db-path", help="LanceDB database path")

    args = parser.parse_args()

    print("=" * 50)
    print("Lifecycle Migration")
    print("=" * 50)

    count = migrate_add_lifecycle_fields(
        db_path=args.db_path,
        dry_run=args.dry_run
    )

    if args.dry_run:
        print(f"[DRY RUN] Would update {count} memories")
        print("Run with --no-dry-run to apply changes")
    else:
        print(f"Updated {count} memories")
