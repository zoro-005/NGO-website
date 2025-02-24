from flask import Flask, render_template, request, redirect, flash, url_for
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

app = Flask(__name__)
app.secret_key = 'supersecretkey'

app.config['SQLALCHEMY_DATABASE_URI'] = "mysql+pymysql://root:@localhost/ngo"
db = SQLAlchemy(app)

class Contact(db.Model):
    sno = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(30), nullable=False)
    email = db.Column(db.String(50), nullable=False)
    subject = db.Column(db.String(40), nullable=True)
    date = db.Column(db.String(20), nullable=False)
    message = db.Column(db.String(200), nullable=False)

class Volunteer(db.Model):
    sno = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(30), nullable=False)
    email = db.Column(db.String(50), nullable=False)
    phone = db.Column(db.String(40), nullable=False)
    date = db.Column(db.String(20), nullable=False)
    reason = db.Column(db.String(200), nullable=False)

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

@app.route('/blog')
def blog():
    return render_template('blog.html')


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
    return render_template('donate.html')
@app.route('/join_us',methods=["GET","POST"])
def join_us():
    if request.method=="POST":
        name=request.form.get('name')
        email=request.form.get('email')
        phone=request.form.get('phone')
        reason=request.form.get('reason')
        entry=Volunteer(name=name,email=email,phone=phone,reason=reason,date=datetime.now())
        db.session.add(entry)
        db.session.commit()
        return redirect('/how-it-works')
    return render_template('how-it-works.html')


if __name__ == '__main__':
    app.run(debug=True)
