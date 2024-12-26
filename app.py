from flask import Flask, render_template, request, redirect, url_for, flash, session,jsonify, send_file
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from route import haversine, get_city_coordinates, find_best_stations
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import json
from report_generator import generate_charts, generate_pdf, generate_ppt

app = Flask(__name__)
app.secret_key = 'your_secret_key'  # Needed for session handling
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.db'
db = SQLAlchemy(app)

# User model
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(80), nullable=False)
    city = db.Column(db.String(80), nullable=True)

# Vehicle model
class Vehicle(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    vehicle_id = db.Column(db.String(80), unique=True, nullable=False)
    owner_name = db.Column(db.String(80), nullable=False)
    registration_number = db.Column(db.String(80), nullable=False)
    battery_status = db.Column(db.Integer, nullable=False)
    speed = db.Column(db.Integer, nullable=False)
    location = db.Column(db.String(80), default='Unknown')
    last_updated = db.Column(db.String(80), default='Just Now')

# Home Page
@app.route('/')
def home():
    return render_template('home.html')

# Register Page
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']
        city = request.form['city']

        # Check if user exists
        existing_user = User.query.filter_by(email=email).first()
        if existing_user:
            return render_template('already_exists.html')  # User exists page
        else:
            # Create new user
            new_user = User(username=username, email=email, password=password, city=city)
            db.session.add(new_user)
            db.session.commit()
            return redirect(url_for('login'))
    return render_template('register.html')

# Login Page
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']

        # Check if user exists
        user = User.query.filter_by(email=email, password=password).first()
        if user:
            session['user'] = user.username  # Save user session
            return redirect(url_for('success'))
        else:
            flash('Invalid email or password!', 'error')
    return render_template('login.html')

# Success Page
@app.route('/success')
def success():
    if 'user' not in session:
        return redirect(url_for('login'))
    return render_template('success.html', username=session['user'])


# Register Vehicle Page
@app.route('/register_vehicle', methods=['GET', 'POST'])
def register_vehicle():
    if 'user' not in session:
        return redirect(url_for('login'))
    if request.method == 'POST':
        try:
            vehicle_id = request.form['vehicle_id']
            owner_name = request.form['owner_name']
            registration_number = request.form['registration_number']
            battery_status = request.form['battery_status']
            speed = request.form['speed']
            location = request.form['location']

            # Check if vehicle ID already exists
            existing_vehicle = Vehicle.query.filter_by(vehicle_id=vehicle_id).first()
            if existing_vehicle:
                flash('Vehicle ID already exists!', 'error')
                return redirect(url_for('register_vehicle'))

            # Create new vehicle
            new_vehicle = Vehicle(
                vehicle_id=vehicle_id,
                owner_name=owner_name,
                registration_number=registration_number,
                battery_status=int(battery_status),
                speed=int(speed),
                location=location,
                last_updated=datetime.now().strftime('%Y-%m-%d %H:%M:%S') 
            )
            db.session.add(new_vehicle)
            db.session.commit()
            flash('Vehicle registered successfully!', 'success')
            return redirect(url_for('vehicle_status'))
        except Exception as e:
            flash(f"Error: {str(e)}", "error")
            return redirect(url_for('register_vehicle'))
    return render_template('register_vehicle.html')

# Vehicle Status Page
@app.route('/vehicle_status')
def vehicle_status():
    if 'user' not in session:
        return redirect(url_for('login'))
    vehicles = Vehicle.query.all()  # Fetch all vehicles
    return render_template('vehicle_status.html', vehicles=vehicles)

# Route Optimization
@app.route('/route_optimization', methods=['GET', 'POST'])
def route_optimization():
    if request.method == 'POST':
        # Get city names and battery level from the HTML form
        source_city = request.form.get('source_city', '').strip()
        destination_city = request.form.get('destination_city', '').strip()
        battery = request.form.get('battery', 50)  # Default battery level 50%

        if not source_city or not destination_city:
            error_message = "Both source and destination cities are required."
            return render_template('route_optimization.html', error=error_message)
        
        open_cage_api_key = 'cf7d55ca167e4082983a92e8d03f063d'  # Replace with your OpenCage API Key
        open_charge_api_key = 'e5daf4e0-473e-4692-ae2e-3793b1f1d567'  # Replace with your Open Charge Map API Key

        source_coords = get_city_coordinates(open_cage_api_key, source_city)
        dest_coords = get_city_coordinates(open_cage_api_key, destination_city)

        if not source_coords or not dest_coords:
            error_message = "Invalid source or destination city."
            return render_template('route_optimization.html', error=error_message)

        # Find the best EV stations based on the battery percentage
        best_stations = find_best_stations(open_charge_api_key, source_coords, dest_coords, battery)

        if not best_stations:
            error_message = "No EV stations found along the route."
            return render_template('route_optimization.html', error=error_message)

        # Render the page with the results
        return render_template('route_optimization.html', source=source_city, destination=destination_city, stations=best_stations)

    return render_template('route_optimization.html')

# Battery Health Status
@app.route('/battery_health_status', methods=['GET', 'POST'])
def battery_health_status():
    if request.method == 'POST':
        # Retrieve form data
        try:
            capacity = float(request.form['capacity'])
            voltage = float(request.form['voltage'])
            temperature = float(request.form['temperature'])
            
            # Example logic to predict battery health
            health_score = (capacity / 1000) * (voltage / 4.2) - (temperature / 100)
            health_status = "Good" if health_score > 0.8 else "Moderate" if health_score > 0.5 else "Poor"
            
            # Render the result on the same page
            return render_template('battery_health_status.html', health_status=health_status, health_score=health_score)
        except ValueError:
            flash("Invalid input. Please enter numeric values.")
            return redirect(url_for('battery_health_status'))
    return render_template('battery_health_status.html')
@app.route('/maintenance_alerts')
def maintenance_alerts():
    return render_template('maintenance_alerts.html')
@app.route('/achievements')
def achievements():
    return render_template('achievements.html')
@app.route('/notification')
def notification():
    return render_template('notification.html')
@app.route('/subscribe')
def subscribe():
    return render_template('subscribe.html')
@app.route('/signin', methods=['GET', 'POST'])
def signin():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        # Check user in database
        user = User.query.filter_by(username=username, password=password).first()
        if user:
            session['logged_in'] = True
            session['username'] = username
            flash('Successfully Signed In!', 'success')
            return redirect('/home')
        else:
            flash('Invalid Username or Password!', 'error')
    return render_template('signin.html')



# Sign Up route
@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        age = request.form['age']

        # Check if the username already exists
        existing_user = User.query.filter_by(username=username).first()
        if existing_user:
            flash('Username already exists!', 'error')
            return redirect(url_for('signup'))

        # Create a new user
        new_user = User(username=username, password=password, age=age)
        db.session.add(new_user)
        db.session.commit()
        flash('Successfully Signed Up!', 'success')
        return redirect(url_for('signin'))
    return render_template('signup.html')

# Logout
@app.route('/logout')
def logout():
    session.pop('user', None)  # Clear session
    return render_template('logout.html')

# Initialize database (first time only)
with app.app_context():
    db.create_all()




# Energy Consumption Route
@app.route('/energy_consumption')
def energy_consumption():
    # Load the dataset
    df = pd.read_csv('operational_Cost.csv', parse_dates=['Datetime'])

    # Sort data by datetime
    df = df.sort_values(by='Datetime')

    # Prepare data for Line Chart
    line_chart_data = {
        "dates": df['Datetime'].dt.strftime('%Y-%m-%d %H:%M:%S').tolist(),  # Convert datetime to string
        "consumption": df['COMED_MW'].tolist(),
        "cost": df['Operational_Costs'].tolist()
    }

    # Prepare data for Pie Chart (Monthly Aggregation)
    df['month'] = df['Datetime'].dt.strftime('%B')  # Extract month names
    monthly_energy = df.groupby('month')['COMED_MW'].sum()
    pie_chart_data = {
        "labels": monthly_energy.index.tolist(),
        "values": monthly_energy.tolist()
    }

    # Pass data to the template
    return render_template(
        'energy_consumption.html',
        line_chart_data=json.dumps(line_chart_data),
        pie_chart_data=json.dumps(pie_chart_data)
    )

@app.route('/generate_report', methods=['POST'])
def generate_report():
    # Parse JSON request
    data = request.get_json()
    report_type = data.get('report_type')

    # Sample data
    report_data = {
        "Weather": "Sunny, 25°C",
        "Battery Health": "85%",
        "Driver Analysis": "Average Speed: 60 km/h",
        "Energy Consumption": "50 kWh",
        "Operational Cost": "$25"
    }
    charts = generate_charts()  # Generate charts

    if report_type == 'pdf':
        report_file = generate_pdf(report_data, charts)
    elif report_type == 'ppt':
        report_file = generate_ppt(report_data, charts)
    else:
        return jsonify({'error': 'Invalid report type'}), 400

    # Return the generated file
    return send_file(report_file, as_attachment=True)



if __name__ == '__main__':
    app.run(debug=True) 





























