import sqlite3
import re
from app.services.retrieval_service import compute_keyword_score

conn = sqlite3.connect("intelligence_os_dev.db")
cursor = conn.cursor()
chunks = cursor.execute("SELECT chunk_index, content FROM document_chunks WHERE document_id = '942a1c2a74d147738a2b5722e7181f7a'").fetchall()
query = "who is the ceo of lonetex?"
query_terms = [t for t in re.findall(r"\w+", query.lower()) if len(t) > 1]

for idx, content in chunks:
    score = compute_keyword_score(content, query)
    print(f"Chunk {idx}: total score = {score}")
    for term in query_terms:
        matches = len(re.findall(r"\b" + re.escape(term) + r"\b", content.lower()))
        print(f"   term '{term}': {matches} matches")
