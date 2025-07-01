# backend/app.py

from flask import Flask, request, jsonify, render_template, url_for, redirect
from flask_sqlalchemy import SQLAlchemy
import os
import uuid # For generating unique IDs for briefing links
import datetime

app = Flask(__name__)

# --- Database Configuration ---
# Configure SQLite database. The path creates a 'site.db' inside 'instance' folder.
# 'instance' folder is outside the 'backend' folder to keep it separate from application code.
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///site.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False # Disable tracking modifications to save memory

db = SQLAlchemy(app)

# --- Define the FlightBriefing Model ---
# This class represents your database table structure
class FlightBriefing(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    # Use a UUID for the public-facing link to make it unguessable
    public_id = db.Column(db.String(36), unique=True, nullable=False, default=lambda: str(uuid.uuid4()))

    # Pilot & Aircraft Info (from initial form)
    pilot_name = db.Column(db.String(100), nullable=True)
    tail_number = db.Column(db.String(20), nullable=True)

    # Core Flight Details (from initial form)
    departure_icao = db.Column(db.String(10), nullable=False)
    destination_icao = db.Column(db.String(10), nullable=False)
    flight_date = db.Column(db.Date, nullable=False) # Store as Date object
    flight_time = db.Column(db.Time, nullable=False) # Store as Time object

    # Additional Details (from "Detailed Pilot Form" - will be added later)
    route_overview = db.Column(db.Text, nullable=True)
    baggage_allowance = db.Column(db.Text, nullable=True)
    documents_to_bring = db.Column(db.Text, nullable=True)
    special_notes = db.Column(db.Text, nullable=True)

    # Future fields (for API integrations / more advanced briefings)
    # Weather Details (e.g., fetched from API)
    dep_weather_summary = db.Column(db.Text, nullable=True)
    dest_weather_summary = db.Column(db.Text, nullable=True)
    # You might want more structured weather data (e.g., temp, wind, pressure, METAR/TAF raw)
    # dep_metar = db.Column(db.String(200), nullable=True)
    # dest_taf = db.Column(db.String(500), nullable=True)

    # Detailed Airport Information (e.g., fetched from API or manually added)
    dep_fbo_info = db.Column(db.Text, nullable=True)
    dest_fbo_info = db.Column(db.Text, nullable=True)
    # You could add specific airport amenities, ground transport links, etc.

    # Route Coordinates for Map (e.g., JSON string or separate table relation)
    # For MVP, a simple string of coordinates, later a more complex structure
    flight_path_coordinates = db.Column(db.Text, nullable=True) # e.g., "[[lat1,lon1],[lat2,lon2],...]"

    # IMSAFE Briefing (user input from detailed form)
    imsafe_notes = db.Column(db.Text, nullable=True)

    # Timestamp for when the briefing was created
    created_at = db.Column(db.DateTime, default=db.func.now())
    updated_at = db.Column(db.DateTime, default=db.func.now(), onupdate=db.func.now())

    def __repr__(self):
        return f"<FlightBriefing {self.public_id} from {self.departure_icao} to {self.destination_icao}>"

# --- Basic Routes ---

# Home route (serves the pilot input HTML page)
# In a real app, this might be split, but for development, it's convenient
@app.route('/')
def home():
    # Assuming your frontend HTML files are in a 'frontend' directory sibling to 'backend'
    # For development, you might just open the HTML file directly in browser or serve like this
    return render_template('pilot_side.html')

# Passenger briefing page route
# This route expects a public_id in the URL
@app.route('/briefing/<uuid:public_id>')
def passenger_briefing(public_id):
    briefing = FlightBriefing.query.filter_by(public_id=str(public_id)).first_or_404()
    # In a real app, you would pass the 'briefing' object to the template
    # and use Jinja2 to populate the HTML. For now, we'll render the static HTML.
    # We'll update this to pass data and use Jinja2 in a later step.
    return render_template('passenger_side.html', briefing=briefing)


# API endpoint to handle the initial pilot form submission
# This will be called by JavaScript on your pilot_input.html
@app.route('/api/flight-briefings/initial', methods=['POST'])
def create_initial_briefing():
    data = request.get_json()
    print("Received data:", data) # For debugging: print incoming data

    # Basic validation for required fields
    required_fields = ['departure_icao', 'destination_icao', 'flight_date', 'flight_time']
    if not all(k in data and data[k] for k in required_fields): # Added 'and data[k]' to check for non-empty values
        missing_fields = [k for k in required_fields if k not in data or not data[k]]
        return jsonify({"error": f"Missing or empty required fields: {', '.join(missing_fields)}"}), 400

    try:
        # Parse date and time strings using Python's datetime module
        # .date() extracts only the date part from a datetime object
        # .time() extracts only the time part from a datetime object
        parsed_flight_date = datetime.datetime.strptime(data['flight_date'], '%Y-%m-%d').date()
        parsed_flight_time = datetime.datetime.strptime(data['flight_time'], '%H:%M').time()

        # Create a new FlightBriefing instance
        new_briefing = FlightBriefing(
            # pilot_name and tail_number are optional for now, as per your last HTML structure
            # If you add them back to HTML, ensure they are passed in `data` and uncomment below:
            # pilot_name=data.get('pilot_name'),
            # tail_number=data.get('tail_number'),
            departure_icao=data['departure_icao'],
            destination_icao=data['destination_icao'],
            flight_date=parsed_flight_date,
            flight_time=parsed_flight_time
        )
        db.session.add(new_briefing)
        db.session.commit()

        print(f"Briefing created with public_id: {new_briefing.public_id}") # Debugging print

        return jsonify({
            "message": "Initial briefing created successfully.",
            "public_id": new_briefing.public_id,
            "redirect_url": url_for('detailed_pilot_form', public_id=new_briefing.public_id, _external=True) # Use _external=True for full URL
        }), 201

    except ValueError as e:
        db.session.rollback()
        # Provide a user-friendly error message for date/time format issues
        return jsonify({"error": f"Invalid date or time format. Please ensure date is YYYY-MM-DD and time is HH:MM (24-hour format). Details: {e}"}), 400
    except Exception as e:
        db.session.rollback()
        print(f"Server error during briefing creation: {e}") # Debugging print
        return jsonify({"error": "An unexpected server error occurred. Please try again later."}), 500

# Placeholder for the detailed pilot form page.
# This would render a new HTML template for the detailed form.
@app.route('/pilot/briefing-details/<uuid:public_id>')
def detailed_pilot_form(public_id):
    # Retrieve the initial briefing to pre-fill some fields or ensure it exists
    briefing = FlightBriefing.query.filter_by(public_id=str(public_id)).first_or_404()
    # For now, we'll just show a simple message.
    # Later, this will render a dedicated HTML template for the detailed form.
    return f"<h1>Detailed Briefing Form for Flight ID: {public_id}</h1><p>Pilot Name: {briefing.pilot_name}</p><p>This is where you'd add more specifics like FBOs, baggage rules, special notes, etc.</p>"


# --- Database Initialization ---
# This block ensures that the database tables are created when the app runs
# You can run this once to create your database file.
# For more complex database migrations, consider Flask-Migrate.
def create_database():
    # Make sure the 'instance' directory exists
    instance_path = os.path.join(app.root_path, 'instance')
    os.makedirs(instance_path, exist_ok=True)
    
    with app.app_context():
        db.create_all()
        print("Database tables created!")

# --- Running the application ---
if __name__ == '__main__':
    # You might want to call create_database() manually once, or use Flask-CLI command.
    # For now, let's keep it simple for initial setup.
    # To create tables, run `python app.py` once, then comment out or remove create_database() for regular runs.
    # Or, even better, run it from Flask CLI: `flask --app app shell` then `db.create_all()`
    create_database() # This will create the database file and tables if they don't exist

    # To run the development server
    app.run(debug=True) # debug=True enables reloader and debugger