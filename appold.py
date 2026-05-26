import os
import secrets
from flask import Flask, request, render_template, flash, redirect, url_for

# Configure app and secret key for session/flash support
app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY') or secrets.token_hex(32)

@app.route("/")
def home():
    return render_template('index.html')

@app.route("/about")
def about():
    return render_template('about.html',company_name="software company")

@app.route("/contact")
def contact():
    return render_template('contact.html')

@app.route('/services')
def services():
    return "Services Page"  

@app.route('/user/data/<int:user_id>')
def user_data(user_id):
    return f"User Data for ID: {user_id}"


@app.route('/search')
def search():
    query = request.args.get('q', '')
    return f"Search results for: {query}"


# @app.route('/login', methods=['GET', 'POST'])
# def login():
#     if request.method == 'POST':
#         print("---- Login Form Submission ----")
#         print(f"Form Data: {request.form}")
#         print(f"Email: {request.form.get('email')}")
#         print(f"Password: {request.form.get('password')}")
#         print(f"Remember Me: {request.form.get('remember')}")
#         print("---- End Submission ----")
#         return "Login submitted successfully!"

#     return render_template('login.html')

# user=[{'user':'admin','password':'password'}]
# @app.route("/login", methods=['GET','POST'])
# def login():
#     if request.method=="POST":
#         print(request.form)
#         print(request.form.get('username'))
#         print(request.form.get('password'))
#         username=request.form.get('username')
#         password=request.form.get('password')
#         for user in user:
#             if username==user.name and password==user.password:
#              render_template('index.html')
#     if request.method=="GET":
#         render_template('login.html')

users = [{'email': 'admin@example.com', 'password': 'password'}]

@app.route("/login", methods=['GET', 'POST'])
def login():
    if request.method == "POST":
        email = request.form.get('email')       # ✅ matches name="email"
        password = request.form.get('password') # ✅ matches name="password"

        for u in users:
            if email == u['email'] and password == u['password']:
                flash("Login successful!", "success")
                return redirect(url_for('home'))

        # No match — go back to login with error
        flash("Invalid email or password.", "danger")
        return redirect(url_for('login'))

    return render_template('login.html')

   

if __name__ == "__main__":
    app.run(debug=True)