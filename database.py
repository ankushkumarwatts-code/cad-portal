import sqlite3

conn = sqlite3.connect('database.db')
cursor = conn.cursor()

cursor.execute('''
CREATE TABLE IF NOT EXISTS complaints (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT,
    issue TEXT,
    description TEXT,
    status TEXT
)
''')

conn.commit()
conn.close()

print("Database Created ✅")