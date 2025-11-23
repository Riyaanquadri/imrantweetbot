#!/usr/bin/env python3
"""
Manual review queue CLI tool.

Usage:
    python3 -m app.review_cli list          # Show pending reviews
    python3 -m app.review_cli approve <id>  # Approve and post
    python3 -m app.review_cli reject <id>   # Reject draft
    python3 -m app.review_cli stats         # Show stats
    python3 -m app.review_cli export        # Export audit log
"""
import sys
import argparse
from .audit_db import get_audit_db
from .logger import logger

audit_db = get_audit_db()


def list_pending():
    """List pending reviews."""
    queue = audit_db.get_review_queue(only_unreviewed=True)
    
    if not queue:
        print("✓ No pending reviews!")
        return
    
    print(f"\n📋 Manual Review Queue ({len(queue)} pending):\n")
    
    for item in queue:
        print(f"ID: {item['draft_id']} | Priority: {item['priority']} | Reason: {item['reason']}")
        print(f"   Text: {item['text'][:80]}...")
        print(f"   Flags: {item['safety_flags']}")
        print()


def approve_draft(draft_id: int, reviewer: str = "cli_user", notes: str = "Approved via CLI"):
    """Approve a draft for posting."""
    try:
        audit_db.approve_for_posting(draft_id, reviewer, notes)
        print(f"✓ Approved draft {draft_id}")
    except Exception as e:
        logger.error(f"Error approving draft: {e}")
        print(f"✗ Error: {e}")


def reject_draft(draft_id: int, reason: str = "User rejected", reviewer: str = "cli_user", notes: str = ""):
    """Reject a draft."""
    try:
        audit_db.reject_draft(draft_id, reviewer, reason, notes)
        print(f"✓ Rejected draft {draft_id}")
    except Exception as e:
        logger.error(f"Error rejecting draft: {e}")
        print(f"✗ Error: {e}")


def show_stats():
    """Show audit statistics."""
    stats = audit_db.get_stats()
    
    print("\n📊 Audit Log Statistics:\n")
    print(f"  Total drafts generated: {stats['total_drafts']}")
    print(f"  Tweets posted:          {stats['posted_tweets']}")
    print(f"  Drafts rejected:        {stats['rejected_drafts']}")
    print(f"  Pending reviews:        {stats['pending_reviews']}")
    print()


def export_log():
    """Export audit log."""
    try:
        audit_db.export_audit_log()
        print("✓ Exported audit log to audit_export.json")
    except Exception as e:
        logger.error(f"Error exporting: {e}")
        print(f"✗ Error: {e}")


def main():
    parser = argparse.ArgumentParser(description='Manual review queue manager')
    subparsers = parser.add_subparsers(dest='command', help='Command to run')
    
    # list command
    subparsers.add_parser('list', help='List pending reviews')
    
    # approve command
    approve_parser = subparsers.add_parser('approve', help='Approve a draft')
    approve_parser.add_argument('draft_id', type=int, help='Draft ID to approve')
    
    # reject command
    reject_parser = subparsers.add_parser('reject', help='Reject a draft')
    reject_parser.add_argument('draft_id', type=int, help='Draft ID to reject')
    
    # stats command
    subparsers.add_parser('stats', help='Show statistics')
    
    # export command
    subparsers.add_parser('export', help='Export audit log')
    
    args = parser.parse_args()
    
    if args.command == 'list':
        list_pending()
    elif args.command == 'approve':
        approve_draft(args.draft_id)
    elif args.command == 'reject':
        reject_draft(args.draft_id)
    elif args.command == 'stats':
        show_stats()
    elif args.command == 'export':
        export_log()
    else:
        parser.print_help()


if __name__ == '__main__':
    main()
