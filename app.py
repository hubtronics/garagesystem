from flask import Flask, render_template, redirect, url_for, request, session, flash
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
import os
from flask import send_file
import io
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from datetime import datetime
from flask_migrate import Migrate

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your_secret_key_here'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///garage.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)
migrate = Migrate(app, db)

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
    role = db.Column(db.String(20), default='user')  # 'admin' or 'user'

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

class ServiceVisit(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    vehicle_id = db.Column(db.Integer, db.ForeignKey('vehicle.id'), nullable=False)
    date = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    notes = db.Column(db.String(255))
    visit_category = db.Column(db.String(100))  # instead of visit_type
    labour = db.Column(db.Float, default=0.0)
    items = db.relationship('ServiceItem', backref='visit', lazy=True)

class ServiceItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    visit_id = db.Column(db.Integer, db.ForeignKey('service_visit.id'), nullable=False)
    item_name = db.Column(db.String(100), nullable=False)
    part_number = db.Column(db.String(100), nullable=True)  # <-- Add this line
    quantity = db.Column(db.Integer, nullable=False, default=1)
    price = db.Column(db.Float, nullable=False, default=0.0)
    labour = db.Column(db.Float, nullable=False, default=0.0)

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
    vehicle_count = Vehicle.query.count()
    customer_count = Customer.query.count()
    return render_template('dashboard.html', vehicle_count=vehicle_count, customer_count=customer_count)

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
    visits = ServiceVisit.query.filter_by(vehicle_id=vehicle_id).order_by(ServiceVisit.date.desc()).all()
    return render_template('vehicle_detail.html', vehicle=v, visits=visits)

@app.route('/vehicles/add', methods=['GET', 'POST'])
@login_required
def add_vehicle():
    customers = Customer.query.all()
    if not customers:
        flash('Please add a customer first before adding a vehicle.', 'warning')
        return redirect(url_for('add_customer'))
    if request.method == 'POST':
        customer_id = request.form['customer_id']
        make = request.form['name']
        custom_make = request.form.get('custom_make', '').strip()
        name = custom_make if make == 'custom' and custom_make else make
        plate = request.form['plate']
        model = request.form['model']
        vin_number = request.form['vin_number']
        type_ = request.form['type']
        status = 'Active'
        date_booked = request.form['date_booked']
        technician = request.form['technician']
        history = request.form.get('history', '')
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
    user = User.query.get(session['user_id'])
    if user.role != 'admin':
        flash('Only admin can edit vehicles.', 'danger')
        return redirect(url_for('vehicles'))
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
    user = User.query.get(session['user_id'])
    if user.role != 'admin':
        flash('Only admin can delete vehicles.', 'danger')
        return redirect(url_for('vehicles'))
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
    user = User.query.get(session['user_id'])
    if user.role != 'admin':
        flash('Only admin can delete customers.', 'danger')
        return redirect(url_for('customers'))
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
    visits = ServiceVisit.query.filter_by(vehicle_id=vehicle_id).order_by(ServiceVisit.date.desc()).all()
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
    p.drawString(160, y-38, "Nairobi, Kenya | Tel: 0748 638225 | Email: info@powertune.co.ke")
    y -= 70

    # Vehicle and customer details
    p.setFont('Helvetica-Bold', 15)
    p.drawString(40, y, f"Vehicle Comprehensive Report")
    y -= 20
    p.setFont('Helvetica', 12)
    p.drawString(40, y, f"Vehicle: {v.name} ({v.plate})")
    y -= 16
    p.drawString(40, y, f"Model: {v.model}")
    y -= 16
    p.drawString(40, y, f"VIN: {v.vin_number or '-'}")
    y -= 16
    p.drawString(40, y, f"Visit Category: {v.type or '-'}")
    y -= 16
    p.drawString(40, y, f"Status: {v.status}")
    y -= 16
    p.drawString(40, y, f"Date Booked: {v.date_booked or '-'}")
    y -= 16
    p.drawString(40, y, f"Technician: {v.technician or '-'}")
    y -= 28

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

    # Service Visits
    p.setFont('Helvetica-Bold', 13)
    p.drawString(40, y, "Visit & Service History:")
    y -= 18
    p.setFont('Helvetica', 11)
    if not visits:
        p.drawString(40, y, "No service visits found.")
    else:
        for idx, visit in enumerate(visits, 1):
            if y < 100:
                p.showPage()
                y = height - 40
            p.setFont('Helvetica-Bold', 11)
            p.drawString(50, y, f"{idx}. Date: {visit.date.strftime('%Y-%m-%d %H:%M')} | Category: {visit.visit_category or '-'} | Notes: {visit.notes or '-'}")
            y -= 14
            p.setFont('Helvetica', 11)
            items = visit.items
            parts_total = sum(item.quantity * item.price for item in items)
            items_labour_total = sum(item.labour or 0 for item in items)
            visit_labour = visit.labour or 0
            grand_total = parts_total + items_labour_total + visit_labour
            if items:
                p.drawString(70, y, "Items:")
                y -= 14
                for item in items:
                    p.drawString(80, y, f"- {item.item_name} | Part#: {item.part_number or '-'} | Qty: {item.quantity} | Price: {item.price} | Labour: {item.labour or 0}")
                    y -= 12
            p.drawString(80, y, f"Parts Total: {parts_total} | Labour (Items): {items_labour_total} | Labour (Visit): {visit_labour} | Grand Total: {grand_total}")
            y -= 18

    p.setFont('Helvetica-Oblique', 9)
    p.drawString(40, 30, "Generated by Powertune Garage System - {date}".format(date=datetime.now().strftime('%Y-%m-%d %H:%M')))
    p.save()
    buffer.seek(0)
    return send_file(buffer, as_attachment=True, download_name=f'vehicle_{v.plate}_report.pdf', mimetype='application/pdf')

@app.route('/vehicles/<int:vehicle_id>/add_visit', methods=['GET', 'POST'])
@login_required
def add_visit(vehicle_id):
    v = Vehicle.query.get_or_404(vehicle_id)
    if request.method == 'POST':
        notes = request.form['notes']
        visit_category = request.form['visit_category']
        item_names = request.form.getlist('item_name')
        part_numbers = request.form.getlist('part_number')
        quantities = request.form.getlist('quantity')
        prices = request.form.getlist('price')
        labours = request.form.getlist('labour')
        visit_labour = float(request.form.get('visit_labour', 0))
        visit = ServiceVisit(vehicle_id=vehicle_id, notes=notes, visit_category=visit_category, labour=visit_labour)
        db.session.add(visit)
        db.session.flush()
        for name, part_no, qty, price, labour in zip(item_names, part_numbers, quantities, prices, labours):
            if name.strip():
                item = ServiceItem(
                    visit_id=visit.id,
                    item_name=name.strip(),
                    part_number=part_no.strip() if part_no else None,
                    quantity=int(qty) if qty else 1,
                    price=float(price) if price else 0.0,
                    labour=float(labour) if labour else 0.0
                )
                db.session.add(item)
        db.session.commit()
        flash('Service visit added!', 'success')
        return redirect(url_for('vehicle_detail', vehicle_id=vehicle_id))
    return render_template('add_visit.html', vehicle=v)

@app.route('/visit/<int:visit_id>/print')
@login_required
def print_visit(visit_id):
    visit = ServiceVisit.query.get_or_404(visit_id)
    vehicle = Vehicle.query.get_or_404(visit.vehicle_id)
    customer = vehicle.customer
    items = visit.items

    # Calculate totals
    parts_total = sum(item.quantity * item.price for item in items)
    items_labour_total = sum(item.labour or 0 for item in items)
    visit_labour = visit.labour or 0
    grand_total = parts_total + items_labour_total + visit_labour

    return render_template(
        'print_visit.html',
        visit=visit,
        vehicle=vehicle,
        customer=customer,
        items=items,
        parts_total=parts_total,
        items_labour_total=items_labour_total,
        visit_labour=visit_labour,
        grand_total=grand_total
    )

@app.route('/change_password', methods=['GET', 'POST'])
@login_required
def change_password():
    if request.method == 'POST':
        current_password = request.form['current_password']
        new_password = request.form['new_password']
        confirm_password = request.form['confirm_password']
        user = User.query.filter_by(username=session.get('username')).first()
        if not user or not check_password_hash(user.password_hash, current_password):
            flash('Current password is incorrect.', 'danger')
        elif new_password != confirm_password:
            flash('New passwords do not match.', 'danger')
        else:
            user.password_hash = generate_password_hash(new_password)
            db.session.commit()
            flash('Password changed successfully.', 'success')
            return redirect(url_for('dashboard'))
    return render_template('change_password.html')

@app.route('/users/add', methods=['GET', 'POST'])
@login_required
def add_user():
    # Only allow admin
    user = User.query.get(session['user_id'])
    if user.role != 'admin':
        flash('Only admin can add users.', 'danger')
        return redirect(url_for('dashboard'))
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        role = request.form['role']
        if User.query.filter_by(username=username).first():
            flash('Username already exists.', 'danger')
        else:
            new_user = User(username=username, role=role)
            new_user.set_password(password)
            db.session.add(new_user)
            db.session.commit()
            flash('User created!', 'success')
            return redirect(url_for('dashboard'))
    return render_template('add_user.html')

if __name__ == '__main__':
    create_admin()
    # Set debug=False for production. Set to True only for local testing.
    app.run(debug=False, port=5001)
