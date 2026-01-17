#!/usr/bin/env python3
"""
Embedding Generation Script for TheReceipts.

Backfills embeddings for existing claim cards or generates embeddings for new ones.
Can be run manually or as part of a migration/maintenance task.

Usage:
    python scripts/generate_embeddings.py [--all] [--claim-id <uuid>] [--batch-size 100]

Options:
    --all              Generate embeddings for all claim cards (including those with existing embeddings)
    --claim-id <uuid>  Generate embedding for a specific claim card
    --batch-size <n>   Number of claim cards to process in each batch (default: 100)
    --skip-existing    Skip claim cards that already have embeddings (default behavior)
"""

import asyncio
import argparse
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from uuid import UUID
from sqlalchemy import select
from database.session import AsyncSessionLocal
from database.models import ClaimCard
from database.repositories import ClaimCardRepository
from services.embedding import EmbeddingService, EmbeddingServiceError


async def generate_embeddings_for_all(
    skip_existing: bool = True,
    batch_size: int = 100
) -> dict:
    """
    Generate embeddings for all claim cards.

    Args:
        skip_existing: Skip claim cards that already have embeddings
        batch_size: Number of claim cards to process per batch

    Returns:
        Dictionary with statistics:
        - total: Total claim cards processed
        - generated: Number of embeddings generated
        - skipped: Number of claim cards skipped (already have embeddings)
        - failed: Number of claim cards that failed to generate embeddings
    """
    stats = {
        "total": 0,
        "generated": 0,
        "skipped": 0,
        "failed": 0
    }

    try:
        embedding_service = EmbeddingService()
    except EmbeddingServiceError as e:
        print(f"Error initializing embedding service: {e}")
        return stats

    async with AsyncSessionLocal() as session:
        repo = ClaimCardRepository(session)

        # Query all claim cards
        result = await session.execute(select(ClaimCard))
        claim_cards = result.scalars().all()

        stats["total"] = len(claim_cards)

        print(f"Found {stats['total']} claim cards")

        # Process in batches
        for i in range(0, len(claim_cards), batch_size):
            batch = claim_cards[i:i + batch_size]
            print(f"\nProcessing batch {i // batch_size + 1} ({len(batch)} claim cards)...")

            for claim_card in batch:
                # Skip if already has embedding (unless --all flag)
                if skip_existing and claim_card.embedding is not None:
                    stats["skipped"] += 1
                    print(f"  Skipped: {claim_card.id} (already has embedding)")
                    continue

                # Generate embedding using claim_text
                try:
                    print(f"  Generating embedding for: {claim_card.id}")
                    embedding = await embedding_service.generate_embedding(
                        claim_card.claim_text
                    )

                    # Update claim card
                    success = await repo.upsert_embedding(claim_card.id, embedding)

                    if success:
                        stats["generated"] += 1
                        print(f"  ✓ Generated embedding for: {claim_card.id}")
                    else:
                        stats["failed"] += 1
                        print(f"  ✗ Failed to update: {claim_card.id}")

                except EmbeddingServiceError as e:
                    stats["failed"] += 1
                    print(f"  ✗ Failed to generate embedding for {claim_card.id}: {e}")

            # Commit batch
            await session.commit()
            print(f"Batch {i // batch_size + 1} committed")

    return stats


async def generate_embedding_for_claim(claim_id: UUID) -> bool:
    """
    Generate embedding for a specific claim card.

    Args:
        claim_id: UUID of the claim card

    Returns:
        True if successful, False otherwise
    """
    try:
        embedding_service = EmbeddingService()
    except EmbeddingServiceError as e:
        print(f"Error initializing embedding service: {e}")
        return False

    async with AsyncSessionLocal() as session:
        repo = ClaimCardRepository(session)

        # Get claim card
        claim_card = await repo.get_by_id(claim_id)

        if not claim_card:
            print(f"Claim card not found: {claim_id}")
            return False

        # Generate embedding
        try:
            print(f"Generating embedding for claim card: {claim_id}")
            embedding = await embedding_service.generate_embedding(
                claim_card.claim_text
            )

            # Update claim card
            success = await repo.upsert_embedding(claim_id, embedding)

            if success:
                await session.commit()
                print(f"✓ Successfully generated embedding for: {claim_id}")
                return True
            else:
                print(f"✗ Failed to update embedding for: {claim_id}")
                return False

        except EmbeddingServiceError as e:
            print(f"✗ Failed to generate embedding: {e}")
            return False


def print_stats(stats: dict):
    """Print statistics summary."""
    print("\n" + "=" * 60)
    print("EMBEDDING GENERATION SUMMARY")
    print("=" * 60)
    print(f"Total claim cards:      {stats['total']}")
    print(f"Embeddings generated:   {stats['generated']}")
    print(f"Skipped (existing):     {stats['skipped']}")
    print(f"Failed:                 {stats['failed']}")
    print("=" * 60)


async def main():
    """Main entry point for the script."""
    parser = argparse.ArgumentParser(
        description="Generate embeddings for TheReceipts claim cards"
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Generate embeddings for all claim cards (including those with existing embeddings)"
    )
    parser.add_argument(
        "--claim-id",
        type=str,
        help="Generate embedding for a specific claim card (UUID)"
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=100,
        help="Batch size for processing claim cards (default: 100)"
    )

    args = parser.parse_args()

    if args.claim_id:
        # Generate embedding for specific claim card
        try:
            claim_id = UUID(args.claim_id)
            success = await generate_embedding_for_claim(claim_id)
            sys.exit(0 if success else 1)
        except ValueError:
            print(f"Error: Invalid UUID format: {args.claim_id}")
            sys.exit(1)
    else:
        # Generate embeddings for all claim cards
        skip_existing = not args.all
        print(f"Generating embeddings for all claim cards...")
        print(f"Skip existing: {skip_existing}")
        print(f"Batch size: {args.batch_size}")

        stats = await generate_embeddings_for_all(
            skip_existing=skip_existing,
            batch_size=args.batch_size
        )

        print_stats(stats)

        # Exit with error code if any failures
        sys.exit(1 if stats["failed"] > 0 else 0)


if __name__ == "__main__":
    asyncio.run(main())
