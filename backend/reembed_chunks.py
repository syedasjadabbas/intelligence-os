import asyncio
import json
import logging
from pathlib import Path
import sqlite3
from typing import List

from app.core.config import settings
from app.services.chunker import TextChunker
from app.services.embedding_service import embedding_service
from app.services.pdf_parser import parse_pdf

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("reembed")


async def reembed_all_chunks():
    db_path = Path(__file__).parent / "intelligence_os_dev.db"
    if not db_path.exists():
        logger.error(f"Database not found at {db_path}")
        return

    logger.info(f"Opening database: {db_path}")
    conn = sqlite3.connect(str(db_path))
    c = conn.cursor()

    # Get all distinct documents
    c.execute("SELECT id, org_id, title, file_path FROM documents")
    docs = c.fetchall()
    logger.info(f"Found {len(docs)} documents in database.")

    for doc_id, org_id, title, file_path_str in docs:
        logger.info(f"Processing document {doc_id} ('{title}') for org {org_id}...")

        # Find PDF file
        candidates = [
            Path(file_path_str) if file_path_str else None,
            settings.upload_path / str(org_id) / f"{doc_id}.pdf",
            Path(__file__).parent / "uploads" / str(org_id) / f"{doc_id}.pdf",
        ]
        pdf_path = next((p for p in candidates if p and p.is_file()), None)

        if pdf_path:
            logger.info(f"Found PDF on disk: {pdf_path}. Re-parsing with enhanced heading detection...")
            pages = parse_pdf(pdf_path)
            chunker = TextChunker()
            new_chunks = chunker.chunk_pages(pages)
            logger.info(f"Generated {len(new_chunks)} chunks for '{title}'.")

            contents = [ch.content for ch in new_chunks]
            embeddings = await embedding_service.generate_embeddings_batch(contents)

            # Delete old chunks for this document and insert newly parsed/embedded chunks
            c.execute("DELETE FROM document_chunks WHERE document_id = ?", (doc_id,))
            for ch, emb in zip(new_chunks, embeddings):
                import uuid
                chunk_uuid = str(uuid.uuid4()).replace("-", "")
                emb_json = json.dumps(emb)
                c.execute(
                    """
                    INSERT INTO document_chunks (
                        id, document_id, org_id, chunk_index, content, 
                        page_number, section_heading, embedding
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        chunk_uuid,
                        doc_id,
                        org_id,
                        ch.chunk_index,
                        ch.content,
                        ch.page_number,
                        ch.section_heading,
                        emb_json,
                    ),
                )
            logger.info(f"Successfully re-embedded and saved {len(new_chunks)} chunks for {doc_id}.")
        else:
            logger.info(f"No PDF found for {doc_id}. Re-embedding existing chunks from DB...")
            c.execute(
                "SELECT id, content FROM document_chunks WHERE document_id = ? ORDER BY chunk_index",
                (doc_id,),
            )
            existing_chunks = c.fetchall()
            if existing_chunks:
                contents = [row[1] for row in existing_chunks]
                embeddings = await embedding_service.generate_embeddings_batch(contents)
                for (chunk_id, _), emb in zip(existing_chunks, embeddings):
                    emb_json = json.dumps(emb)
                    c.execute(
                        "UPDATE document_chunks SET embedding = ? WHERE id = ?",
                        (emb_json, chunk_id),
                    )
                logger.info(f"Updated embeddings for {len(existing_chunks)} existing chunks.")

    conn.commit()
    conn.close()
    logger.info("Re-embedding completed successfully.")


if __name__ == "__main__":
    asyncio.run(reembed_all_chunks())
