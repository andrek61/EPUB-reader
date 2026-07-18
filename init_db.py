import sqlite3
from werkzeug.security import generate_password_hash
import getpass

# Membuat file database.db baru
connection = sqlite3.connect('database.db')
cursor = connection.cursor()

# 1. Buat Tabel Books (Struktur Sempurna)
cursor.execute('''
CREATE TABLE IF NOT EXISTS books (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT,
    author TEXT,
    file_name TEXT,
    folder_name TEXT UNIQUE,
    opf_path TEXT,
    cover_path TEXT,
    language TEXT DEFAULT 'Unknown',
    last_read DATETIME NULL,
    is_deleted BOOLEAN DEFAULT 0
)
''')

# 2. Buat Tabel Bookmarks
cursor.execute('''
CREATE TABLE IF NOT EXISTS bookmarks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    book_id INTEGER,
    chapter_title TEXT,
    cfi_location TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    is_deleted BOOLEAN DEFAULT 0,
    FOREIGN KEY (book_id) REFERENCES books(id) ON DELETE CASCADE
)
''')

# 3. Buat Tabel Highlights
cursor.execute('''
CREATE TABLE IF NOT EXISTS highlights (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    book_id INTEGER,
    cfi_location TEXT,
    quote_text TEXT,
    note_text TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    is_deleted BOOLEAN DEFAULT 0,
    FOREIGN KEY (book_id) REFERENCES books(id) ON DELETE CASCADE
)
''')

# 4. Buat Tabel Users
cursor.execute('''
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL
)
''')

# 5. Buat Tabel Penghubung untuk Fitur Mengintip
cursor.execute('''
CREATE TABLE IF NOT EXISTS book_peeks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    book_id INTEGER,          
    peek_book_id INTEGER,     
    FOREIGN KEY (book_id) REFERENCES books(id) ON DELETE CASCADE,
    FOREIGN KEY (peek_book_id) REFERENCES books(id) ON DELETE CASCADE,
    UNIQUE(book_id, peek_book_id) 
)
''')

# 6. Suntikkan Akun Master
username = input("Masukkan Username: ")
password = getpass.getpass("Masukkan Password (teks disembunyikan): ")
hash_pw = generate_password_hash(password)

try:
    cursor.execute("INSERT INTO users (username, password_hash) VALUES (?, ?)", (username, hash_pw))
    print("Database SQLite dengan struktur asli berhasil dibuat! Akun master siap digunakan.")
except sqlite3.IntegrityError:
    print("Akun admin sudah ada.")

connection.commit()
connection.close()