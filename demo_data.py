from app import db, Customer, Vehicle, ServiceVisit, ServiceItem, app
import random
import sys
from datetime import datetime, timedelta

CUSTOMER_NAMES = [
    "John Doe", "Jane Smith", "Michael Brown", "Emily Davis", "Chris Wilson",
    "Sarah Johnson", "David Lee", "Linda Martinez", "James Anderson", "Patricia Thomas"
]

MAKES_MODELS = [
    ("Volkswagen", ["Golf", "Passat", "Tiguan"]),
    ("Audi", ["A4", "Q5", "A3"]),
    ("Mercedes-Benz", ["C-Class", "E-Class", "GLA"]),
    ("BMW", ["3 Series", "5 Series", "X3"]),
    ("Nissan", ["Note", "X-Trail", "Navara"]),
    ("Toyota", ["Corolla", "Hilux", "Vitz"])
]

VISIT_CATEGORIES = [
    ("Diagnosis", [
        {"item_name": "OBD Scan", "part_number": "OBD-001", "quantity": 1, "price": 2000, "labour": 500},
        {"item_name": "Engine Check", "part_number": "ENG-CHK", "quantity": 1, "price": 0, "labour": 1500}
    ]),
    ("Suspension", [
        {"item_name": "Front Shock Absorber", "part_number": "SHK-FR-123", "quantity": 2, "price": 7500, "labour": 2000},
        {"item_name": "Control Arm", "part_number": "CTRL-ARM-456", "quantity": 2, "price": 4500, "labour": 1200}
    ]),
    ("Service Engine", [
        {"item_name": "Oil Filter", "part_number": "OF-789", "quantity": 1, "price": 1200, "labour": 300},
        {"item_name": "Engine Oil 5W-30", "part_number": "EO-5W30", "quantity": 4, "price": 900, "labour": 0},
        {"item_name": "Air Filter", "part_number": "AF-321", "quantity": 1, "price": 1500, "labour": 200}
    ]),
    ("Gearbox", [
        {"item_name": "ATF Fluid", "part_number": "ATF-654", "quantity": 5, "price": 850, "labour": 1000},
        {"item_name": "Gearbox Gasket", "part_number": "GB-GSKT-987", "quantity": 1, "price": 1800, "labour": 500}
    ]),
    ("Electrical", [
        {"item_name": "Battery", "part_number": "BAT-555", "quantity": 1, "price": 9500, "labour": 300},
        {"item_name": "Alternator", "part_number": "ALT-888", "quantity": 1, "price": 14500, "labour": 1200}
    ]),
    ("Coding Online", [
        {"item_name": "ECU Coding", "part_number": "ECU-CODE", "quantity": 1, "price": 0, "labour": 3500},
        {"item_name": "Key Programming", "part_number": "KEY-PROG", "quantity": 1, "price": 0, "labour": 2500}
    ])
]

def add_demo_data():
    print("Adding comprehensive demo data...")
    db.session.query(ServiceItem).delete()
    db.session.query(ServiceVisit).delete()
    db.session.query(Vehicle).delete()
    db.session.query(Customer).delete()
    db.session.commit()

    for idx, name in enumerate(CUSTOMER_NAMES):
        phone = f"07{random.randint(10000000,99999999)}"
        email = f"{name.lower().replace(' ','.')}@demo.com"
        customer = Customer(name=name, phone=phone, email=email)
        db.session.add(customer)
        db.session.flush()

        for vnum in range(2):
            make, models = random.choice(MAKES_MODELS)
            model = random.choice(models)
            plate = f"{make[:2].upper()}{random.randint(100,999)}{chr(65+vnum)}"
            vin = f"VIN{random.randint(10000,99999)}{make[:2].upper()}"
            vehicle = Vehicle(
                customer_id=customer.id,
                name=make,
                plate=plate,
                model=model,
                vin_number=vin,
                type=random.choice(["Mechanical", "Electrical", "Service"]),
                status="Active",
                date_booked=(datetime.now() - timedelta(days=random.randint(1, 365))).strftime("%Y-%m-%d"),
                technician=random.choice(["Tech Demo", "Alex", "Sam", "Grace"]),
                history="Demo vehicle history"
            )
            db.session.add(vehicle)
            db.session.flush()

            # Add two visits per vehicle, each with a different category
            visit_types = random.sample(VISIT_CATEGORIES, 2)
            for cat, items in visit_types:
                visit = ServiceVisit(
                    vehicle_id=vehicle.id,
                    notes=f"{cat} performed. {random.choice(['No major issues.', 'Parts replaced.', 'System updated.'])}",
                    visit_category=cat,
                    labour=sum(item['labour'] for item in items)
                )
                db.session.add(visit)
                db.session.flush()
                for item in items:
                    db.session.add(ServiceItem(
                        visit_id=visit.id,
                        item_name=item['item_name'],
                        part_number=item['part_number'],
                        quantity=item['quantity'],
                        price=item['price'],
                        labour=item['labour']
                    ))
    db.session.commit()
    print("Demo data added.")

def remove_demo_data():
    print("Removing demo data...")
    db.session.query(ServiceItem).delete()
    db.session.query(ServiceVisit).delete()
    db.session.query(Vehicle).delete()
    db.session.query(Customer).delete()
    db.session.commit()
    print("Demo data removed.")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python demo_data.py [add|remove]")
        sys.exit(1)
    with app.app_context():
        if sys.argv[1] == "add":
            add_demo_data()
        elif sys.argv[1] == "remove":
            remove_demo_data()
        else:
            print("Unknown command. Use 'add' or 'remove'.")