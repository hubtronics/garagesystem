from flask import Flask, render_template, redirect, url_for, request, session, flash
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
import os
from flask import send_file
import io
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your_secret_key_here'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///garage.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# VehicleHistory model
class VehicleHistory(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    vehicle_id = db.Column(db.Integer, db.ForeignKey('vehicle.id'), nullable=False)
    date = db.Column(db.String(20), nullable=False)
    timestamp = db.Column(db.DateTime, nullable=False, default=db.func.current_timestamp())
    description = db.Column(db.Text, nullable=False)
    technician = db.Column(db.String(100), nullable=True)
    vehicle = db.relationship('Vehicle', backref='history_entries')

# User model

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

# Vehicle model
class Vehicle(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)  # Vehicle name
    model = db.Column(db.String(100), nullable=False)
    plate = db.Column(db.String(20), unique=True, nullable=False)
    vin_number = db.Column(db.String(100), nullable=True)
    type = db.Column(db.String(50), nullable=True)  # electrical, mechanical, or service
    status = db.Column(db.String(50), nullable=False)
    date_booked = db.Column(db.String(20), nullable=True)
    technician = db.Column(db.String(100), nullable=True)  # Technician working on vehicle
    history = db.Column(db.Text, nullable=True)  # Track work done
    customer_id = db.Column(db.Integer, db.ForeignKey('customer.id'), nullable=True)
    customer = db.relationship('Customer', backref='vehicles')

# Customer model
class Customer(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    phone = db.Column(db.String(20), nullable=False)
    email = db.Column(db.String(100), nullable=False)


# Create default admin and initialize DB at startup
def create_admin():
    with app.app_context():
        db.create_all()
        if not User.query.filter_by(username='admin').first():
            admin = User(username='admin')
            admin.set_password('admin')
            db.session.add(admin)
            db.session.commit()

def login_required(f):
    from functools import wraps
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please log in to access this page.', 'warning')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

@app.route('/')
def index():
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = User.query.filter_by(username=username).first()
        if user and user.check_password(password):
            session['user_id'] = user.id
            session['username'] = user.username
            flash('Login successful!', 'success')
            return redirect(url_for('dashboard'))
        else:
            flash('Invalid username or password.', 'danger')
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    flash('Logged out successfully.', 'info')
    return redirect(url_for('login'))


# Dashboard
        # VehicleHistory model
@app.route('/dashboard')
@login_required
def dashboard():
    return render_template('dashboard.html')

# VEHICLE CRUD

@app.route('/vehicles')
@login_required
def vehicles():
    q = request.args.get('q', '').strip()
    if q:
        vehicles = Vehicle.query.filter(
            (Vehicle.plate.ilike(f'%{q}%')) |
            (Vehicle.model.ilike(f'%{q}%')) |
            (Vehicle.name.ilike(f'%{q}%'))
        ).all()
    else:
        vehicles = Vehicle.query.all()
    return render_template('vehicles.html', vehicles=vehicles)


# Vehicle detail and add history record
@app.route('/vehicles/<int:vehicle_id>', methods=['GET', 'POST'])
@login_required
def vehicle_detail(vehicle_id):
    v = Vehicle.query.get_or_404(vehicle_id)
    if request.method == 'POST':
        from datetime import datetime
        date = request.form['date']
        description = request.form['description']
        technician = request.form['technician']
        new_record = VehicleHistory(vehicle_id=vehicle_id, date=date, description=description, technician=technician, timestamp=datetime.now())
        db.session.add(new_record)
        db.session.commit()
        flash('New record added to vehicle history!', 'success')
        return redirect(url_for('vehicle_detail', vehicle_id=vehicle_id))
    # Get all history entries for this vehicle, ordered by date descending
    history_entries = VehicleHistory.query.filter_by(vehicle_id=vehicle_id).order_by(VehicleHistory.date.desc()).all()
    quotes = []  # Placeholder for quotes, to be implemented
    return render_template('vehicle_detail.html', vehicle=v, quotes=quotes, history_entries=history_entries)

@app.route('/vehicles/add', methods=['GET', 'POST'])
@login_required
def add_vehicle():
    customers = Customer.query.all()
    if not customers:
        flash('Please add a customer first before adding a vehicle.', 'warning')
        return redirect(url_for('add_customer'))
    if request.method == 'POST':
        customer_id = request.form['customer_id']
        name = request.form['name']
        plate = request.form['plate']
        model = request.form['model']
        vin_number = request.form['vin_number']
        type_ = request.form['type']
        # status field removed from form, set a default value
        status = 'Active'  # or any default you prefer
        date_booked = request.form['date_booked']
        technician = request.form['technician']
        history = request.form.get('history', '')
        # Check for duplicate plate
        if Vehicle.query.filter_by(plate=plate).first():
            flash('A vehicle with this plate number already exists.', 'danger')
            return render_template('add_vehicle.html', customers=customers)
        v = Vehicle(
            customer_id=customer_id,
            name=name,
            plate=plate,
            model=model,
            vin_number=vin_number,
            type=type_,
            status=status,
            date_booked=date_booked,
            technician=technician,
            history=history
        )
        db.session.add(v)
        db.session.commit()
        flash('Vehicle added successfully!', 'success')
        return redirect(url_for('vehicles'))
    return render_template('add_vehicle.html', customers=customers)

@app.route('/vehicles/edit/<int:vehicle_id>', methods=['GET', 'POST'])
@login_required
def edit_vehicle(vehicle_id):
    v = Vehicle.query.get_or_404(vehicle_id)
    customers = Customer.query.all()
    if not customers:
        flash('Please add a customer first before editing a vehicle.', 'warning')
        return redirect(url_for('add_customer'))
    if request.method == 'POST':
        v.customer_id = request.form['customer_id']
        v.name = request.form['name']
        v.plate = request.form['plate']
        v.model = request.form['model']
        v.vin_number = request.form['vin_number']
        v.type = request.form['type']
        v.status = request.form['status']
        v.date_booked = request.form['date_booked']
        v.technician = request.form['technician']
        v.history = request.form.get('history', '')
        db.session.commit()
        flash('Vehicle updated!', 'success')
        return redirect(url_for('vehicles'))
    return render_template('edit_vehicle.html', vehicle=v, customers=customers)

@app.route('/vehicles/delete/<int:vehicle_id>', methods=['POST'])
@login_required
def delete_vehicle(vehicle_id):
    v = Vehicle.query.get_or_404(vehicle_id)
    db.session.delete(v)
    db.session.commit()
    flash('Vehicle deleted!', 'info')
    return redirect(url_for('vehicles'))

# CUSTOMER CRUD
@app.route('/customers')
@login_required
def customers():
    q = request.args.get('q', '').strip()
    if q:
        customers = Customer.query.filter(
            (Customer.name.ilike(f'%{q}%')) |
            (Customer.phone.ilike(f'%{q}%')) |
            (Customer.email.ilike(f'%{q}%'))
        ).all()
    else:
        customers = Customer.query.all()
    return render_template('customers.html', customers=customers)

@app.route('/customers/add', methods=['GET', 'POST'])
@login_required
def add_customer():
    if request.method == 'POST':
        name = request.form['name']
        phone = request.form['phone']
        email = request.form['email']
        c = Customer(name=name, phone=phone, email=email)
        db.session.add(c)
        db.session.commit()
        flash('Customer added!', 'success')
        return redirect(url_for('customers'))
    return render_template('add_customer.html')

@app.route('/customers/edit/<int:customer_id>', methods=['GET', 'POST'])
@login_required
def edit_customer(customer_id):
    c = Customer.query.get_or_404(customer_id)
    if request.method == 'POST':
        c.name = request.form['name']
        c.phone = request.form['phone']
        c.email = request.form['email']
        db.session.commit()
        flash('Customer updated!', 'success')
        return redirect(url_for('customers'))
    return render_template('edit_customer.html', customer=c)

@app.route('/customers/delete/<int:customer_id>', methods=['POST'])
@login_required
def delete_customer(customer_id):
    c = Customer.query.get_or_404(customer_id)
    db.session.delete(c)
    db.session.commit()
    flash('Customer deleted!', 'info')
    return redirect(url_for('customers'))

@app.route('/vehicles/<int:vehicle_id>/report')
@login_required
def vehicle_report(vehicle_id):
    from flask import send_file, current_app
    import io
    from reportlab.lib.pagesizes import letter
    from reportlab.pdfgen import canvas
    from reportlab.lib.utils import ImageReader
    import os
    v = Vehicle.query.get_or_404(vehicle_id)
    history_entries = VehicleHistory.query.filter_by(vehicle_id=vehicle_id).order_by(VehicleHistory.date.desc()).all()
    buffer = io.BytesIO()
    p = canvas.Canvas(buffer, pagesize=letter)
    width, height = letter
    y = height - 40
    # Company logo and details
    logo_path = os.path.join(current_app.root_path, 'static', 'powertune.jpg')
    logo_height = 50
    logo_width = 100
    logo_y = y - logo_height + 10
    if os.path.exists(logo_path):
        p.drawImage(ImageReader(logo_path), 40, logo_y, width=logo_width, height=logo_height, mask='auto')
    p.setFont('Helvetica-Bold', 18)
    p.drawString(160, y-20, "POWERTUNE AUTO GARAGE")
    p.setFont('Helvetica', 10)
    p.drawString(160, y-38, "Nairobi, Kenya | Tel: 0712 345678 | Email: info@powertune.co.ke")
    y -= 70
    p.setFont('Helvetica-Bold', 15)
    p.drawString(40, y, f"Vehicle Service Report")
    y -= 20
    p.setFont('Helvetica', 12)
    p.drawString(40, y, f"Vehicle: {v.name} ({v.plate})")
    y -= 16
    p.drawString(40, y, f"Model: {v.model}")
    y -= 16
    p.drawString(40, y, f"VIN: {v.vin_number or '-'}")
    y -= 28  # Add extra space before customer details

    if v.customer:
        p.drawString(40, y, "Customer Details:")
        y -= 14
        p.setFont('Helvetica', 11)
        p.drawString(60, y, f"Name: {v.customer.name}")
        y -= 14
        p.drawString(60, y, f"Phone: {v.customer.phone}")
        y -= 14
        p.drawString(60, y, f"Email: {v.customer.email}")
        y -= 16
        p.setFont('Helvetica', 12)
    y -= 10
    p.setFont('Helvetica-Bold', 13)
    p.drawString(40, y, "Visit & Service History:")
    y -= 18
    p.setFont('Helvetica', 11)
    if not history_entries:
        p.drawString(40, y, "No history records found.")
    else:
        for idx, h in enumerate(history_entries, 1):
            if y < 60:
                p.showPage()
                y = height - 40
            p.setFont('Helvetica-Bold', 11)
            ts = h.timestamp.strftime('%Y-%m-%d %H:%M') if hasattr(h, 'timestamp') and h.timestamp else '-'
            p.drawString(50, y, f"{idx}. Date: {h.date} | Time: {ts} | Technician: {h.technician or '-'}")
            y -= 14
            p.setFont('Helvetica', 11)
            p.drawString(70, y, f"Description: {h.description}")
            y -= 22
    p.setFont('Helvetica-Oblique', 9)
    p.drawString(40, 30, "Generated by Powertune Garage System - {date}".format(date=''))
    p.save()
    buffer.seek(0)
    return send_file(buffer, as_attachment=True, download_name=f'vehicle_{v.plate}_report.pdf', mimetype='application/pdf')

if __name__ == '__main__':
    create_admin()
    # Set debug=False for production. Set to True only for local testing.
    app.run(debug=False, port=5001)
