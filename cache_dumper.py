"""
Cache Dumper for YeetCode FastAPI

Periodically dumps dirty cache entries to DynamoDB in batches.
Runs every 10 minutes to persist cache state to database.
"""

import os
import boto3
from typing import Dict, List
from logger import info, error, warning
from cache_manager import cache_manager, CacheType
from wal_manager import wal_manager

# DynamoDB client
ddb = boto3.client('dynamodb', region_name=os.environ.get('AWS_REGION', 'us-east-1'))

# Table names from environment
USERS_TABLE = os.environ.get('USERS_TABLE', 'Yeetcode_users')
DAILY_TABLE = os.environ.get('DAILY_TABLE', 'Daily')
DUELS_TABLE = os.environ.get('DUELS_TABLE', 'Duels')
BOUNTIES_TABLE = os.environ.get('BOUNTIES_TABLE', 'Bounties')


def chunks(lst: List, n: int):
    """Yield successive n-sized chunks from lst"""
    for i in range(0, len(lst), n):
        yield lst[i:i + n]


def convert_value_to_dynamodb(value):
    """
    Convert a single Python value to DynamoDB format (recursive helper)

    Args:
        value: Python value of any type

    Returns:
        DynamoDB formatted value with type key
    """
    if isinstance(value, bool):
        # IMPORTANT: Check bool before int (bool is subclass of int in Python)
        return {'BOOL': value}
    elif isinstance(value, str):
        return {'S': value}
    elif isinstance(value, int):
        return {'N': str(value)}
    elif isinstance(value, float):
        return {'N': str(value)}
    elif isinstance(value, dict):
        return {'M': convert_to_dynamodb_format(value)}
    elif isinstance(value, list):
        # Recursively convert each item in the list
        dynamodb_list = []
        for item in value:
            dynamodb_list.append(convert_value_to_dynamodb(item))
        return {'L': dynamodb_list}
    elif value is None:
        return {'NULL': True}
    else:
        # Fallback: convert to string
        return {'S': str(value)}


def convert_to_dynamodb_format(data: Dict) -> Dict:
    """
    Convert Python dict to DynamoDB format

    Args:
        data: Python dictionary

    Returns:
        DynamoDB formatted dictionary
    """
    dynamodb_item = {}

    for key, value in data.items():
        dynamodb_item[key] = convert_value_to_dynamodb(value)

    return dynamodb_item


def batch_write_to_dynamodb(table_name: str, items: List[Dict]) -> Dict:
    """
    Write items to DynamoDB in batches of 25

    Args:
        table_name: DynamoDB table name
        items: List of items to write (in DynamoDB format)

    Returns:
        Dictionary with success status and stats
    """
    total_written = 0
    total_failed = 0
    failed_items = []

    try:
        for batch in chunks(items, 25):  # DynamoDB limit: 25 items per batch
            request_items = {
                table_name: [
                    {'PutRequest': {'Item': item}} for item in batch
                ]
            }

            response = ddb.batch_write_item(RequestItems=request_items)

            # Handle unprocessed items
            unprocessed = response.get('UnprocessedItems', {})
            if unprocessed:
                # Retry unprocessed items once
                retry_response = ddb.batch_write_item(RequestItems=unprocessed)
                unprocessed = retry_response.get('UnprocessedItems', {})

                if unprocessed:
                    failed_count = len(unprocessed.get(table_name, []))
                    total_failed += failed_count
                    failed_items.extend(unprocessed.get(table_name, []))
                    warning(f"Failed to write {failed_count} items to {table_name} after retry")

            total_written += len(batch) - len(unprocessed.get(table_name, []))

        return {
            "success": total_failed == 0,
            "written": total_written,
            "failed": total_failed,
            "failed_items": failed_items
        }

    except Exception as e:
        error(f"Batch write to {table_name} failed: {e}")
        return {
            "success": False,
            "written": total_written,
            "failed": len(items) - total_written,
            "error": str(e)
        }


async def dump_cache_to_db() -> Dict:
    """
    Dump all dirty cache entries to DynamoDB by replaying WAL operations.

    CRITICAL FIX: Instead of dumping raw cache entries (which have wrapped structures
    like {"success": True, "data": [...]}), we now read from the WAL operation log
    which has correctly structured operations for DynamoDB updates.

    Returns:
        Dictionary with dump statistics
    """
    info("🗄️ Starting cache dump to DynamoDB via WAL operations...")

    try:
        # Get checkpoint to avoid replaying already-applied entries
        last_applied = wal_manager.get_last_applied_sequence()
        info(f"📍 Checkpoint: last_applied_sequence = {last_applied}")

        # Get WAL entries since last checkpoint (+ 1 to get next unapplied entry)
        wal_entries = wal_manager.get_entries_since(last_applied + 1)

        if not wal_entries:
            info("✅ No new WAL entries to sync")
            return {"success": True, "entries": 0, "message": "No new WAL entries"}

        info(f"📦 Found {len(wal_entries)} new WAL entries to sync to DynamoDB")

        # Deduplicate: For UPDATE operations on the same (table, key), only the latest matters.
        # INCREMENT operations must NOT be deduplicated (they are additive).
        # Process: separate INCREMENTs, deduplicate UPDATEs/PUTs, merge back in order.
        deduped_entries = []
        seen_update_keys = {}  # (table, key_tuple) -> index in deduped_entries

        for entry in wal_entries:
            operation = entry.get('operation')
            table = entry.get('table')
            key = entry.get('key', {})

            if operation in ("UPDATE", "PUT"):
                # Create a hashable key identifier
                key_tuple = (table, tuple(sorted(key.items())))
                if key_tuple in seen_update_keys:
                    # Replace old entry with newer one (merge data for UPDATEs)
                    old_idx = seen_update_keys[key_tuple]
                    old_entry = deduped_entries[old_idx]
                    if operation == "UPDATE" and old_entry.get('operation') == "UPDATE":
                        # Merge data fields (newer overwrites older)
                        merged_data = {**old_entry.get('data', {}), **entry.get('data', {})}
                        entry = {**entry, 'data': merged_data}
                    deduped_entries[old_idx] = entry
                else:
                    seen_update_keys[key_tuple] = len(deduped_entries)
                    deduped_entries.append(entry)
            else:
                # INCREMENT, DELETE, etc. - keep all of them
                deduped_entries.append(entry)

        # Remove None placeholders (shouldn't happen but be safe)
        deduped_entries = [e for e in deduped_entries if e is not None]

        original_count = len(wal_entries)
        info(f"🔄 Deduplicated {original_count} -> {len(deduped_entries)} WAL entries")

        # Track the max sequence from ALL original entries so we can advance the checkpoint
        # past all the redundant entries we deduplicated away
        max_original_sequence = max(e.get('sequence', -1) for e in wal_entries)

        # Limit batch size to prevent hanging (process max 500 entries per dump cycle)
        MAX_ENTRIES_PER_DUMP = 500
        entries_to_process = deduped_entries[:MAX_ENTRIES_PER_DUMP]
        processing_all = len(deduped_entries) <= MAX_ENTRIES_PER_DUMP
        if not processing_all:
            info(f"⚡ Processing first {MAX_ENTRIES_PER_DUMP} of {len(deduped_entries)} entries this cycle")
            # When not processing all, we can only advance checkpoint to the max sequence
            # of entries we're actually processing
            max_original_sequence = max(e.get('sequence', -1) for e in entries_to_process)

        # Track stats
        total_synced = 0
        total_failed = 0
        errors = []

        # Process each WAL operation until first failure
        # CRITICAL: We must stop on first failure to prevent double-applying later INCREMENTs
        # Example: seq 1 ✅, seq 2 ❌, seq 3 INCREMENT ✅ (checkpoint=1)
        # Next run: seq 2 fails again, seq 3 replayed → INCREMENT applied twice!
        for entry in entries_to_process:
            operation = entry.get('operation')
            table = entry.get('table')
            key = entry.get('key')
            data = entry.get('data')

            # Track sequence for checkpoint management
            entry_sequence = entry.get('sequence', -1)

            # Validate based on operation type
            # DELETE operations don't require data, all others do
            if operation == "DELETE":
                if not all([operation, table, key]):
                    total_failed += 1
                    error_msg = f"Incomplete DELETE entry at sequence {entry_sequence}: {entry}"
                    warning(error_msg)
                    errors.append(error_msg)
                    # STOP processing to prevent replaying later entries (especially INCREMENTs)
                    break
            else:
                if not all([operation, table, key, data]):
                    total_failed += 1
                    error_msg = f"Incomplete {operation} entry at sequence {entry_sequence}: {entry}"
                    warning(error_msg)
                    errors.append(error_msg)
                    # STOP processing to prevent replaying later entries (especially INCREMENTs)
                    break

            try:
                if operation == "UPDATE":
                    # Build UpdateExpression from data
                    # Always alias field names with ExpressionAttributeNames to avoid
                    # reserved keyword conflicts (users, date, status, name, etc.)
                    update_expr_parts = []
                    expr_attr_names = {}
                    expr_attr_values = {}

                    for field, value in data.items():
                        alias = f"#f_{field}"
                        update_expr_parts.append(f"{alias} = :{field}")
                        expr_attr_names[alias] = field
                        expr_attr_values[f":{field}"] = convert_value_to_dynamodb(value)

                    # Convert key to DynamoDB format
                    dynamodb_key = {}
                    for k, v in key.items():
                        if isinstance(v, str):
                            dynamodb_key[k] = {'S': v}
                        elif isinstance(v, (int, float)):
                            dynamodb_key[k] = {'N': str(v)}

                    # Perform update
                    ddb.update_item(
                        TableName=table,
                        Key=dynamodb_key,
                        UpdateExpression=f"SET {', '.join(update_expr_parts)}",
                        ExpressionAttributeNames=expr_attr_names,
                        ExpressionAttributeValues=expr_attr_values
                    )

                elif operation == "PUT":
                    # Full item put - merge key and data
                    item = {**key, **data}
                    dynamodb_item = convert_to_dynamodb_format(item)

                    ddb.put_item(
                        TableName=table,
                        Item=dynamodb_item
                    )

                elif operation == "DELETE":
                    # Convert key to DynamoDB format
                    dynamodb_key = {}
                    for k, v in key.items():
                        if isinstance(v, str):
                            dynamodb_key[k] = {'S': v}
                        elif isinstance(v, (int, float)):
                            dynamodb_key[k] = {'N': str(v)}

                    ddb.delete_item(
                        TableName=table,
                        Key=dynamodb_key
                    )

                elif operation == "INCREMENT":
                    # Build increment expression with aliased field names
                    update_expr_parts = []
                    expr_attr_names = {}
                    expr_attr_values = {}

                    for field, value in data.items():
                        alias = f"#f_{field}"
                        update_expr_parts.append(f"{alias} = if_not_exists({alias}, :zero) + :{field}")
                        expr_attr_names[alias] = field
                        expr_attr_values[f":{field}"] = {'N': str(value)}

                    expr_attr_values[":zero"] = {'N': '0'}

                    # Convert key to DynamoDB format
                    dynamodb_key = {}
                    for k, v in key.items():
                        if isinstance(v, str):
                            dynamodb_key[k] = {'S': v}
                        elif isinstance(v, (int, float)):
                            dynamodb_key[k] = {'N': str(v)}

                    ddb.update_item(
                        TableName=table,
                        Key=dynamodb_key,
                        UpdateExpression=f"SET {', '.join(update_expr_parts)}",
                        ExpressionAttributeNames=expr_attr_names,
                        ExpressionAttributeValues=expr_attr_values
                    )

                else:
                    # Unknown operation type - fail explicitly
                    total_failed += 1
                    error_msg = f"Unknown WAL operation type '{operation}' at sequence {entry_sequence}"
                    warning(error_msg)
                    errors.append(error_msg)
                    # STOP processing to prevent replaying later entries (especially INCREMENTs)
                    break

                total_synced += 1

            except Exception as e:
                total_failed += 1
                error_msg = f"Failed to sync WAL entry at sequence {entry_sequence} to {table}: {e}"
                error(error_msg)
                errors.append(error_msg)
                # STOP processing to prevent replaying later entries (especially INCREMENTs)
                break

        # Mark success if all synced
        if total_failed == 0:
            # Advance checkpoint to cover all original WAL entries (including deduplicated ones)
            wal_manager.set_last_applied_sequence(max_original_sequence)

            # Clear WAL entries up to the max sequence we covered
            wal_manager.clear_up_to(max_original_sequence)

            # Note: We intentionally DON'T call cache_manager.mark_synced() here because:
            # - Cache entries don't track their WAL sequence number
            # - We can't safely determine which cache entries map to synced WAL entries
            # - Dirty flags in cache are eventually consistent (background task marks them synced)
            # - The WAL checkpoint is our source of truth for what's been persisted

            info(f"✅ Cache dump complete: {total_synced} WAL operations synced to DynamoDB (checkpoint: {max_original_sequence}, deduped from {original_count})")

            return {
                "success": True,
                "entries": total_synced,
                "failed": 0,
                "checkpoint": max_original_sequence
            }
        else:
            warning(f"⚠️ Cache dump partially failed: {total_failed}/{len(wal_entries)} operations failed")

            return {
                "success": False,
                "entries": len(wal_entries),
                "synced": total_synced,
                "failed": total_failed,
                "errors": errors
            }

    except Exception as e:
        error(f"❌ Cache dump failed: {e}")
        return {
            "success": False,
            "error": str(e)
        }

