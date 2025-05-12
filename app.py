from flask import Flask, render_template, request, redirect, url_for, session, flash
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import secrets

app = Flask(__name__)
app.config['SECRET_KEY'] = 'supersecretkey'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///smarttimetracker.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

ADMIN_PASSWORD = "admin123"  # Fixes Admin-Passwort

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), unique=True, nullable=False)
    token = db.Column(db.String(32), unique=True, nullable=False)
    times = db.relationship('TimeEntry', backref='user', lazy=True)

class Project(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), unique=True, nullable=False)
    times = db.relationship('TimeEntry', backref='project', lazy=True)

class TimeEntry(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    duration = db.Column(db.Float, nullable=False)
    date = db.Column(db.Date, nullable=False, default=datetime.utcnow)
    comment = db.Column(db.String(255), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    project_id = db.Column(db.Integer, db.ForeignKey('project.id'), nullable=False)

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

@app.route('/admin/dashboard')
def admin_dashboard():
    if not session.get('admin'):
        return redirect(url_for('admin_login'))
    users = User.query.all()
    projects = Project.query.all()
    return render_template('admin_dashboard.html', users=users, projects=projects)

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

@app.route('/user/login', methods=['GET', 'POST'])
def user_login():
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
    projects = Project.query.all()
    if request.method == 'POST':
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
                entry = TimeEntry(duration=duration, date=date_obj, comment=comment, user_id=user.id, project_id=project_id)
                db.session.add(entry)
                db.session.commit()
                flash('Zeiteintrag gespeichert.', 'success')
            except Exception as e:
                flash('Fehler beim Speichern: ' + str(e), 'danger')
    entries = TimeEntry.query.filter_by(user_id=user.id).order_by(TimeEntry.date.desc()).all()
    return render_template('user_dashboard.html', user=user, projects=projects, entries=entries)

if __name__ == '__main__':
    app.run(debug=True)
