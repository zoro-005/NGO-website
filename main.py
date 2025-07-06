from flask import Flask, render_template, request, redirect, flash, url_for, jsonify, session
from flask_sqlalchemy import SQLAlchemy
from flask_mail import Mail, Message
from datetime import datetime
from dotenv import load_dotenv
from werkzeug.utils import secure_filename
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
import razorpay
import os
import requests
import logging

load_dotenv()
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.secret_key = 'supersecretkey'
app.config['SESSION_TYPE'] = 'filesystem'
from flask_session import Session
Session(app)

# Database configuration
app.config['SQLALCHEMY_DATABASE_URI'] = "mysql+pymysql://root:@localhost/ngo"
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
creds = Credentials.from_service_account_file('credentials.json', scopes=SCOPES)
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
def contact():
    if request.method == "POST":
        name = request.form.get('name')
        email = request.form.get('email')
        subject = request.form.get('subject')
        message = request.form.get('message')
        entry = Contact(name=name, email=email, subject=subject, message=message, date=datetime.now())
        db.session.add(entry)
        db.session.commit()
        flash('Message sent successfully!')
        return redirect(url_for('contact', success_message=True))
    success_message = request.args.get('success_message')
    return render_template('contact.html', success_message=success_message)

@app.route('/donate')
def donate():
    donors = Donation.query.order_by(Donation.date.desc()).limit(4).all()
    return render_template('donate.html', donors=donors, key_id=os.getenv("RAZORPAY_KEY_ID"), paypal_client_id=os.getenv("PAYPAL_CLIENT_ID"))

@app.route('/join_us', methods=["GET", "POST"])
def join_us():
    if request.method == "POST":
        name = request.form.get('name')
        email = request.form.get('email')
        phone = request.form.get('phone')
        reason = request.form.get('reason')
        entry = Volunteer(name=name, email=email, phone=phone, reason=reason, date=datetime.now())
        db.session.add(entry)
        db.session.commit()
        flash('Thank you for signing up as a volunteer!')
        return redirect(url_for('join_us', success_message=True))
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
    donor_name = data.get('donor-name')
    donor_email = data.get('donor-email')
    amount = int(float(data.get('custom-amount')) * 100)

    order_data = {
        "amount": amount,
        "currency": "INR",
        "receipt": f"donation_{donor_name}",
        "notes": {
            "name": donor_name,
            "email": donor_email
        }
    }
    try:
        order = razorpay_client.order.create(data=order_data)
        return jsonify({"order_id": order['id']})
    except Exception as e:
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
            print(f"Email sent successfully to {notes.get('email')} at {datetime.now()}")
        except Exception as e:
            print(f"Failed to send email: {str(e)}")

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
            print(f"Error Response: {response.status_code} - {response.text}")
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
    logger.debug(f"Received data: {data}")
    donor_name = data.get('donor-name')
    donor_email = data.get('donor-email')
    amount = float(data.get('amount', 0))

    if not donor_name or not donor_email or amount <= 0:
        logger.error(f"Invalid input: name={donor_name}, email={donor_email}, amount={amount}")
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
    logger.debug(f"Received data for capture: {data}")

    try:
        capture = paypal_client.capture_order(order_id)
        logger.debug(f"Capture response: {capture}")
        
        purchase_unit = capture['purchase_units'][0]
        captures = purchase_unit.get('payments', {}).get('captures', [])
        if not captures:
            raise ValueError("No capture data found in response")
        
        capture_data = captures[0]
        amount = float(capture_data['amount']['value'])
        payment_id = capture_data['id']
        donor_name = session.get('donor_name', purchase_unit.get('custom_id', 'Anonymous'))  # Use session name
        donor_email = session.get('donor_email') or ''  # Use session email

        logger.debug(f"Using donor_name: {donor_name} from session: {session.get('donor_name')} or custom_id: {purchase_unit.get('custom_id')}")
        logger.debug(f"Using donor_email: {donor_email} from session: {session.get('donor_email')}")

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
            logger.debug(f"Email message created: subject={msg.subject}, recipients={msg.recipients}, html={msg.html}")
            if donor_email:
                with app.app_context():
                    mail.send(msg)
                logger.info(f"Email sent successfully to {donor_email} at {datetime.now()}")
            else:
                logger.warning("No valid donor email provided, skipping email")
        except Exception as e:
            logger.error(f"Failed to send email: {str(e)}", exc_info=True)

        session['just_donated'] = True
        session['donor_name'] = donor_name  # Update session name
        return jsonify({'status': 'success', 'redirect_url': url_for('donation_success', _external=True)})
    except requests.exceptions.RequestException as e:
        logger.error(f"Payment capture failed: {str(e)}")
        return jsonify({'status': 'failure', 'error': str(e)}), 400
    except (KeyError, ValueError) as e:
        logger.error(f"Invalid capture response: {str(e)}")
        return jsonify({'status': 'failure', 'error': f"Invalid response data: {str(e)}"}), 400
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
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
    return render_template('success_story.html', story_id=story_id)

@app.route('/success/all')
def success_all():
    return render_template('success_all.html')

@app.route('/submit-fundraiser', methods=['GET', 'POST'])
def submit_fundraiser():
    client_key = os.getenv('CLIENT_KEY')
    if request.method == 'POST':
        if 'client_key' in request.form:
            provided_key = request.form.get('client_key')
            if provided_key != client_key:
                flash('Invalid client key. Access denied.')
                return render_template('submit_fundraiser.html', show_modal=True)
            session['authenticated'] = True
            return redirect(url_for('submit_fundraiser'))
        else:
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

@app.route('/authenticate-client', methods=['POST'])
def authenticate_client():
    client_key = os.getenv('CLIENT_KEY')
    provided_key = request.form.get('client_key')
    if provided_key == client_key:
        session['authenticated'] = True
        return redirect(url_for('submit_fundraiser'))
    flash('Invalid client key. Access denied.')
    return redirect(url_for('home'))

@app.route('/get-fundraisers', methods=['GET'])
def get_fundraisers():
    fundraisers = get_latest_fundraisers(limit=None)  # Fetch all fundraisers
    print(f"Fundraisers fetched: {fundraisers}")
    return jsonify([{'id': i + 1, 'name': f['name'] or 'Unnamed Fundraiser'} for i, f in enumerate(fundraisers)])

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)