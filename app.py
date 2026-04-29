from flask import Flask, render_template, request, redirect, flash , session, url_for
import requests
from models.database import create_table, add_book ,add_copy , get_all_books , delete_book ,issue_book , return_book, get_copy_by_barcode, get_overdue_books, get_user_by_username , add_member , get_all_members, get_issued_books , get_member_issues , add_user , search_books
from functools import wraps
from werkzeug.security import generate_password_hash, check_password_hash

def login_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if "username" not in session:
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return wrapper

create_table()

app = Flask(__name__)
app.secret_key = 'your_secret_key'

@app.route("/")
def home():
    rows = get_all_books()
    total = sum(row[4] for row in rows)
    available = sum(row[5] for row in rows)
    issued = total - available

    return render_template("home.html", total=total, available=available, issued=issued)

@app.route("/add_book", methods=["GET", "POST"])
@login_required
def add_book_route():
    if session.get("role") != "admin":
        flash("Only admin can add books")
        return redirect(url_for("home"))
    action = request.form.get("action")
    if action == "add_book":
        if request.method == "POST":
            ISBN = request.form["ISBN"]
            title = request.form["title"]
            author = request.form["author"]
            category = request.form["category"]
            rack = request.form["rack_number"]
            shelf = request.form["shelf_number"]
            barcode = request.form["barcode"]

            book_id, result = add_book(ISBN, title, author, category, rack, shelf)
            if result:
                add_copy(book_id, barcode)
                flash("Book added successfully")
            else:
                flash("Book with same ISBN already exists")
            
    elif action == "add_copy":
        if request.method == "POST":
            book_id = int(request.form["book_id"])
            barcode = request.form["barcode"]

            add_copy(book_id, barcode)

    return render_template("add_book.html")

@app.route("/add_member", methods=["GET", "POST"])
@login_required
def add_member_route():
    if session.get("role") != "admin":
        flash("Only admin can add members")
        return redirect(url_for("home"))
    if request.method == "POST":
        name = request.form["name"]
        class_ = request.form["class"]
        section = request.form["section"]
        roll_number = int(request.form["roll_number"])

        result = add_member(name, class_, section, roll_number)
        if result:
            flash("Member added successfully")
        else:
            flash("Member with same roll number already exists")

    return render_template("add_member.html")

@app.route("/issue_book", methods=["GET", "POST"])
@login_required
def issue_book_route():
    if session.get("role") != "admin":
        flash("Only admin can issue books")
        return redirect(url_for("home"))
    if request.method == "POST":
        barcode = request.form["barcode"]
        member_id = int(request.form["member_id"])
        duration = int(request.form["duration"])
        result = issue_book(barcode, member_id, duration)

        if result:
            flash("Book issued successfully")
        else:
            flash("Book not available or invalid barcode")

        return redirect("/issue_book")

    return render_template("issue_book.html")

@app.route("/return_book", methods=["GET", "POST"])
@login_required
def return_book_route():
    if session.get("role") != "admin":
        flash("Only admin can return books")
        return redirect(url_for("home"))
    if request.method == "POST":
        barcode = request.form["barcode"]
        result, fine = return_book(barcode)

        if result:
            flash(f"Book returned successfully. Fine: ₹{fine}")
        else:
            flash("Invalid barcode or book already returned")

        return redirect("/return_book")

    return render_template("return_book.html")

@app.route("/view_books")
@login_required
def view_books_route():
    rows = get_all_books()
    filter_type = request.args.get("filter")
    if filter_type == "available":
        rows = [row for row in rows if row[5] >= 1]
    elif filter_type == "issued":
        rows = [row for row in rows if row[5] == 0]
    return render_template("view_books.html", rows=rows)

@app.route("/view_members")
@login_required
def view_members_route():
    rows = get_all_members()
    return render_template("view_members.html", rows=rows)

@app.route("/delete/<int:book_id>")
@login_required
def delete(book_id):
    if session.get("role") != "admin":
        flash("Only admin can delete books")
        return redirect(url_for("home"))
    result = delete_book(book_id)
    if result:
        flash("Book deleted successfully")
    else:
        flash("Book cannot be deleted as it is currently issued")
    return redirect("/view_books")

@app.route("/search", methods=["GET", "POST"])
@login_required
def search():
    copy = None

    if request.method == "POST":
        input_value = request.form["input_value"]
        copy, result = search_books(input_value)
        if not result:
            flash("No book found with the given input")

    return render_template("search.html", copy=copy)

@app.route("/overdue")
@login_required
def overdue():
    rows = get_overdue_books()
    return render_template("overdue.html", rows=rows)

@app.route("/issued_books")
@login_required
def issued_books():
    rows = get_issued_books()
    return render_template("issued_books.html", rows=rows)

@app.route("/member_dashboard")
@login_required
def member_dashboard():
    rows = get_member_issues(session.get("member_id"))
    return render_template("member_dashboard.html", rows=rows)

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]
        user = get_user_by_username(username)
        if user is not None and check_password_hash(user[3], password):
            session["username"] = username
            session["role"] = user[4]
            session["member_id"] = user[1]
            flash("Login successful")
            return redirect(url_for("home"))
        else:
            flash("wrong username OR password")
            flash("Login failed")
            return redirect(url_for("login"))

    return render_template("login.html")

@app.route("/logout")
@login_required
def logout():
    session.pop("username", None)
    session.pop("role", None)
    session.pop("member_id", None)
    flash("Logged out successfully")
    return redirect(url_for("login"))

@app.route("/register", methods=["GET", "POST"])
def register():
    if session.get("role") != "admin":
        flash("Only admin can add users")
        return redirect(url_for("home"))
    if request.method == "POST":
        member_id = request.form.get("member_id")
        member_id = int(member_id) if member_id else None
        username = request.form["username"]
        password = request.form["password"]
        password = generate_password_hash(password)
        role = request.form["role"]
        add_user(member_id, username, password, role)

        flash("User registered successfully")
        return redirect(url_for("register"))
    return render_template("register.html")

@app.route("/open_library")
@login_required
def open_library():
    query = request.args.get("q", "")
    books = []
    trending = []

    if query:
        try:
            response = requests.get(
                f"https://openlibrary.org/search.json?q={query}&limit=12",
                timeout=5
            )
            data = response.json()
            for doc in data.get("docs", []):
                books.append({
                    "title": doc.get("title", "Unknown"),
                    "author": ", ".join(doc.get("author_name", ["Unknown"])),
                    "year": doc.get("first_publish_year", "N/A"),
                    "cover_id": doc.get("cover_i"),
                    "key": doc.get("key", "")
                })
        except Exception:
            flash("Could not connect to Open Library. Please try again.")
    else:
        try:
            response = requests.get(
                "https://openlibrary.org/trending/daily.json?limit=10",
                timeout=5
            )
            data = response.json()
            for doc in data.get("works", []):
                trending.append({
                    "title": doc.get("title", "Unknown"),
                    "author": ", ".join(doc.get("author_name", ["Unknown"])),
                    "year": doc.get("first_publish_year", "N/A"),
                    "cover_id": doc.get("cover_i"),
                    "key": doc.get("key", "")
                })
        except Exception:
            flash("Could not load trending books.")

    return render_template("open_library.html", books=books, trending=trending, query=query)

if __name__ == "__main__":
    app.run()


    