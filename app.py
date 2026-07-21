import os
import zipfile
import xml.etree.ElementTree as ET
from flask import Flask, render_template, request, redirect, url_for, send_from_directory
import pymysql
from werkzeug.utils import secure_filename
import pymysql.cursors
from flask import request, jsonify

from flask import session, redirect, url_for, flash
from werkzeug.security import check_password_hash
from functools import wraps
from datetime import timedelta

import sqlite3

app = Flask(__name__)

# Kunci rahasia untuk mengenkripsi cookie session (bebas tulis apa saja yang panjang)
app.secret_key = "kunci_rahasia_super_kuat_bebas_diisi_apa_saja" 
# Durasi "Remember Me" (misal: 30 hari browser tidak akan minta login lagi)
app.permanent_session_lifetime = timedelta(days=30)

# Folder untuk menyimpan hasil ekstrak buku
EXTRACT_FOLDER = "static/extracted_books"
app.config["EXTRACT_FOLDER"] = EXTRACT_FOLDER
os.makedirs(EXTRACT_FOLDER, exist_ok=True)

DB_HOST = ""
DB_USER = ""
DB_PASSWORD = ""
DB_NAME = ""

# db = pymysql.connect(
#     host="localhost",
#     user="root",
#     password="",
#     database="ebook_db"
# )

def get_db_connection():
    conn = sqlite3.connect('database.db', check_same_thread=False)
    return conn

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Jika tidak ada tanda pengenal 'logged_in' di session, tendang ke login!
        if 'logged_in' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

@app.route('/login', methods=['GET', 'POST'])
def login():
    # Jika sudah login, jangan biarkan masuk ke halaman login lagi
    if 'logged_in' in session:
        return redirect(url_for('index'))

    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        remember = 'remember' in request.form # Mengecek apakah checkbox dicentang

        connection = get_db_connection()
        # HAPUS parameter dictionary=True, biarkan default (Tuple)
        cursor = connection.cursor() 
        cursor.execute("SELECT * FROM users WHERE username = ?", (username,))
        user = cursor.fetchone()
        connection.close()

        # user[0] = id, user[1] = username, user[2] = password_hash
        if user and check_password_hash(user[2], password):
            session['logged_in'] = True
            session['username'] = user[1]
            
            # Jika "Remember Me" dicentang, sesi bertahan 30 hari
            if remember:
                session.permanent = True 
            else:
                session.permanent = False
                
            return redirect(url_for('index'))
        else:
            flash("Username atau Password salah!", "error")

    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear() # Hapus semua ingatan sesi
    return redirect(url_for('login'))


@app.route("/")
@login_required
def index():
    
    connection = get_db_connection()
    cursor = connection.cursor()
    cursor.execute("SELECT * FROM books WHERE is_deleted = 0")
    books = cursor.fetchall()
    connection.close()
    return render_template("index.html", books=books)

# ... (Koneksi Database db = pymysql.connect(...) tetap sama)

@app.route("/upload", methods=["POST"])
@login_required
def upload():
    file = request.files["file"]
    if file:
        filename = secure_filename(file.filename)
        folder_name = filename.rsplit('.', 1)[0]
        extract_path = os.path.join(app.config["EXTRACT_FOLDER"], folder_name)
        
        # 1 & 2. Server Unzip
        with zipfile.ZipFile(file, 'r') as zip_ref:
            zip_ref.extractall(extract_path)

        # 3. Server baca container.xml
        container_xml_path = os.path.join(extract_path, "META-INF", "container.xml")
        tree = ET.parse(container_xml_path)
        root = tree.getroot()
        ns = {'n': 'urn:oasis:names:tc:opendocument:xmlns:container'}
        rootfile = root.find('.//n:rootfile', ns)
        opf_relative_path = rootfile.attrib['full-path'] 

        # ==========================================================
        # 4. EKSTRAK METADATA (TITLE & AUTHOR) DARI FILE .OPF
        # ==========================================================
        opf_absolute_path = os.path.join(extract_path, opf_relative_path)
        opf_tree = ET.parse(opf_absolute_path)
        opf_root = opf_tree.getroot()

        book_title = folder_name.replace("_", " ") 
        book_author = "Unknown Author"
        book_language = "Unknown"
        cover_id = None
        cover_href = None

        # --- TAHAP 1: Cari Judul, Penulis, dan ID Cover Standar ---
        for elem in opf_root.iter():
            tag_name = elem.tag.split('}')[-1] 
            
            if tag_name == 'title' and elem.text:
                book_title = elem.text
            elif tag_name == 'creator' and elem.text:
                book_author = elem.text
            elif tag_name == 'language' and elem.text:
                book_language = elem.text
            elif tag_name == 'meta':
                prop = elem.attrib.get('property')
                if prop == 'dcterms:title' and elem.text:
                    book_title = elem.text
                elif prop == 'dcterms:creator' and elem.text:
                    book_author = elem.text
                elif prop == 'dcterms:language' and elem.text: # Jaga-jaga format EPUB 3
                    book_language = elem.text
                elif elem.attrib.get('name') == 'cover':
                    cover_id = elem.attrib.get('content')

        # --- TAHAP 2: Eksekusi 3 Lapis Pencarian Cover ---
        
        # Lapis 1: Standar EPUB Resmi
        for elem in opf_root.iter():
            tag_name = elem.tag.split('}')[-1]
            if tag_name == 'item':
                if 'cover-image' in elem.attrib.get('properties', ''):
                    cover_href = elem.attrib.get('href')
                    break
                elif cover_id and elem.attrib.get('id') == cover_id:
                    cover_href = elem.attrib.get('href')
                    break
                    
        # Lapis 2: Cari keyword "cover" di ID atau Href (Bagus untuk EPUB Gabungan)
        if not cover_href:
            for elem in opf_root.iter():
                tag_name = elem.tag.split('}')[-1]
                if tag_name == 'item' and 'image' in elem.attrib.get('media-type', ''):
                    # Cek apakah ada kata "cover" di href atau id-nya
                    href_lower = elem.attrib.get('href', '').lower()
                    id_lower = elem.attrib.get('id', '').lower()
                    if 'cover' in href_lower or 'cover' in id_lower:
                        cover_href = elem.attrib.get('href')
                        break

        # Lapis 3: Mode Nekat (Ambil gambar apa saja yang pertama kali muncul)
        if not cover_href:
            for elem in opf_root.iter():
                tag_name = elem.tag.split('}')[-1]
                if tag_name == 'item' and 'image' in elem.attrib.get('media-type', ''):
                    cover_href = elem.attrib.get('href')
                    break # Langsung sikat gambar pertama!

        # --- TAHAP 3: Penggabungan Jalur Path ---
        # Jika benar-benar file EPUB-nya murni teks tanpa gambar 1 pun
        cover_path_final = "default" 
        
        if cover_href:
            opf_dir = os.path.dirname(opf_relative_path)
            # Ini akan menggabungkan path serumit apapun (misal: 1/1/OEBPS/Images/...)
            cover_path_final = os.path.normpath(os.path.join(opf_dir, cover_href)).replace("\\", "/")

        # ==========================================================
        # 5. Simpan ke Database (Perbaikan SQL + Anti Lock)
        # ==========================================================
        connection = get_db_connection()
        connection.row_factory = sqlite3.Row # Agar hasil query bisa dipanggil dengan nama kolom
        cursor = connection.cursor()
        
        try:
            # Cek apakah folder buku sudah pernah ada di database
            cursor.execute("SELECT id, is_deleted FROM books WHERE folder_name = ?", (folder_name,))
            existing_book = cursor.fetchone()

            if existing_book:
                # Jika buku sudah ada di database...
                if existing_book['is_deleted'] == 1:
                    # ...dan statusnya terhapus (1), maka pulihkan jadi 0 dan update metadatanya
                    cursor.execute("""
                        UPDATE books 
                        SET is_deleted = 0, title = ?, author = ?, language = ?, opf_path = ?, cover_path = ?, file_name = ?
                        WHERE id = ?
                    """, (book_title, book_author, book_language, opf_relative_path, cover_path_final, filename, existing_book['id']))
                    connection.commit()
                else:
                    # Jika buku sudah ada dan masih aktif (0), biarkan saja (tidak usah upload ulang)
                    print(f"Buku '{folder_name}' sudah ada dan masih aktif di dashboard.")
            else:
                # Jika buku benar-benar baru, lakukan penyisipan (INSERT) biasa
                cursor.execute(
                    """INSERT INTO books 
                       (title, author, language, file_name, folder_name, opf_path, cover_path) 
                       VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    (book_title, book_author, book_language, filename, folder_name, opf_relative_path, cover_path_final)
                )
                connection.commit()
                
        except Exception as e:
            connection.rollback() # Batalkan transaksi jika terjadi error
            print("Error sistem saat upload:", str(e))
        finally:
            connection.close() # Pastikan database selalu ditutup agar tidak terkunci (locked)

    return redirect(url_for("index"))

# Rute khusus agar Flask bisa menyajikan file-file buku yang sudah diekstrak
@app.route('/buku_ekstrak/<folder_name>/<path:filename>')
@login_required
def serve_extracted_book(folder_name, filename):
    book_dir = os.path.join(app.config['EXTRACT_FOLDER'], folder_name)
    return send_from_directory(book_dir, filename)

@app.route("/detail/<folder_name>")
@login_required
def detail(folder_name):
    connection = get_db_connection()
    # Gunakan DictCursor agar data mudah dibaca di HTML
    connection.row_factory = sqlite3.Row
    cursor = connection.cursor() 
    
    # 1. Ambil data utama buku
    cursor.execute("SELECT * FROM books WHERE folder_name = ? AND is_deleted = 0", (folder_name,))
    book = cursor.fetchone()
    
    if not book:
        return "Buku tidak ditemukan", 404
        
    book_id = book['id']
    
    # 2. Ambil semua Bookmark untuk buku ini
    cursor.execute("SELECT * FROM bookmarks WHERE book_id = ? AND is_deleted = 0 ORDER BY created_at DESC", (book_id,))
    bookmarks = cursor.fetchall()
    
    # 3. Ambil semua Kutipan & Catatan
    cursor.execute("SELECT * FROM highlights WHERE book_id = ? AND is_deleted = 0 ORDER BY created_at DESC", (book_id,))
    highlights = cursor.fetchall()
    
    connection.close()
    
    # Kirim SEMUA data ke halaman detail.html
    return render_template("detail.html", 
                           book=book, 
                           bookmarks=bookmarks, 
                           highlights=highlights)

@app.route("/read/<folder_name>")
@login_required
def read(folder_name):
    # Ambil opf_path dari database berdasarkan folder_name
    connection = get_db_connection()
    cursor = connection.cursor()
    cursor.execute("SELECT opf_path, title FROM books WHERE folder_name = ? AND is_deleted = 0", (folder_name,))
    result = cursor.fetchone()
    
    opf_path = result[0]
    title_name = result[1]
    connection.close()
    return render_template("reader.html", folder_name=folder_name, opf_path=opf_path, title_name=title_name)

@app.route("/add_bookmark", methods=["POST"])
@login_required
def add_bookmark():
    # Terima data JSON dari JavaScript
    data = request.get_json()
    folder_name = data.get('folder_name')
    chapter_title = data.get('chapter_title')
    cfi_location = data.get('cfi_location')

    if not all([folder_name, chapter_title, cfi_location]):
        return jsonify({"success": False, "message": "Data tidak lengkap"}), 400

    connection = get_db_connection()
    cursor = connection.cursor()

    try:
        # 1. Cari ID buku berdasarkan folder_name
        cursor.execute("SELECT id FROM books WHERE folder_name = ? AND is_deleted = 0", (folder_name,))
        book = cursor.fetchone()

        if not book:
            return jsonify({"success": False, "message": "Buku tidak ditemukan"}), 404

        # Menyesuaikan jika pakai DictCursor atau Cursor biasa
        book_id = book['id'] if isinstance(book, dict) else book[0]

        # 2. Simpan bookmark ke database
        cursor.execute(
            "INSERT INTO bookmarks (book_id, chapter_title, cfi_location) VALUES (?, ?, ?)",
            (book_id, chapter_title, cfi_location)
        )
        connection.commit()
        return jsonify({"success": True, "message": "Bookmark berhasil disimpan!"})
        
    except Exception as e:
        connection.rollback()
        return jsonify({"success": False, "message": str(e)}), 500
    finally:
        connection.close()

# --- API UNTUK MENYIMPAN HIGHLIGHT & CATATAN ---
@app.route("/add_highlight", methods=["POST"])
@login_required
def add_highlight():
    data = request.get_json()
    highlight_id = data.get('highlight_id') # Tangkap ID dari JS (Bisa None)
    folder_name = data.get('folder_name')
    highlight_text = data.get('highlight_text')
    note_text = data.get('note_text')
    cfi_location = data.get('cfi_location')

    if not all([folder_name, highlight_text, cfi_location]):
        return jsonify({"success": False, "message": "Data tidak lengkap"}), 400

    connection = get_db_connection()
    cursor = connection.cursor()

    try:
        # LOGIKA 1: JIKA INI ADALAH PROSES EDIT (Berdasarkan ID Asli)
        # Sistem tidak peduli buku apa yang sedang dibaca, langsung ubah catatan aslinya!
        if highlight_id:
            cursor.execute(
                "UPDATE highlights SET note_text = ? WHERE id = ?",
                (note_text, highlight_id)
            )
            message = "Catatan berhasil diperbarui!"
        
        # LOGIKA 2: JIKA INI ADALAH CATATAN BARU (Highlight ID kosong)
        else:
            # 1. Cari ID buku saat ini
            cursor.execute("SELECT id FROM books WHERE folder_name = ?", (folder_name,))
            book = cursor.fetchone()
            if not book:
                return jsonify({"success": False, "message": "Buku tidak ditemukan"}), 404
            
            book_id = book['id'] if isinstance(book, dict) else book[0]

            # 2. Jaga-jaga: Cek apakah user tak sengaja membuat catatan dobel di lokasi yang sama
            cursor.execute(
                "SELECT id FROM highlights WHERE book_id = ? AND cfi_location = ? AND is_deleted = 0",
                (book_id, cfi_location)
            )
            existing_hl = cursor.fetchone()

            if existing_hl:
                hl_id = existing_hl['id'] if isinstance(existing_hl, dict) else existing_hl[0]
                cursor.execute(
                    "UPDATE highlights SET note_text = ? WHERE id = ?",
                    (note_text, hl_id)
                )
                message = "Catatan berhasil diperbarui!"
            else:
                # 3. Murni Catatan Baru
                cursor.execute(
                    "INSERT INTO highlights (book_id, quote_text, note_text, cfi_location) VALUES (?, ?, ?, ?)",
                    (book_id, highlight_text, note_text, cfi_location)
                )
                message = "Catatan baru berhasil disimpan!"
                
        connection.commit()
        return jsonify({"success": True, "message": message})
        
    except Exception as e:
        connection.rollback()
        return jsonify({"success": False, "message": str(e)}), 500
    finally:
        connection.close()
        
@app.route("/api/books_for_relation/<int:book_id>", methods=["GET"])
@login_required
def books_for_relation(book_id):
    connection = get_db_connection()
    connection.row_factory = sqlite3.Row
    cursor = connection.cursor()
    
    # Ambil semua buku selain dirinya sendiri yang tidak di-soft-delete
    cursor.execute("SELECT id, title FROM books WHERE id != ? AND is_deleted = 0", (book_id,))
    books = cursor.fetchall()
    
    # Ambil daftar ID buku yang saat ini sedang diintip
    cursor.execute("SELECT peek_book_id FROM book_peeks WHERE book_id = ?", (book_id,))
    existing_relations = [row['peek_book_id'] for row in cursor.fetchall()]
    connection.close()
    
    result = [{"id": b['id'], "title": b['title'], "is_checked": b['id'] in existing_relations} for b in books]
    return jsonify({"success": True, "books": result})

@app.route("/api/save_relations/<int:book_id>", methods=["POST"])
@login_required
def save_relations(book_id):
    selected_ids = request.get_json().get('related_ids', [])
    connection = get_db_connection()
    cursor = connection.cursor()
    try:
        # Hapus semua relasi lama untuk buku ini
        cursor.execute("DELETE FROM book_peeks WHERE book_id = ?", (book_id,))
        # Masukkan relasi baru (jika ada yang dicentang)
        for p_id in selected_ids:
            cursor.execute("INSERT INTO book_peeks (book_id, peek_book_id) VALUES (?, ?)", (book_id, p_id))
        connection.commit()
        return jsonify({"success": True, "message": "Radar lintas volume berhasil diperbarui!"})
    except Exception as e:
        connection.rollback()
        return jsonify({"success": False, "message": str(e)}), 500
    finally:
        connection.close()

@app.route("/get_highlights/<folder_name>", methods=["GET"])
@login_required
def get_highlights(folder_name):
    connection = get_db_connection()
    connection.row_factory = sqlite3.Row
    cursor = connection.cursor()
    
    try:
        # 1. Cari ID buku saat ini
        cursor.execute("SELECT id FROM books WHERE folder_name = ? AND is_deleted = 0", (folder_name,))
        current_book = cursor.fetchone()
        if not current_book:
            return jsonify({"success": False, "message": "Buku tidak ditemukan"}), 404
            
        current_book_id = current_book['id']
        
        # 2. Cari target ID (dirinya sendiri + buku yang diintip)
        cursor.execute("SELECT peek_book_id FROM book_peeks WHERE book_id = ?", (current_book_id,))
        target_ids = [current_book_id] + [row['peek_book_id'] for row in cursor.fetchall()]

        # 3. Tarik highlight beserta ID highlight dan Judul Buku
        placeholders = ",".join(["?"] * len(target_ids))
        query = f"""
            SELECT h.id, h.cfi_location, h.note_text, h.quote_text, h.book_id, b.title as book_title
            FROM highlights h
            JOIN books b ON h.book_id = b.id
            WHERE h.book_id IN ({placeholders}) AND h.is_deleted = 0 AND b.is_deleted = 0
        """
        
        cursor.execute(query, tuple(target_ids))
        highlights = cursor.fetchall()
        
        result = []
        for hl in highlights:
            result.append({
                "id": hl['id'],
                "book_title": hl['book_title'],
                "cfi_location": hl['cfi_location'],
                "note": hl['note_text'] if hl['note_text'] else "",
                "highlight_text": hl['quote_text'],
                "is_external": hl['book_id'] != current_book_id
            })
            
        return jsonify({"success": True, "highlights": result})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500
    finally:
        connection.close()

# --- API UNTUK MENGEDIT CATATAN (HIGHLIGHT) ---
@app.route("/edit_highlight/<int:hl_id>", methods=["POST"])
@login_required
def edit_highlight(hl_id):
    data = request.get_json()
    new_note = data.get('new_note', '')

    connection = get_db_connection()
    cursor = connection.cursor()

    try:
        # Update kolom note_text berdasarkan ID highlight
        cursor.execute(
            "UPDATE highlights SET note_text = ? WHERE id = ?", 
            (new_note, hl_id)
        )
        connection.commit()
        return jsonify({"success": True, "message": "Catatan berhasil diperbarui!"})
        
    except Exception as e:
        connection.rollback()
        print("ERROR EDIT HIGHLIGHT:", str(e))
        return jsonify({"success": False, "message": str(e)}), 500
    finally:
        connection.close()

# --- API UNTUK SOFT DELETE ---

@app.route("/delete_book/<int:book_id>", methods=["POST"])
@login_required
def delete_book(book_id):
    connection = get_db_connection()
    cursor = connection.cursor()
    # Soft delete buku
    cursor.execute("UPDATE books SET is_deleted = TRUE WHERE id = ?", (book_id,))
    connection.commit()
    connection.close()
    return jsonify({"success": True, "message": "Buku dipindahkan ke tempat sampah."})

@app.route("/delete_bookmark/<int:bm_id>", methods=["POST"])
@login_required
def delete_bookmark(bm_id):
    connection = get_db_connection()
    cursor = connection.cursor()
    cursor.execute("UPDATE bookmarks SET is_deleted = TRUE WHERE id = ?", (bm_id,))
    connection.commit()
    connection.close()
    return jsonify({"success": True})

@app.route("/delete_highlight/<int:hl_id>", methods=["POST"])
@login_required
def delete_highlight(hl_id):
    connection = get_db_connection()
    cursor = connection.cursor()
    cursor.execute("UPDATE highlights SET is_deleted = TRUE WHERE id = ?", (hl_id,))
    connection.commit()
    connection.close()
    return jsonify({"success": True})

if __name__ == "__main__":
    app.run(debug=True)