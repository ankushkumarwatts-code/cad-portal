from flask import Flask, render_template, request, redirect, url_for, send_from_directory, session
import psycopg2
import datetime
import os

# 🔥 PDF LIBRARIES (UPGRADED)
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet

app = Flask(__name__)
app.secret_key = "secret123"

# =======================
# FOLDERS
# =======================
UPLOAD_FOLDER = 'uploads'
STATIC_FOLDER = 'static'

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(STATIC_FOLDER, exist_ok=True)

# =======================
# DATABASE
# =======================
def get_db():
    conn = psycopg2.connect(os.environ.get("DATABASE_URL"))
    return conn

# =======================
# USERS TABLE
# =======================
def create_users():
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id SERIAL PRIMARY KEY,
        username TEXT,
        password TEXT,
        role TEXT
    )
    """)

    # 🔥 RESET USERS (Deploy safe)
    cursor.execute("DELETE FROM users")

    cursor.execute("INSERT INTO users VALUES (NULL,'admin','1234','admin')")
    cursor.execute("INSERT INTO users VALUES (NULL,'staff','welcome1','staff')")

    conn.commit()
    conn.close()

# =======================
# COMPLAINT TABLE
# =======================
def create_complaints_table():
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS complaints (
        id SERIAL PRIMARY KEY,
        name TEXT,
        phone TEXT,
        issue TEXT,
        description TEXT,
        status TEXT,
        assigned_to TEXT,
        document TEXT,
        received TEXT,
        assigned_time TEXT,
        received_time TEXT,
        deadline TEXT,
        progress INTEGER
    )
    """)

    conn.commit()
    conn.close()

# 🔥 INIT
create_users()
create_complaints_table()

# =======================
# LOGIN (FIXED)
# =======================
@app.route('/', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        u = request.form.get('username')
        p = request.form.get('password')

        conn = get_db()
        cursor = conn.cursor()

       cursor.execute("SELECT role FROM users WHERE username=%s AND password=%s", (u, p))
        user = cursor.fetchone()

        conn.close()

        if user:
            session['user'] = u

            if user['role'] == "admin":
                return redirect(url_for('dashboard'))
            else:
                return redirect(url_for('staff_dashboard'))

        return "Invalid Login ❌"

    return render_template('login.html')

# =======================
# LOGOUT
# =======================
@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

# =======================
# ADD COMPLAINT
# =======================
@app.route('/complaint', methods=['GET', 'POST'])
def complaint():
    if request.method == 'POST':
        name = request.form.get('name')
        phone = request.form.get('phone')
        issue = request.form.get('issue')
        description = request.form.get('description')

        file = request.files.get('document')
        filename = ""

        if file and file.filename:
            filename = file.filename
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))

        conn = get_db()
        cursor = conn.cursor()

        cursor.execute("""
        INSERT INTO complaints 
        (name, phone, issue, description, status, assigned_to, document, received, assigned_time, received_time, deadline, progress)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            name, phone, issue, description,
            "Pending", "Not Assigned", filename,
            "No", "-", "-", "-", 0
        ))

        conn.commit()
        conn.close()

        return "Complaint Submitted Successfully ✅"

    return render_template('complaint.html')

# =======================
# ADMIN DASHBOARD
# =======================
@app.route('/dashboard')
def dashboard():
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM complaints")
    data = cursor.fetchall()

    cursor.execute("SELECT COUNT(*) FROM complaints")
    total = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM complaints WHERE status='Pending'")
    pending = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM complaints WHERE status='In Progress'")
    progress = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM complaints WHERE status='Completed'")
    completed = cursor.fetchone()[0]

    conn.close()

    return render_template('dashboard.html',
                           data=data,
                           total=total,
                           pending=pending,
                           progress=progress,
                           completed=completed)

# =======================
# STAFF PANEL
# =======================
@app.route('/staff')
def staff_dashboard():
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM complaints WHERE assigned_to != 'Not Assigned'")
    data = cursor.fetchall()

    conn.close()

    return render_template('staff_dashboard.html', data=data)

# =======================
# ASSIGN
# =======================
@app.route('/assign/<int:id>', methods=['POST'])
def assign(id):
    staff = request.form.get('staff')
    deadline = request.form.get('deadline')

    assign_time = datetime.datetime.now().strftime("%d-%m-%Y %H:%M:%S")

    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("""
    UPDATE complaints
    SET assigned_to=?, assigned_time=?, deadline=?
    WHERE id=?
    """, (staff, assign_time, deadline, id))

    conn.commit()
    conn.close()

    return redirect(url_for('dashboard'))

# =======================
# RECEIVE
# =======================
@app.route('/receive/<int:id>', methods=['POST'])
def receive(id):
    recv_time = datetime.datetime.now().strftime("%d-%m-%Y %H:%M:%S")

    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("""
    UPDATE complaints
    SET received='Yes', received_time=?
    WHERE id=?
    """, (recv_time, id))

    conn.commit()
    conn.close()

    return redirect(url_for('staff_dashboard'))

# =======================
# STATUS UPDATE
# =======================
@app.route('/status/<int:id>', methods=['POST'])
def update_status(id):
    status = request.form.get('status')

    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("UPDATE complaints SET status=? WHERE id=?", (status, id))

    conn.commit()
    conn.close()

    return redirect(url_for('staff_dashboard'))

# =======================
# PROGRESS UPDATE
# =======================
@app.route('/progress/<int:id>', methods=['POST'])
def update_progress(id):
    new_progress = int(request.form.get('progress'))

    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("SELECT status FROM complaints WHERE id=?", (id,))
    status = cursor.fetchone()[0]

    if status == "Completed":
        conn.close()
        return redirect(url_for('staff_dashboard'))

    if new_progress >= 100:
        cursor.execute("UPDATE complaints SET progress=100, status='Completed' WHERE id=?", (id,))
    else:
        cursor.execute("UPDATE complaints SET progress=? WHERE id=?", (new_progress, id))

    conn.commit()
    conn.close()

    return redirect(url_for('staff_dashboard'))

# =======================
# FILE UPLOAD
# =======================
@app.route('/upload/<int:id>', methods=['POST'])
def upload_file(id):
    file = request.files.get('document')

    if file and file.filename:
        filename = file.filename
        file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))

        conn = get_db()
        cursor = conn.cursor()

        cursor.execute("UPDATE complaints SET document=? WHERE id=?", (filename, id))

        conn.commit()
        conn.close()

    return redirect(url_for('staff_dashboard'))

# =======================
# PERFORMANCE REPORT
# =======================
@app.route('/performance')
def performance():
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM complaints WHERE assigned_to != 'Not Assigned'")
    rows = cursor.fetchall()

    result = {}

    for row in rows:
        staff = row[6]
        status = row[5]

        if staff not in result:
            result[staff] = {"completed": 0, "in_progress": 0, "pending": 0, "score": 0}

        if status == "Completed":
            result[staff]["completed"] += 1
        elif status == "In Progress":
            result[staff]["in_progress"] += 1
        else:
            result[staff]["pending"] += 1

    for staff in result:
        c = result[staff]["completed"]
        p = result[staff]["in_progress"]
        result[staff]["score"] = (c * 10) + (p * 5)

    conn.close()

    return render_template('performance.html', data=result)

# =======================
# PDF REPORT
# =======================
@app.route('/download_report')
def download_report():
    start = request.args.get('start')
    end = request.args.get('end')

    conn = get_db()
    cursor = conn.cursor()

    if start and end:
        cursor.execute("""
        SELECT * FROM complaints
        WHERE substr(assigned_time,7,4)||'-'||substr(assigned_time,4,2)||'-'||substr(assigned_time,1,2)
        BETWEEN ? AND ?
        """, (start, end))
    else:
        cursor.execute("SELECT * FROM complaints")

    rows = cursor.fetchall()
    conn.close()

    file_path = "report.pdf"

    doc = SimpleDocTemplate(file_path, pagesize=letter)
    styles = getSampleStyleSheet()

    elements = []

    logo_path = os.path.join('static', 'logo.png')
    if os.path.exists(logo_path):
        elements.append(Image(logo_path, width=150, height=60))

    elements.append(Spacer(1, 10))
    elements.append(Paragraph("Baba Farid Group of Institutions", styles['Title']))
    elements.append(Paragraph("CAD Complaint & Service Report", styles['Heading2']))
    elements.append(Spacer(1, 10))

    table_data = [["ID", "Name", "Phone", "Issue", "Status", "Assigned To", "Progress"]]

    for r in rows:
        table_data.append([r[0], r[1], r[2], r[3], r[5], r[6], str(r[12]) + "%"])

    table = Table(table_data, repeatRows=1)

    table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.darkblue),
        ('TEXTCOLOR',(0,0),(-1,0),colors.white),
        ('ALIGN',(0,0),(-1,-1),'CENTER'),
        ('GRID',(0,0),(-1,-1),0.5,colors.black),
        ('FONTNAME',(0,0),(-1,0),'Helvetica-Bold'),
    ]))

    elements.append(table)
    doc.build(elements)

    return send_from_directory('.', file_path, as_attachment=True)

# =======================
# FILE VIEW
# =======================
@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

# =======================
# RUN
# =======================
if __name__ == '__main__':
    app.run(debug=True)
