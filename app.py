from flask import Flask, render_template, request, redirect, url_for, flash, session
import mysql.connector
from werkzeug.utils import secure_filename
import os



app = Flask(__name__)
app.secret_key = 'your_secret_key'
app.config['UPLOAD_FOLDER'] = 'static/uploads'  

ALLOWED_EXTENSIONS = {'jpg', 'jpeg', 'png', 'gif'} 

db_config = {
    "host": "localhost",
    "user": "root",
    "password": "Leader@123",
    "database": "RecipeHub"
}



@app.route('/', methods=['GET'])
def index():
    conn = mysql.connector.connect(**db_config)
    cursor = conn.cursor(dictionary=True)

    search_query = request.args.get('search')

    if search_query:
        query = """
            SELECT * FROM recipes 
            WHERE name LIKE %s OR ingredients LIKE %s 
            ORDER BY recipe_id DESC
        """
        cursor.execute(query, ('%' + search_query + '%', '%' + search_query + '%'))
    else:
        cursor.execute('SELECT * FROM recipes ORDER BY recipe_id DESC')

    recipes = cursor.fetchall()

    cursor.execute('SELECT * FROM recipes ORDER BY recipe_id DESC LIMIT 1')
    featured_recipe = cursor.fetchone()

    cursor.close()
    conn.close()

    categories = {
        'Breakfast': ['sandwich', 'pancake', 'omelette', 'cereal', 'toast', 'smoothie', 'waffle'],
        'Lunch': ['salad', 'wrap', 'burger', 'bowl', 'soup'],
        'Dinner': ['pizza','pasta', 'steak', 'curry', 'roast', 'grilled','spaghetti'],
        'Desserts': ['pudding', 'brownies', 'cookie', 'muffin', 'cake', 'icecream', 'gulab jamun']
    }

    categorized_recipes = {'Breakfast': [], 'Lunch': [], 'Dinner': [], 'Desserts': []}
    for recipe in recipes:
        assigned = False
        for category, keywords in categories.items():
            if any(keyword.lower() in recipe['name'].lower() or keyword.lower() in recipe['ingredients'].lower() for keyword in keywords):
                categorized_recipes[category].append(recipe)
                assigned = True
                break
        if not assigned:
            categorized_recipes['Lunch'].append(recipe)  

    return render_template('index.html', featured_recipe=featured_recipe, categorized_recipes=categorized_recipes, search_query=search_query)




@app.route('/recipe/<int:recipe_id>')
def recipe_details(recipe_id):
    conn = mysql.connector.connect(**db_config)
    cursor = conn.cursor(dictionary=True)

 
    cursor.execute('SELECT * FROM recipes WHERE recipe_id = %s', (recipe_id,))
    recipe = cursor.fetchone()

    image_path = os.path.join(app.config['UPLOAD_FOLDER'], f"{recipe_id}.jpg")
    image_exists = os.path.exists(image_path)

    cursor.execute("""
        SELECT comments.comment, comments.date_posted, users.user_name 
        FROM comments 
        JOIN users ON comments.user_id = users.user_id 
        WHERE comments.recipe_id = %s
    """, (recipe_id,))
    comments = cursor.fetchall()

    for comment in comments:
        if comment['date_posted']:
            comment['date_posted'] = comment['date_posted'].strftime('%B %d, %Y')
        else:
            comment['date_posted'] = "Unknown Date"

    cursor.close()
    conn.close()
    
    return render_template('recipe_details.html', recipe=recipe, comments=comments, image_exists=image_exists, image_filename=f"{recipe_id}.jpg")

 

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/submit_recipe', methods=['GET', 'POST'])
def submit_recipe():
    if 'loggedin' not in session:
        flash('You need to login to submit a recipe.', 'danger')
        return redirect(url_for('login'))

    if request.method == 'POST':
        name = request.form['name']
        ingredients = request.form['ingredients']
        instructions = request.form['instructions']
        cooking_time_input = request.form['cooking_time']
        serving_size = request.form['serving_size']
        user_id = session['user_id']
        file = request.files.get('image')

       
        try:
            cooking_time_minutes = int(cooking_time_input)
            hours = cooking_time_minutes // 60
            minutes = cooking_time_minutes % 60
            cooking_time = f"{hours:02}:{minutes:02}:00"
        except ValueError:
            flash("Please enter a valid number for cooking time in minutes.", 'danger')
            return redirect(url_for('submit_recipe'))

        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor()

      
        cursor.execute(
            'INSERT INTO recipes (name, ingredients, instructions, cooking_time, serving_size, user_id) VALUES (%s, %s, %s, %s, %s, %s)',
            (name, ingredients, instructions, cooking_time, serving_size, user_id)
        )
        recipe_id = cursor.lastrowid  
        conn.commit()

     
        if file and allowed_file(file.filename):
            filename = secure_filename(f"{recipe_id}.jpg") 
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(file_path)
            print(f"Image saved at: {file_path}")  
        cursor.close()
        conn.close()

        flash('Recipe submitted successfully!', 'success')
        return redirect(url_for('index'))

    return render_template('submit_recipe.html')



@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        user_name = request.form['username']
        email = request.form['email']
        password = request.form['password']

        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor()
        cursor.execute(
            'INSERT INTO users (user_name, email, password) VALUES (%s, %s, %s)',
            (user_name, email, password)  
        )
        conn.commit()
        cursor.close()
        conn.close()

        flash('Registration successful! Please login.', 'success')
        return redirect(url_for('login'))

    return render_template('register.html')
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']

        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor(dictionary=True)
        cursor.execute('SELECT * FROM users WHERE email = %s', (email,))
        user = cursor.fetchone()
        cursor.close()
        conn.close()

        if not user or user['password'] != password:  
            flash('Invalid email or password.', 'danger')  
        else:
            session['loggedin'] = True
            session['user_id'] = user['user_id']
            session['user_name'] = user['user_name']
            flash('Login successful!', 'success')
            return redirect(url_for('index'))

    return render_template('login.html')



@app.route('/logout')
def logout():
    session.pop('loggedin', None)
    session.pop('user_id', None)
    session.pop('user_name', None)
    flash('You have been logged out.', 'success')
    return redirect(url_for('index'))

@app.route('/comment/<int:recipe_id>', methods=['POST'])
def comment(recipe_id):
    if 'loggedin' not in session:
        flash('You need to login to leave a comment.', 'danger')
        return redirect(url_for('login'))

    comment_text = request.form['comment']
    user_id = session['user_id']

    conn = mysql.connector.connect(**db_config)
    cursor = conn.cursor()
    cursor.execute(
        'INSERT INTO comments (recipe_id, user_id, comment) VALUES (%s, %s, %s)',
        (recipe_id, user_id, comment_text)
    )
    conn.commit()
    cursor.close()
    conn.close()

    flash('Comment added successfully!', 'success')
    return redirect(url_for('recipe_details', recipe_id=recipe_id))

if __name__ == '__main__':
    app.run(debug=True)


