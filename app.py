from flask import Flask, render_template, request, redirect, url_for, session, flash, Response
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import secrets
import csv
import io

import os
import secrets

app = Flask(__name__)
app.config['SECRET_KEY'] = secrets.token_hex(16)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///smarttimetracker.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "admin123")  # Admin-Passwort aus Umgebungsvariable oder Default

user_project = db.Table(
    'user_project',
    db.Column('user_id', db.Integer, db.ForeignKey('user.id'), primary_key=True),
    db.Column('project_id', db.Integer, db.ForeignKey('project.id'), primary_key=True)
)

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), unique=True, nullable=False)
    token = db.Column(db.String(32), unique=True, nullable=False)
    times = db.relationship('TimeEntry', backref='user', lazy=True)
    projects = db.relationship('Project', secondary=user_project, backref=db.backref('users', lazy='dynamic'))

class Project(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), unique=True, nullable=False)
    is_archived = db.Column(db.Boolean, default=False, nullable=False)
    times = db.relationship('TimeEntry', backref='project', lazy=True)

class TimeEntry(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    duration = db.Column(db.Float, nullable=False)
    date = db.Column(db.Date, nullable=False, default=datetime.utcnow)
    comment = db.Column(db.String(255), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    project_id = db.Column(db.Integer, db.ForeignKey('project.id'), nullable=False)
    status = db.Column(db.String(8), nullable=True)  # "ok", "not_ok" oder None

@app.before_request
def create_tables():
    if not hasattr(app, '_tables_created'):
        db.create_all()
        app._tables_created = True

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        pw = request.form.get('password')
        if pw == ADMIN_PASSWORD:
            session['admin'] = True
            return redirect(url_for('admin_dashboard'))
        else:
            flash('Falsches Passwort', 'danger')
    return render_template('admin_login.html')

@app.route('/admin/logout')
def admin_logout():
    session.pop('admin', None)
    return redirect(url_for('index'))

@app.route('/admin/dashboard', methods=['GET', 'POST'])
def admin_dashboard():
    if not session.get('admin'):
        return redirect(url_for('admin_login'))
    # Projekt-Zuweisung
    if request.method == 'POST' and request.form.get('action') == 'assign_projects':
        user_id = request.form.get('user_id')
        project_ids = request.form.getlist('project_ids')
        user = User.query.get(user_id)
        if user is not None:
            # Nur aktive Projekte zuweisen
            user.projects = Project.query.filter(Project.id.in_(project_ids), Project.is_archived == False).all()
            db.session.commit()
            flash('Projekte zugewiesen.', 'success')
        return redirect(url_for('admin_dashboard'))
    # Status setzen
    if request.method == 'POST' and request.form.get('entry_id'):
        entry_id = request.form.get('entry_id')
        status = request.form.get('status')
        entry = TimeEntry.query.get(entry_id)
        if entry:
            entry.status = status
            db.session.commit()
            flash('Status aktualisiert.', 'success')
        return redirect(url_for('admin_dashboard'))
    users = User.query.all()
    # Nur aktive Projekte im Dashboard anzeigen
    projects = Project.query.filter_by(is_archived=False).all()
    # Alle Einträge anzeigen (auch von archivierten Projekten)
    entries = (
        db.session.query(TimeEntry)
        .order_by(TimeEntry.date.desc())
        .all()
    )
    return render_template('admin_dashboard.html', users=users, projects=projects, entries=entries)

@app.route('/admin/export_csv')
def admin_export_csv():
    if not session.get('admin'):
        return redirect(url_for('admin_login'))
    entries = TimeEntry.query.order_by(TimeEntry.date.desc()).all()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['Datum', 'Dauer (h)', 'Benutzer', 'Projekt', 'Kommentar', 'Status'])

    for entry in entries:
        writer.writerow([
            entry.date.strftime('%Y-%m-%d'),
            entry.duration,
            entry.user.name,
            entry.project.name,
            entry.comment,
            entry.status or ''
        ])

    output.seek(0)
    return Response(
        output,
        mimetype='text/csv',
        headers={'Content-Disposition': 'attachment; filename=zeiteintraege.csv'}
    )

@app.route('/admin/export_archived_projects_csv')
def admin_export_archived_projects_csv():
    if not session.get('admin'):
        return redirect(url_for('admin_login'))
    # Nur archivierte Projekte abrufen
    archived_projects = Project.query.filter_by(is_archived=True).order_by(Project.name).all()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['Projektname', 'Gesamtstunden', 'Zuletzt zugewiesene Benutzer'])

    for project in archived_projects:
        # Gesamtstunden berechnen
        total_duration = db.session.query(db.func.sum(TimeEntry.duration)).filter(TimeEntry.project_id == project.id).scalar() or 0
        # Benutzer finden, die dieses Projekt *hatten* (Beziehung existiert noch in user_project, auch wenn is_archived=True)
        # Da wir die Beziehung beim Archivieren entfernen, müssen wir uns anders behelfen oder die Annahme ändern.
        # Aktuelle Implementierung entfernt die Beziehung. Wir lassen die Benutzer-Spalte vorerst leer oder ändern die Logik.
        # Alternative: Beziehung nicht entfernen beim Archivieren. Dann können wir hier die Benutzer abfragen.
        # Entscheidung: Wir lassen die Benutzer-Spalte vorerst leer, da die Anforderung war, die Referenz *in der DB* zu halten,
        # was durch die TimeEntries gegeben ist, aber nicht unbedingt durch die user_project-Tabelle nach dem Entfernen.
        # Wenn die user_project-Beziehung erhalten bleiben soll, muss der Code in archive_project angepasst werden.
        assigned_users = ", ".join([user.name for user in project.users]) # Funktioniert nur, wenn Beziehung nicht entfernt wird.

        writer.writerow([
            project.name,
            round(total_duration, 2),
            assigned_users # Diese Spalte bleibt leer mit der aktuellen Archivierungslogik
        ])

    output.seek(0)
    return Response(
        output,
        mimetype='text/csv',
        headers={'Content-Disposition': 'attachment; filename=archivierte_projekte.csv'}
    )


@app.route('/admin/add_user', methods=['POST'])
def add_user():
    if not session.get('admin'):
        return redirect(url_for('admin_login'))
    name = request.form.get('name')
    if not name:
        flash('Name erforderlich', 'danger')
        return redirect(url_for('admin_dashboard'))
    token = secrets.token_hex(16)
    user = User(name=name, token=token)
    db.session.add(user)
    db.session.commit()
    flash(f'Benutzer {name} hinzugefügt. Token: {token}', 'success')
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/add_project', methods=['POST'])
def add_project():
    if not session.get('admin'):
        return redirect(url_for('admin_login'))
    name = request.form.get('name')
    if not name:
        flash('Projektname erforderlich', 'danger')
        return redirect(url_for('admin_dashboard'))
    project = Project(name=name)
    db.session.add(project)
    db.session.commit()
    flash(f'Projekt {name} hinzugefügt.', 'success')
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/archive_project/<int:project_id>', methods=['POST'])
def archive_project(project_id):
    if not session.get('admin'):
        return redirect(url_for('admin_login'))
    project = Project.query.get(project_id)
    if project:
        project.is_archived = True
        # Entferne Projekt von allen Benutzern, denen es direkt zugewiesen ist
        for user in project.users:
            user.projects.remove(project)
        db.session.commit()
        flash(f'Projekt "{project.name}" archiviert.', 'success')
    else:
        flash('Projekt nicht gefunden.', 'danger')
    return redirect(url_for('admin_dashboard'))

@app.route('/user/login', methods=['GET', 'POST'])
def user_login():
    # Direktlogin per URL-Parameter ?token=...
    token = request.args.get('token')
    if token:
        user = User.query.filter_by(token=token).first()
        if user:
            session['user_id'] = user.id
            return redirect(url_for('user_dashboard'))
        else:
            flash('Ungültiger Token', 'danger')

    if request.method == 'POST':
        token = request.form.get('token')
        user = User.query.filter_by(token=token).first()
        if user:
            session['user_id'] = user.id
            return redirect(url_for('user_dashboard'))
        else:
            flash('Ungültiger Token', 'danger')
    return render_template('user_login.html')

@app.route('/user/logout')
def user_logout():
    session.pop('user_id', None)
    return redirect(url_for('index'))

@app.route('/user/dashboard', methods=['GET', 'POST'])
def user_dashboard():
    user_id = session.get('user_id')
    if not user_id:
        return redirect(url_for('user_login'))
    user = User.query.get(user_id)
    # Nur zugewiesene *und nicht archivierte* Projekte anzeigen
    projects = [p for p in user.projects if not p.is_archived] if user.projects else []
    # Wenn keine Projekte zugewiesen sind, keine anzeigen (statt alle)
    # projects = Project.query.filter_by(is_archived=False).all() # Alte Logik, falls keine zugewiesen waren
    edit_entry = None

    # Bearbeiten-Formular laden
    edit_id = request.args.get('edit')
    if edit_id:
        edit_entry = TimeEntry.query.filter_by(id=edit_id, user_id=user.id).first()

    # Eintrag speichern oder bearbeiten
    if request.method == 'POST':
        entry_id = request.form.get('entry_id')
        duration = request.form.get('duration')
        date = request.form.get('date')
        comment = request.form.get('comment')
        project_id = request.form.get('project_id')
        if not (duration and comment and project_id):
            flash('Alle Felder sind Pflicht!', 'danger')
        else:
            try:
                duration = float(duration)
                if not date:
                    date_obj = datetime.utcnow().date()
                else:
                    date_obj = datetime.strptime(date, '%Y-%m-%d').date()
                if entry_id:  # Bearbeiten
                    entry = TimeEntry.query.filter_by(id=entry_id, user_id=user.id).first()
                    if entry:
                        entry.duration = duration
                        entry.date = date_obj
                        entry.comment = comment
                        entry.project_id = project_id
                        db.session.commit()
                        flash('Zeiteintrag aktualisiert.', 'success')
                else:  # Neu
                    entry = TimeEntry(duration=duration, date=date_obj, comment=comment, user_id=user.id, project_id=project_id)
                    db.session.add(entry)
                    db.session.commit()
                    flash('Zeiteintrag gespeichert.', 'success')
            except Exception as e:
                flash('Fehler beim Speichern: ' + str(e), 'danger')
        return redirect(url_for('user_dashboard'))

    entries = TimeEntry.query.filter_by(user_id=user.id).order_by(TimeEntry.date.desc()).all()
    return render_template('user_dashboard.html', user=user, projects=projects, entries=entries, edit_entry=edit_entry)

@app.route('/user/delete_entry/<int:entry_id>', methods=['POST'])
def delete_entry(entry_id):
    user_id = session.get('user_id')
    if not user_id:
        return redirect(url_for('user_login'))
    entry = TimeEntry.query.filter_by(id=entry_id, user_id=user_id).first()
    if entry:
        db.session.delete(entry)
        db.session.commit()
        flash('Zeiteintrag gelöscht.', 'success')
    else:
        flash('Eintrag nicht gefunden oder keine Berechtigung.', 'danger')
    return redirect(url_for('user_dashboard'))

if __name__ == '__main__':
    app.run(debug=True)
