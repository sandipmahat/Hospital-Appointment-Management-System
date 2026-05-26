from flask import render_template,request,redirect,url_for,session,flash
from werkzeug.security import generate_password_hash, check_password_hash
from apps.database import get_connection

def login():
        return render_template('login.html')       

def home():
        return render_template('home.html')
def contact():
        return render_template('contact.html')

def register():
        if session.get("user_id"):
                return redirect(url_for('auth.dashboard'))
        
        if request.method == "POST":
                name = request.form.get("name", "").strip()
                email = request.form.get("email","").strip()
                password = request.form.get("password","")
                #Validation 
                if not name or not email or not password:
                        flash("All fields are required.", "error")
                        return render_template("register.html")
                if len(name) > 100:
                        flash("Name must be less than 100 characters.", "error")
                        return render_template("register.html")
                if len(email) > 100:
                        flash("Email must be less than 100 characters.", "error")
                        return render_template("register.html")
                if len(password) < 6:
                        flash("Password must be at least 6 characters long.", "error")
                        return render_template("register.html")
                conn = get_connection()
                cursor = conn.cursor()

                cursor.execute("SELECT * FROM users WHERE email = %s", (email,))
                existing_user = cursor.fetchone()

                if existing_user:
                        flash("Email already registered", "error")
                        return render_template("register.html")

                hashed_password = generate_password_hash(password)

                cursor.execute(
                        "INSERT INTO users (name, email, password) VALUES (%s, %s, %s)",
                        (name, email, hashed_password),
                )
                conn.commit()
                cursor.close()
                conn.close()

                flash("Registration successful! Please log in.", "success")
                return redirect(url_for('auth.login'))
        

        
        return render_template('register.html')
                
       
