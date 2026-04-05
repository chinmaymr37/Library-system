import sqlite3
import psycopg2
import os

DATABASE_URL = os.environ.get("DATABASE_URL")

def get_connection():
    return psycopg2.connect(DATABASE_URL)

def create_table():
    create_book_table()
    create_member_table()
    create_issue_table() 
    create_user_table()      
    create_copies_table() 

def create_book_table():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS books (
        id SERIAL PRIMARY KEY,
        ISBN TEXT UNIQUE,
        title TEXT NOT NULL,
        author TEXT NOT NULL,
        category TEXT NOT NULL,
        rack TEXT,
        shelf TEXT
    )
    """)

    conn.commit()
    conn.close()

def create_copies_table():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS copies (
        copy_id SERIAL PRIMARY KEY,
        book_id INTEGER NOT NULL,
        barcode TEXT UNIQUE NOT NULL,
        available INTEGER NOT NULL,
        FOREIGN KEY (book_id) REFERENCES books(id)
    )
    """)

    conn.commit()
    conn.close()

def create_member_table():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS members (
        member_id SERIAL PRIMARY KEY,
        name TEXT NOT NULL,
        class INTEGER ,
        section TEXT ,
        roll_number INTEGER NOT NULL UNIQUE
    )
    """)

    conn.commit()
    conn.close()

def create_issue_table():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS issues (
        issue_id SERIAL PRIMARY KEY,
        member_id INTEGER NOT NULL,
        copy_id INTEGER NOT NULL,
        issue_date TEXT NOT NULL,
        due_date TEXT NOT NULL,
        return_date TEXT
    )
    """)

    conn.commit()
    conn.close()

def create_user_table():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        user_id SERIAL PRIMARY KEY,
        member_id INTEGER ,
        username TEXT NOT NULL UNIQUE,
        password TEXT NOT NULL,
        role TEXT NOT NULL,
        last_login TEXT
    )
    """)

    conn.commit()
    conn.close()

def add_book(ISBN, title, author, category, rack, shelf):
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute("SELECT * FROM books WHERE ISBN = %s", (ISBN,))
    existing_book = cursor.fetchone()
    if existing_book:
        conn.close()
        return None, False

    cursor.execute("""
    INSERT INTO books (ISBN, title, author, category, rack, shelf)
    VALUES (%s, %s, %s, %s, %s, %s)
    """, (ISBN, title, author, category, rack, shelf))

    cursor.execute("SELECT id FROM books WHERE ISBN = %s", (ISBN,))
    book_id = cursor.fetchone()[0]

    conn.commit()
    conn.close()
    return book_id , True

def add_copy(book_id, barcode):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
    INSERT INTO copies (book_id, barcode, available)
    VALUES (%s, %s, 1)
    """, (book_id, barcode))

    conn.commit()
    conn.close()

def get_all_books():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
    SELECT 
        books.id,
        books.title,
        books.author,
        books.category,
        COUNT(copies.copy_id) AS total,
        COALESCE(SUM(copies.available), 0) AS available
    FROM books
    LEFT JOIN copies ON books.id = copies.book_id
    GROUP BY books.id
    """)
    books = cursor.fetchall()

    conn.close()
    return books

def delete_book(book_id):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
    SELECT COUNT(*) FROM copies 
    WHERE book_id = %s AND available = 0
    """, (book_id,))
    
    issued_count = cursor.fetchone()[0]

    if issued_count > 0:
        conn.close()
        return False

    cursor.execute("DELETE FROM copies WHERE book_id = %s", (book_id,))
    cursor.execute("DELETE FROM books WHERE id = %s", (book_id,))

    conn.commit()
    conn.close()

    return True

def issue_book(barcode ,member_id , duration):
    conn = get_connection()
    cursor = conn.cursor()
    
    copy = get_copy_by_barcode(barcode)
    member = get_member_by_member_id(member_id)

    if copy is None:
        conn.close()
        return False

    if copy[3] == 0:
        conn.close()
        return False

    if member is None:
        conn.close()
        return False


    from datetime import date, timedelta
                
    issue_date = date.today()
    due_date = issue_date + timedelta(days=duration)

    cursor.execute(
    "INSERT INTO issues (member_id, copy_id, issue_date, due_date ,return_date) VALUES (%s, %s, %s, %s, NULL)",
    (member_id, copy[0], issue_date, due_date)
    )

    cursor.execute(
    "UPDATE copies SET available = 0 WHERE copy_id = %s AND available = 1",
    (copy[0],)
    )

    conn.commit()
    updated = cursor.rowcount
    conn.close()

    return updated > 0

def return_book(barcode):
    conn = get_connection()
    cursor = conn.cursor()

    copy = get_copy_by_barcode(barcode)
    if copy is None:
        conn.close()
        return False, 0
    if copy[3] == 1:
        conn.close()
        return False, 0
    
    copy_id = copy[0]
    from datetime import date
    return_date = date.today()

    cursor.execute(
        "SELECT * FROM issues WHERE copy_id = %s AND return_date IS NULL",
        (copy_id,)
    )
    issue = cursor.fetchone()
    if issue is None:
        conn.close()
        return False, 0
    rate = 10 
    due_date = date.fromisoformat(issue[4])
    days_late = max(0, (return_date - due_date).days)
    fine = days_late * rate

    cursor.execute(
        "UPDATE issues SET return_date = %s WHERE copy_id = %s AND return_date IS NULL",
        (return_date, copy_id)
    )

    updated = cursor.rowcount
    if updated == 0:
        conn.close()
        return False, 0
        
    cursor.execute(
        "UPDATE copies SET available = 1 WHERE copy_id = %s AND available = 0",
        (copy_id,)
    )

    conn.commit()
    conn.close()

    return True, fine

def get_copy_by_barcode(barcode):

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM copies WHERE barcode = %s", (barcode,))
    book = cursor.fetchone()

    conn.close()
    return book

def get_member_by_member_id(member_id):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM members WHERE member_id = %s", (member_id,))
    member = cursor.fetchone()

    conn.close()
    return member
    
def get_overdue_books():

    conn = get_connection()
    cursor = conn.cursor()

    from datetime import date
    today = date.today()

    cursor.execute("""
    SELECT * FROM issues 
    WHERE return_date IS NULL 
    AND due_date::date < %s
    """, (today,))
    overdue= cursor.fetchall()
    result = []
    for row in overdue:
        due_date = date.fromisoformat(row[4])
        days_late = max(0, (today - due_date).days)
        rate = 10
        fine = days_late * rate
        result.append((row[0], row[1], row[2], row[3], row[4], fine))
    conn.close()
    return result

def get_user_by_username(username):

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
    SELECT * FROM users WHERE username = %s
    """, (username,)
    )
    user = cursor.fetchone()
    if user is not None:
        conn.close()
        return user

    conn.close()
    return user

def add_member(name, class_, section, roll_number):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM members WHERE roll_number = %s", (roll_number,))
    existing_member = cursor.fetchone()
    if existing_member:
        conn.close()
        return False

    cursor.execute("""
    INSERT INTO members (name, class, section, roll_number)
    VALUES (%s, %s, %s, %s)
    """, (name, class_, section, roll_number))

    conn.commit()
    conn.close()

    return True

def get_all_members():

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM members")
    rows = cursor.fetchall()

    conn.close()
    return rows

def get_issued_books():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
    SELECT m.name, b.title, c.barcode, i.issue_date, i.due_date, i.return_date
    FROM issues i
    JOIN members m ON i.member_id = m.member_id
    JOIN copies c ON i.copy_id = c.copy_id
    JOIN books b ON c.book_id = b.id
    """)

    rows = cursor.fetchall()

    conn.close()
    return rows

def get_member_issues(member_id):

    conn = get_connection()
    cursor = conn.cursor()

    from datetime import date
    today = date.today()

    cursor.execute("""
    SELECT b.title, i.issue_date, i.due_date, i.return_date 
    FROM issues i
    JOIN copies c ON i.copy_id = c.copy_id
    JOIN books b ON c.book_id = b.id
    WHERE i.member_id = %s
    """, (member_id,))

    rows = cursor.fetchall()
    result = []
    for row in rows:
        due_date = date.fromisoformat(row[2])
        days_late = max(0, (today - due_date).days)
        rate = 10
        fine = days_late * rate
        is_overdue = row[3] is None and today > due_date
        result.append((row[0], row[1], row[2], row[3], fine, is_overdue))

    conn.close()
    return result

def add_user(member_id, username, password, role):

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
    INSERT INTO users (member_id, username, password, role)
    VALUES (%s, %s, %s, %s)
    """, (member_id, username, password, role))

    conn.commit()
    conn.close()

def search_books(input_value):

    conn = get_connection()
    cursor = conn.cursor()

    base_query = """
    SELECT b.id, b.title, b.author, b.category,
           COUNT(c.copy_id) AS total_copies,
           COALESCE(SUM(c.available), 0) AS available_copies
    FROM books b
    LEFT JOIN copies c ON b.id = c.book_id
    """
    cursor.execute("""
    SELECT b.id, b.title, b.author, b.category,
        COUNT(c.copy_id) AS total_copies,
        COALESCE(SUM(c.available), 0) AS available_copies
        FROM copies c
        JOIN books b ON c.book_id = b.id
        WHERE c.barcode = %s
        GROUP BY b.id
        """, (input_value,))

    barcode_result = cursor.fetchall()

    if barcode_result:
        conn.close()
        return barcode_result, True

    if input_value.isdigit():
        query = base_query + " WHERE b.id = %s GROUP BY b.id"
        cursor.execute(query, (input_value,))
    else:
        query = base_query + " WHERE b.title LIKE %s GROUP BY b.id"
        cursor.execute(query, (f"%{input_value}%",))

    results = cursor.fetchall()
    conn.close()
    return results, bool(results)


