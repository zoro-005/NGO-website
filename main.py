from flask import Flask, render_template, request, redirect, flash, url_for, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_mail import Mail, Message
from datetime import datetime
from dotenv import load_dotenv
import razorpay
import os

load_dotenv()

app = Flask(__name__)
app.secret_key = 'supersecretkey'

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

# Routes
@app.route('/')
def home():
    return render_template('index.html')

@app.route('/about')
def about():
    return render_template('about.html')

@app.route('/how-it-works')
def how_it_works():
    return render_template('how-it-works.html')

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
    return render_template('donate.html', donors=donors, key_id=os.getenv("RAZORPAY_KEY_ID"))

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
        return redirect(url_for('join_us'))
    return render_template('how-it-works.html')

# Razorpay client
razorpay_client = razorpay.Client(auth=(os.getenv("RAZORPAY_KEY_ID"), os.getenv("RAZORPAY_KEY_SECRET")))

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
            order_id=order_id
        )
        db.session.add(donation)
        db.session.commit()

        # Send email receipt
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

        # Return success with redirect URL
        return jsonify({"status": "success", "redirect_url": url_for('donation_success', _external=True)})
    else:
        return jsonify({"status": "failed", "error": "Payment verification failed. Please try again."}), 400

@app.route('/donation-success')
def donation_success():
    # Get the latest donation (assuming it's the one just processed)
    latest_donation = Donation.query.order_by(Donation.date.desc()).first()
    if latest_donation:
        return render_template('success.html', 
                              name=latest_donation.name, 
                              amount=latest_donation.amount, 
                              email=latest_donation.email, 
                              date=latest_donation.date.strftime('%b %d, %Y'), 
                              payment_id=latest_donation.payment_id)
    return render_template('success.html', 
                          name='Donor', 
                          amount='XXX', 
                          email='your email', 
                          date=datetime.now().strftime('%b %d, %Y'), 
                          payment_id='XXX-XXX-XXX')

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)