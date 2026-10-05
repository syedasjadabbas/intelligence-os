import sqlite3

conn = sqlite3.connect("intelligence_os_dev.db")
cursor = conn.cursor()
tables = [row[0] for row in cursor.execute("SELECT name FROM sqlite_master WHERE type='table';").fetchall()]
print("Tables:", tables)

for t in ["organizations", "users", "documents", "document_chunks"]:
    if t in tables:
        count = cursor.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
        print(f"{t} count: {count}")
        if t == "documents":
            for doc in cursor.execute("SELECT id, org_id, title, status FROM documents").fetchall():
                print("  Doc:", doc)
        if t == "users":
            for u in cursor.execute("SELECT id, org_id, email FROM users").fetchall():
                print("  User:", u)
        if t == "document_chunks":
            for chunk in cursor.execute("SELECT id, document_id, chunk_index, page_number, content FROM document_chunks LIMIT 5").fetchall():
                print(f"  Chunk: doc={chunk[1]} p={chunk[3]} content={chunk[4][:60]}")
