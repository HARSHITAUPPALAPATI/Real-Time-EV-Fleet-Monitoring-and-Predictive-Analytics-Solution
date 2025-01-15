from flask import Flask, render_template, request, redirect, url_for, flash, session,jsonify, send_file
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from route import haversine, get_city_coordinates, find_best_stations
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import json
from report_generator import generate_charts, generate_pdf, generate_ppt
import re
import joblib  # For loading the model
import pickle
from sklearn.preprocessing import LabelEncoder



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

class duser(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), nullable=False)
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

# LOGIN PAGE
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get("email")
        password = request.form.get("password")
        
        errors = {}

        # Email validation
        if not email:
            errors['email'] = 'Email is required.'
        elif not re.match(r'[^@]+@[^@]+\.[^@]+', email):
            errors['email'] = 'Invalid email format.'

        # Password validation
        if not password:
            errors['password'] = 'Password is required.'
        elif len(password) < 8:
            errors['password'] = 'Password must be at least 8 characters long.'

        # Check if there are any validation errors
        if errors:
            return jsonify(errors), 400

        # Database query to check user credentials
        user = User.query.filter_by(email=email, password=password).first()
        if user:
            session['logged_in'] = True
            session['email'] = email
            return jsonify({'success': 'Login successful! Redirecting...'}), 200
        else:
            return jsonify({'email': 'Invalid email or password!'}), 400

    return render_template('login.html')


# Register page
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form["username"]
        email = request.form["email"]
        password = request.form["password"]
        city = request.form["city"]
        
        errors = {}
        
        # Check if username or email already exists
        existing_user = User.query.filter((User.username == username) | (User.email == email)).first()
        if existing_user:
            errors['username'] = 'Username or Email already exists!'
        
        if not username:
            errors['username'] = 'Username is required.'
        if not email:
            errors['email'] = 'Email is required.'
        elif not re.match(r'[^@]+@[^@]+\.[^@]+', email):
            errors['email'] = 'Invalid email format.'
        if not password:
            errors['password'] = 'Password is required.'
        elif len(password) <= 8:
            errors['password'] = 'Password must be more than 8 characters.'
        if not city:
            errors['city'] = 'City is required.'

        if errors:
            return jsonify(errors), 400

        # Create new user and add to the database
        new_user = User(username=username, email=email, password=password, city=city)
        db.session.add(new_user)
        db.session.commit()

        return jsonify({'success': 'Registration successful! Please log in.'}), 200
        
    return render_template('register.html')

# Success Page
@app.route('/success')
def success():
    return render_template('success.html')


# Register Vehicle Page
@app.route('/register_vehicle', methods=['GET', 'POST'])
def register_vehicle():
    
    errors = {}

    if request.method == 'POST':
        vehicle_id = request.form.get('vehicle_id', '').strip()
        owner_name = request.form.get('owner_name', '').strip()
        registration_number = request.form.get('registration_number', '').strip()
        battery_status = request.form.get('battery_status', '').strip()
        speed = request.form.get('speed', '').strip()
        location = request.form.get('location', '').strip()

        # Validation
        if not vehicle_id:
            errors['vehicle_id'] = "Vehicle ID is required."
        elif len(vehicle_id) > 20:
            errors['vehicle_id'] = "Vehicle ID must be 20 characters or fewer."

        if not owner_name:
            errors['owner_name'] = "Owner Name is required."
        elif not owner_name.isalpha():
            errors['owner_name'] = "Owner Name must contain only letters."

        if not registration_number:
            errors['registration_number'] = "Registration Number is required."
        elif len(registration_number) > 15:
            errors['registration_number'] = "Registration Number must be 15 characters or fewer."

        if not battery_status:
            errors['battery_status'] = "Battery Status is required."
        elif not battery_status.isdigit() or not (0 <= int(battery_status) <= 100):
            errors['battery_status'] = "Battery Status must be a number between 0 and 100."

        if not speed:
            errors['speed'] = "Speed is required."
        elif not speed.isdigit() or int(speed) < 0:
            errors['speed'] = "Speed must be a positive number."

        if not location:
            errors['location'] = "Location is required."

        # If there are errors, re-render the form with error messages
        if errors:
            return render_template('register_vehicle.html', errors=errors)

        try:
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
    
    # Initial render with no errors
    return render_template('register_vehicle.html', errors={})

# Vehicle Status Page
@app.route('/vehicle_status')
def vehicle_status():
    vehicles = Vehicle.query.all()  # Fetch all vehicles
    return render_template('vehicle_status.html', vehicles=vehicles)

# Route Optimization
@app.route('/route_optimization', methods=['GET', 'POST'])
def route_optimization():
    errors = {}
    if request.method == 'POST':
        # Get city names and battery level from the HTML form
        source_city = request.form.get('source_city', '').strip()
        destination_city = request.form.get('destination_city', '').strip()
        battery_level = request.form.get('battery_level', '').strip()

        # Validate inputs
        if not source_city:
            errors['source_city'] = "Source city is required."
        if not destination_city:
            errors['destination_city'] = "Destination city is required."
        if battery_level:
            if not battery_level.isdigit() or not (0 <= int(battery_level) <= 100):
                errors['battery_level'] = "Battery level must be a number between 0 and 100."
        else:
            errors['battery_level'] = "Battery level is required."

        if errors:
            return render_template(
                'route_optimization.html', errors=errors
            )

        # Default battery level if not provided
        battery_level = int(battery_level) if battery_level else 50

        open_cage_api_key = 'cf7d55ca167e4082983a92e8d03f063d'  # Replace with your OpenCage API Key
        open_charge_api_key = 'e5daf4e0-473e-4692-ae2e-3793b1f1d567'  # Replace with your Open Charge Map API Key

        source_coords = get_city_coordinates(open_cage_api_key, source_city)
        dest_coords = get_city_coordinates(open_cage_api_key, destination_city)

        if not source_coords or not dest_coords:
            error_message = "Invalid source or destination city."
            return render_template('route_optimization.html', error=error_message)

        # Find the best EV stations based on the battery percentage
        best_stations = find_best_stations(open_charge_api_key, source_coords, dest_coords, battery_level)

        if not best_stations:
            error_message = "No EV stations found along the route."
            return render_template('route_optimization.html', error=error_message)

        # Render the page with the results
        return render_template(
            'route_optimization.html',
            source=source_city,
            destination=destination_city,
            stations=best_stations,
            errors={}
        )

    return render_template('route_optimization.html', errors={})

# Battery Health Status
@app.route('/battery_health_status', methods=['GET', 'POST'])
def battery_health_status():
    errors = {}
    if request.method == 'POST':
        try:
            capacity = request.form.get('capacity')
            voltage = request.form.get('voltage')
            temperature = request.form.get('temperature')

            # Validate inputs
            if not capacity or not capacity.replace('.', '', 1).isdigit():
                errors['capacity'] = "Capacity must be a numeric value."
            if not voltage or not voltage.replace('.', '', 1).isdigit():
                errors['voltage'] = "Voltage must be a numeric value."
            if not temperature or not temperature.replace('.', '', 1).isdigit():
                errors['temperature'] = "Temperature must be a numeric value."

            if errors:
                return render_template(
                    'battery_health_status.html', errors=errors
                )

            # Convert to floats if valid
            capacity = float(capacity)
            voltage = float(voltage)
            temperature = float(temperature)

            # Predict battery health
            health_score = (capacity / 1000) * (voltage / 4.2) - (temperature / 100)
            health_status = "Good" if health_score > 0.8 else "Moderate" if health_score > 0.5 else "Poor"

            return render_template(
                'battery_health_status.html',
                health_status=health_status,
                health_score=health_score,
                errors={}
            )
        except ValueError:
            errors['general'] = "Invalid input. Please enter valid numeric values."
            return render_template(
                'battery_health_status.html', errors=errors
            )
    return render_template('battery_health_status.html', errors={})






# Load the model using pickle
with open('behavior.pkl', 'rb') as file:
    model = pickle.load(file)

fatigue_level_encoder = LabelEncoder()
fatigue_level_encoder.fit(['medium', 'high','low'])  # Add all possible values here

road_condition_encoder = LabelEncoder()
road_condition_encoder.fit(['wet', 'dry'])  # Add all possible values here

# Define a mapping for the predicted behavior
behavior_mapping = {
    0: 'Normal',
    1: 'Cautious',
    2: 'Aggressive',
    3: 'Risky'
}

def driver_behavior_from_input(speed, acceleration, fatigue_level, road_condition):
    # Encode fatigue_level and road_condition into numeric values
    encoded_fatigue_level = fatigue_level_encoder.transform([fatigue_level])[0]
    encoded_road_condition = road_condition_encoder.transform([road_condition])[0]

    # Prepare the input data for prediction
    input_data = [[speed, acceleration, encoded_fatigue_level, encoded_road_condition]]  # Adjust based on your model's expected format

    # Predict behavior using the model
    predicted_behavior_numeric = model.predict(input_data)[0]  # Assuming single prediction

    # Log the numeric prediction for debugging
    print(f"Predicted numeric behavior: {predicted_behavior_numeric}")

    # Map numeric prediction to the corresponding label
    predicted_behavior = behavior_mapping.get(predicted_behavior_numeric, 'Unknown')
    return predicted_behavior


@app.route('/driver_behavior', methods=['GET', 'POST'])
def driver_behavior():
    errors = {}
    behavior = None

    if request.method == 'POST':
        speed = request.form.get('speed')
        acceleration = request.form.get('acceleration')
        fatigue_level = request.form.get('fatigue_level')
        road_condition = request.form.get('road_condition')

        # Validate inputs
        if not speed or not speed.replace('.', '', 1).isdigit():
            errors['speed'] = "Speed must be a numeric value."
        if not acceleration or not acceleration.replace('.', '', 1).isdigit():
            errors['acceleration'] = "Acceleration must be a numeric value."
        if not fatigue_level:
            errors['fatigue_level'] = "Fatigue level cannot be empty."
        if not road_condition:
            errors['road_condition'] = "Road condition cannot be empty."

        if errors:
            return render_template('driver_behavior.html', errors=errors)

        # Convert to floats if valid
        speed = float(speed)
        acceleration = float(acceleration)

        # Predict behavior using the model
        behavior = driver_behavior_from_input(speed, acceleration, fatigue_level, road_condition)

        return render_template('driver_behavior.html', errors=errors, behavior=behavior)

    return render_template('driver_behavior.html', errors=errors, behavior=behavior)








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
