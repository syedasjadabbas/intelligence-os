import sqlite3
import sys

sys.stdout.reconfigure(encoding='utf-8')
conn = sqlite3.connect("intelligence_os_dev.db")
cursor = conn.cursor()
for chunk in cursor.execute("SELECT id, chunk_index, page_number, content FROM document_chunks WHERE document_id = '942a1c2a74d147738a2b5722e7181f7a'").fetchall():
    print(f"=== Chunk {chunk[1]} (Page {chunk[2]}) ===")
    print(chunk[3])
