from flask import Flask, render_template, request, redirect, flash, url_for, jsonify, session, make_response
from flask_sqlalchemy import SQLAlchemy
from flask_mail import Mail, Message
from datetime import datetime, timedelta
from dotenv import load_dotenv
from werkzeug.utils import secure_filename
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from flask_session import Session
import razorpay
import os
import requests
import json
import pymysql
pymysql.install_as_MySQLdb()
import logging

load_dotenv()
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

app = Flask(__name__, static_folder='static', static_url_path='/static')
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY')  # Ensure this is set in Railway Variables
app.config['SESSION_TYPE'] = 'filesystem'
app.config['SESSION_COOKIE_SECURE'] = True  # Forces cookies to use HTTPS
app.config['SESSION_COOKIE_HTTPONLY'] = True  # Prevents JavaScript access
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'  # Mitigates CSRF
Session(app)
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(minutes=30)  # 30-minute timeout
app.config['SESSION_PERMANENT'] = True

from flask_wtf import CSRFProtect
csrf = CSRFProtect(app)

def create_tables():
    with app.app_context():
        db.create_all()

@app.after_request
def apply_security_headers(response):
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
    response.headers['X-Frame-Options'] = 'DENY'
    response.headers['X-XSS-Protection'] = '1; mode=block'
    response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
    response.headers['Content-Security-Policy'] = (
    "default-src 'self' https://fonts.googleapis.com https://fonts.gstatic.com https://www.juicer.io https://static.juicer.io https://www.google.com https://maps.googleapis.com https://maps.gstatic.com;"
    "script-src 'self' 'unsafe-inline' https://code.jquery.com https://www.juicer.io https://checkout.razorpay.com https://www.paypal.com;"
    "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com https://www.juicer.io;"
    "font-src 'self' https://fonts.gstatic.com https://static.juicer.io;"
    "img-src 'self' data: https:;"
    "frame-src 'self' https://www.google.com https://www.google.com/maps/embed https://maps.googleapis.com https://www.paypal.com https://www.sandbox.paypal.com https://api.razorpay.com;"
    "connect-src 'self' https://api.razorpay.com https://api-m.sandbox.paypal.com https://www.juicer.io;"
    )


    return response


# Database configuration
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('SQLALCHEMY_DATABASE_URI')
db = SQLAlchemy(app)

# Email configuration
app.config['MAIL_SERVER'] = os.getenv('MAIL_SERVER')
app.config['MAIL_PORT'] = int(os.getenv('MAIL_PORT'))
app.config['MAIL_USE_TLS'] = os.getenv('MAIL_USE_TLS') == 'True'
app.config['MAIL_USERNAME'] = os.getenv('MAIL_USERNAME')
app.config['MAIL_PASSWORD'] = os.getenv('MAIL_PASSWORD')
app.config['MAIL_DEFAULT_SENDER'] = os.getenv('MAIL_DEFAULT_SENDER')
mail = Mail(app)

UPLOAD_FOLDER = os.path.join(app.root_path, 'static', 'images')
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

# Database models
class Contact(db.Model):
    sno = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(30), nullable=False)
    email = db.Column(db.String(50), nullable=False)
    subject = db.Column(db.String(40), nullable=True)
    date = db.Column(db.DateTime, nullable=False)
    message = db.Column(db.String(200), nullable=False)

class Volunteer(db.Model):
    sno = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(30), nullable=False)
    email = db.Column(db.String(50), nullable=False)
    phone = db.Column(db.String(40), nullable=False)
    date = db.Column(db.DateTime, nullable=False)
    reason = db.Column(db.String(200), nullable=False)

class Donation(db.Model):
    sno = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(30), nullable=False)
    email = db.Column(db.String(50), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    date = db.Column(db.DateTime, nullable=False)
    payment_id = db.Column(db.String(50), nullable=True)
    order_id = db.Column(db.String(50), nullable=True)
    payment_method = db.Column(db.String(20), nullable=False, default='razorpay')

# Google Sheets setup
SCOPES = ['https://www.googleapis.com/auth/spreadsheets']
creds = Credentials.from_service_account_info(json.loads(os.getenv('GOOGLE_APPLICATION_CREDENTIALS_JSON')), scopes=SCOPES)
service = build('sheets', 'v4', credentials=creds)
SHEET_ID = os.getenv('CLIENT_SHEET_ID')

def get_latest_fundraisers(limit=6):
    sheet = service.spreadsheets()
    result = sheet.values().get(spreadsheetId=SHEET_ID, range='Form Responses 1').execute()
    data = result.get('values', [])
    if data:
        headers = data[0]
        fundraisers = []
        for i, row in enumerate(data[1:], start=1):
            fundraisers.append({
                'id': i,
                'name': row[1] if len(row) > 1 else 'Unnamed',
                'amount': row[2] if len(row) > 2 else 'N/A',
                'description': row[3] if len(row) > 3 else 'No description',
                'image_url': row[4] if len(row) > 4 else None
            })
        return fundraisers[::-1][:limit]  # Reverse the list and limit to the specified number
    return []

from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)
limiter.init_app(app)

@app.route('/authenticate-client', methods=['POST'])
@limiter.limit("10 per hour")  # Limit to 10 attempts per IP per hour
def authenticate_client():
    client_key = os.getenv('CLIENT_KEY')
    provided_key = request.form.get('client_key')
    if provided_key == client_key:
        session['authenticated'] = True
        return redirect(url_for('submit_fundraiser'))
    flash('Invalid client key. Access denied.')
    return redirect(url_for('home'))

# Routes
@app.route('/')
def home():
    fundraisers = get_latest_fundraisers()
    return render_template('index.html', fundraisers=fundraisers)

@app.route('/about')
def about():
    return render_template('about.html')

@app.route('/gallery')
def gallery():
    return render_template('gallery.html')

@app.route('/blog-single')
def blog_single():
    return render_template('blog-single.html')

@app.route('/contact', methods=["GET", "POST"])
@limiter.limit("10 per hour")  # Added rate limit
def contact():
    if request.method == "POST":
        name = request.form.get('name')
        email = request.form.get('email')
        subject = request.form.get('subject')
        message = request.form.get('message')
        if name and email and subject and message:
            # Save to database
            entry = Contact(name=name, email=email, subject=subject, message=message, date=datetime.now())
            db.session.add(entry)
            db.session.commit()

            # Send email notification to client
            msg = Message('New Contact Us Submission',
                          recipients=[os.getenv('CLIENT_EMAIL')],  # Use env var for client's email
                          body=f"""
                          New submission from Contact Us form:
                          - Name: {name}
                          - Email: {email}
                          - Subject: {subject}
                          - Message: {message}
                          - Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S IST')}
                          """)
            mail.send(msg)

            flash('Message sent successfully!')
            return redirect(url_for('contact', success_message=True))
        else:
            flash('Please fill in all fields.', 'error')
    success_message = request.args.get('success_message')
    return render_template('contact.html', success_message=success_message)

@app.route('/donate')
def donate():
    donors = Donation.query.order_by(Donation.date.desc()).limit(4).all()
    return render_template('donate.html', donors=donors, key_id=os.getenv("RAZORPAY_KEY_ID"), paypal_client_id=os.getenv("PAYPAL_CLIENT_ID"))

@app.route('/join_us', methods=["GET", "POST"])
@limiter.limit("10 per hour")  # Reduced from 100 per day to 10 per hour
def join_us():
    if request.method == "POST":
        name = request.form.get('name')
        email = request.form.get('email')
        phone = request.form.get('phone')
        reason = request.form.get('reason')
        if name and email and phone and reason:
            # Save to database
            entry = Volunteer(name=name, email=email, phone=phone, reason=reason, date=datetime.now())
            db.session.add(entry)
            db.session.commit()

            # Send email notification to client
            msg = Message('New Join Us Submission',
                          recipients=[os.getenv('CLIENT_EMAIL')],  # Use env var for client's email
                          body=f"""
                          New submission from Join Us form:
                          - Name: {name}
                          - Email: {email}
                          - Phone: {phone}
                          - Reason: {reason}
                          - Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S IST')}
                          """)
            mail.send(msg)

            flash('Thank you for signing up as a volunteer!')
            return redirect(url_for('join_us', success_message=True))
        else:
            flash('Please fill in all fields.', 'error')
    success_message = request.args.get('success_message')
    return render_template('join_us.html', success_message=success_message)

# Razorpay client
razorpay_client = razorpay.Client(auth=(os.getenv("RAZORPAY_KEY_ID"), os.getenv("RAZORPAY_KEY_SECRET")))

# PayPal client
def get_access_token():
    auth = (os.getenv("PAYPAL_CLIENT_ID"), os.getenv("PAYPAL_CLIENT_SECRET"))
    response = requests.post(
        'https://api-m.sandbox.paypal.com/v1/oauth2/token',
        auth=auth,
        data={'grant_type': 'client_credentials'},
        headers={'Accept': 'application/json'}
    )
    response.raise_for_status()
    return response.json()['access_token']

@app.route('/process-donation', methods=['POST'])
def process_donation():
    data = request.get_json()
    logger.debug("Received donation request: %s", data)  # ✅ log input

    donor_name = data.get('donor-name')
    donor_email = data.get('donor-email')

    try:
        amount = int(float(data.get('custom-amount')) * 100)
    except (ValueError, TypeError) as e:
        logger.error("Invalid amount: %s", data.get('custom-amount'))  # 🧩 clearer log
        return jsonify({"error": "Invalid donation amount"}), 400

    order_data = {
        "amount": amount,
        "currency": "INR",
        "receipt": f"donation_{donor_name}",
        "notes": {
            "name": donor_name,
            "email": donor_email
        }
    }
    logger.debug("Final order data: %s", order_data)  # ✅ log Razorpay payload

    try:
        order = razorpay_client.order.create(data=order_data)
        return jsonify({"order_id": order['id']})
    except Exception as e:
        logger.error("Razorpay order creation failed: %s", str(e))  # ❗ key debug output
        return jsonify({"error": str(e)}), 500


@app.route('/verify-payment', methods=['POST'])
def verify_payment():
    from hashlib import sha256
    import hmac
    data = request.get_json()
    payment_id = data['razorpay_payment_id']
    order_id = data['razorpay_order_id']
    signature = data['razorpay_signature']

    generated_signature = hmac.new(
        os.getenv("RAZORPAY_KEY_SECRET").encode(),
        f"{order_id}|{payment_id}".encode(),
        sha256
    ).hexdigest()

    if generated_signature == signature:
        order = razorpay_client.order.fetch(order_id)
        notes = order.get('notes', {})
        donation = Donation(
            name=notes.get('name', 'Anonymous'),
            email=notes.get('email', ''),
            amount=order['amount'] / 100,
            date=datetime.now(),
            payment_id=payment_id,
            order_id=order_id,
            payment_method='razorpay'
        )
        db.session.add(donation)
        db.session.commit()

        try:
            msg = Message(
                subject="Thank You for Your Donation!",
                recipients=[notes.get('email')],
                html=render_template(
                    'email_receipt.html',
                    name=notes.get('name', 'Donor'),
                    amount=order['amount'] / 100,
                    date=donation.date.strftime('%b %d, %Y'),
                    payment_id=payment_id
                )
            )
            mail.send(msg)
            #print(f"Email sent successfully to {notes.get('email')} at {datetime.now()}")
        except Exception as e:
            pass
            #print(f"Failed to send email: {str(e)}")

        session['just_donated'] = True
        return jsonify({"status": "success", "redirect_url": url_for('donation_success', _external=True)})
    else:
        return jsonify({"status": "failed", "error": "Payment verification failed. Please try again."}), 400
    
class PayPalClient:
    def __init__(self):
        self.base_url = 'https://api-m.sandbox.paypal.com'
        self.access_token = get_access_token()

    def create_order(self, amount, donor_name, donor_email):
        url = f'{self.base_url}/v2/checkout/orders'
        headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {self.access_token}'
        }
        payload = {
            "intent": "CAPTURE",
            "purchase_units": [{
                "amount": {
                    "currency_code": "USD",  # Changed from INR to USD
                    "value": f"{amount:.2f}",
                    "breakdown": {
                        "item_total": {
                            "currency_code": "USD",
                            "value": f"{amount:.2f}"
                        }
                    }
                },
                "items": [{
                    "name": f"Donation by {donor_name}",
                    "unit_amount": {
                        "currency_code": "USD",
                        "value": f"{amount:.2f}"
                    },
                    "quantity": "1",
                    "description": f"Donation from {donor_email}"
                }],
                "description": f"Donation to Your NGO by {donor_name}",
                "custom_id": donor_name,
                "soft_descriptor": "NGO DONATION"
            }],
            "application_context": {
                "return_url": url_for('capture_paypal_payment', _external=True),
                "cancel_url": url_for('donate', _external=True),
                "brand_name": "Your NGO",
                "locale": "en-IN",
                "shipping_preference": "NO_SHIPPING"
            }
        }
        response = requests.post(url, json=payload, headers=headers)
        if response.status_code != 201:
            # print(f"Error Response: {response.status_code} - {response.text}")
            return {"error": response.text}, response.status_code  # Return dict with status
        return response.json()

    def capture_order(self, order_id):
        url = f'{self.base_url}/v2/checkout/orders/{order_id}/capture'
        headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {self.access_token}'
        }
        response = requests.post(url, headers=headers)
        response.raise_for_status()
        return response.json()

paypal_client = PayPalClient()

@app.route('/create-paypal-order', methods=['POST'])
def create_paypal_order():
    data = request.get_json()
    # logger.debug(f"Received data: {data}")
    donor_name = data.get('donor-name')
    donor_email = data.get('donor-email')
    amount = float(data.get('amount', 0))

    if not donor_name or not donor_email or amount <= 0:
        # logger.error(f"Invalid input: name={donor_name}, email={donor_email}, amount={amount}")
        return jsonify({'error': 'Missing or invalid data'}), 400

    session['donor_name'] = donor_name  # Store in session
    session['donor_email'] = donor_email  # Store in session

    paypal_client = PayPalClient()
    order_response = paypal_client.create_order(amount, donor_name, donor_email)
    if isinstance(order_response, tuple) and 'error' in order_response[0]:
        return jsonify(order_response[0]), order_response[1]
    return jsonify({'orderID': order_response['id']})

@app.route('/capture-paypal-payment', methods=['POST'])
def capture_paypal_payment():
    data = request.get_json()
    order_id = data.get('orderID')
    #logger.debug(f"Received data for capture: {data}")

    try:
        capture = paypal_client.capture_order(order_id)
        #logger.debug(f"Capture response: {capture}")
        
        purchase_unit = capture['purchase_units'][0]
        captures = purchase_unit.get('payments', {}).get('captures', [])
        if not captures:
            raise ValueError("No capture data found in response")
        
        capture_data = captures[0]
        amount = float(capture_data['amount']['value'])
        payment_id = capture_data['id']
        donor_name = session.get('donor_name', purchase_unit.get('custom_id', 'Anonymous'))  # Use session name
        donor_email = session.get('donor_email') or ''  # Use session email

        #logger.debug(f"Using donor_name: {donor_name} from session: {session.get('donor_name')} or custom_id: {purchase_unit.get('custom_id')}")
        #logger.debug(f"Using donor_email: {donor_email} from session: {session.get('donor_email')}")

        donation = Donation(
            name=donor_name,
            email=donor_email,
            amount=amount,
            date=datetime.now(),
            payment_id=payment_id,
            order_id=order_id,
            payment_method='paypal'
        )
        db.session.add(donation)
        db.session.commit()

        try:
            msg = Message(
                subject="Thank You for Your Donation!",
                recipients=[donor_email] if donor_email else [],
                html=render_template(
                    'email_receipt.html',
                    name=donor_name,
                    amount=amount,
                    date=donation.date.strftime('%b %d, %Y'),
                    payment_id=payment_id,
                    currency_symbol='$' if donation.payment_method == 'paypal' else '₹'  # Dynamic currency
                )
            )
            #logger.debug(f"Email message created: subject={msg.subject}, recipients={msg.recipients}, html={msg.html}")
            if donor_email:
                with app.app_context():
                    mail.send(msg)
                #logger.info(f"Email sent successfully to {donor_email} at {datetime.now()}")
            else:
                pass
                #logger.warning("No valid donor email provided, skipping email")
        except Exception as e:
            pass
            #logger.error(f"Failed to send email: {str(e)}", exc_info=True)

        session['just_donated'] = True
        session['donor_name'] = donor_name  # Update session name
        return jsonify({'status': 'success', 'redirect_url': url_for('donation_success', _external=True)})
    except requests.exceptions.RequestException as e:
        #logger.error(f"Payment capture failed: {str(e)}")
        return jsonify({'status': 'failure', 'error': str(e)}), 400
    except (KeyError, ValueError) as e:
        #logger.error(f"Invalid capture response: {str(e)}")
        return jsonify({'status': 'failure', 'error': f"Invalid response data: {str(e)}"}), 400
    except Exception as e:
        #logger.error(f"Unexpected error: {str(e)}")
        return jsonify({'status': 'failure', 'error': str(e)}), 500

@app.route('/donation-success')
def donation_success():
    if not session.get('just_donated'):
        flash('You must complete a donation to view this page.', 'error')
        return redirect(url_for('donate'))
    
    session.pop('just_donated', None)
    latest_donation = Donation.query.order_by(Donation.date.desc()).first()
    if latest_donation:
        currency_symbol = '$' if latest_donation.payment_method == 'paypal' else '₹'
        return render_template('success.html', 
                              name=session.get('donor_name', latest_donation.name),  # Fallback to DB if session fails
                              amount=latest_donation.amount,
                              email=latest_donation.email,
                              date=latest_donation.date.strftime('%b %d, %Y'),
                              payment_id=latest_donation.payment_id,
                              currency_symbol=currency_symbol)
    return render_template('success.html', 
                          name='Donor',
                          amount='XXX',
                          email='your email',
                          date=datetime.now().strftime('%b %d, %Y'),
                          payment_id='XXX-XXX-XXX',
                          currency_symbol='₹')

@app.route('/fundraiser/<int:fundraiser_id>')
def fundraiser(fundraiser_id):
    sheet = service.spreadsheets()
    result = sheet.values().get(spreadsheetId=SHEET_ID, range='Form Responses 1').execute()
    data = result.get('values', [])
    if data:
        headers = data[0]
        for i, row in enumerate(data[1:], start=1):
            if i == fundraiser_id:
                edit_url = row[headers.index('Edit Link')] if 'Edit Link' in headers else None
                return render_template('fundraiser.html', fundraiser_id=fundraiser_id, name=row[1] if len(row) > 1 else 'Unnamed', amount=row[2] if len(row) > 2 else 'N/A', description=row[3] if len(row) > 3 else 'No description', image_url=row[4] if len(row) > 4 else None, edit_url=edit_url)
    return render_template('fundraiser.html', fundraiser_id=fundraiser_id)

@app.route('/success/<int:story_id>')
def success_story(story_id):
    # Sample data - replace with database query
    success_stories = {
        1: {
            'title': "🐾 A New Dawn for Animal Welfare: SESF Launches Meerut’s First Animal Ambulance",
            'image': "https://via.placeholder.com/600x300?text=Lucky's+Recovery",
            'description': """In a heartfelt move that blends compassion with action, SESF—Sardhana Environmental and Social Foundation—made history by introducing Meerut’s first dedicated animal ambulance. This transformative leap in animal welfare was made possible thanks to the generous donation from Maneka Gandhi, a towering advocate for animal rights in India.
            Her contribution wasn’t just a van outfitted with medical supplies. It was a rolling sanctuary, purpose-built for rescuing, treating, and transporting injured or distressed animals across the region. For SESF, this vehicle represents more than convenience—it’s a declaration of their mission to ensure that animals, too, receive timely care and dignity.
            When the ambulance arrived, wrapped in anticipation and promise, the SESF team wasted no time. Soon, it was on its first call—responding to a wounded street dog that had been struck by a vehicle. With proper equipment and trained volunteers, the ambulance offered care on the spot, changing the narrative for countless animals who would’ve otherwise been forgotten.
            Our director shared: “Before this, our response was limited. We had heart, but no wheels. Now we can reach any corner of Meerut, and that changes everything.”
            As the siren now wails through the city, it carries more than sound—it carries a message: Every life matters. And with SESF and this pioneering ambulance, Meerut has taken its first bold step toward a more humane future.
            """,
            'impact': "With Meerut's first animal ambulance, SESF turns compassion into rapid response—redefining how a city protects its voiceless lives."
        }
    }
    story_data = success_stories.get(story_id)
    return render_template('success_story.html', story_id=story_id, story_data=story_data)

# @app.route('/success/all')
# def success_all():
#     return render_template('success_all.html')

@app.route('/submit-fundraiser', methods=['GET', 'POST'])
def submit_fundraiser():
    if request.method == 'POST' and not session.get('authenticated', False):
        flash('Please authenticate first.')
        return redirect(url_for('home'))
    if request.method == 'POST' and session.get('authenticated', False):
        name = request.form.get('fundraiser_name')
        amount = request.form.get('amount')
        description = request.form.get('description')
        image = request.files.get('image')
        if not image or not image.filename:
            flash('Image attachment is required.')
            return render_template('submit_fundraiser.html', show_modal=False)
        filename = secure_filename(image.filename)
        image_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        image.save(image_path)
        image_url = url_for('static', filename=f'images/{filename}')
        values = [datetime.now().isoformat(), name, amount, description, image_url]
        sheet = service.spreadsheets()
        sheet.values().append(
            spreadsheetId=SHEET_ID,
            range='Form Responses 1',
            valueInputOption='RAW',
            body={'values': [values]}
        ).execute()
        session.pop('authenticated', None)
        flash('Fundraiser updated successfully!')
        return redirect(url_for('home'))
    show_modal = not session.get('authenticated', False)
    return render_template('submit_fundraiser.html', show_modal=show_modal)

@app.route('/get-fundraisers', methods=['GET'])
def get_fundraisers():
    fundraisers = get_latest_fundraisers(limit=None)  # Fetch all fundraisers
    print(f"Fundraisers fetched: {fundraisers}")
    return jsonify([{'id': i + 1, 'name': f['name'] or 'Unnamed Fundraiser'} for i, f in enumerate(fundraisers)])

class RestrictMethodsMiddleware:
    def __init__(self, app):
        self.app = app

    def __call__(self, environ, start_response):
        if environ['REQUEST_METHOD'] == 'OPTIONS':
            start_response('405 Method Not Allowed', [('Content-Type', 'text/plain')])
            return [b'Method Not Allowed']
        return self.app(environ, start_response)
    

app.wsgi_app = RestrictMethodsMiddleware(app.wsgi_app)

# Call it at the end of the file, after all models are defined
create_tables()


# if __name__ == '__main__':
#     with app.app_context():
#         db.create_all()
#     app.run(host='0.0.0.0', port=int(os.getenv('PORT', 5000)), debug=False)