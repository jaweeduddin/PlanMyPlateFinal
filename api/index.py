from flask import Flask, render_template, request, redirect, session
from groq import Groq
from flask_sqlalchemy import SQLAlchemy
import os

app = Flask(__name__, template_folder="../templates", static_folder="../static")
app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("DATABASE_URL")
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.secret_key = "planmyplate_secret"

db = SQLAlchemy(app)


# ---------------- MODELS ---------------- #

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100))
    email = db.Column(db.String(100), unique=True)
    password = db.Column(db.String(100))


class Recipe(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer)
    title = db.Column(db.String(200))
    ingredients = db.Column(db.Text)
    instructions = db.Column(db.Text)


class MealPlan(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer)
    day = db.Column(db.String(50))
    recipe_id = db.Column(db.Integer)


with app.app_context():
    db.create_all()


client = Groq(api_key=os.environ.get("GROQ_API_KEY"))


# ---------------- HOME ---------------- #

@app.route("/")
def home():
    return render_template("index.html")


# ---------------- REGISTER ---------------- #

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form["username"]
        email = request.form["email"]
        password = request.form["password"]

        new_user = User(username=username, email=email, password=password)
        db.session.add(new_user)
        db.session.commit()

        return redirect("/login")

    return render_template("register.html")


# ---------------- LOGIN ---------------- #

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form["email"]
        password = request.form["password"]

        user = User.query.filter_by(email=email, password=password).first()

        if user:
            session["user_id"] = user.id
            session["username"] = user.username
            return redirect("/dashboard")

        return "Invalid Email or Password"

    return render_template("login.html")


# ---------------- DASHBOARD ---------------- #

@app.route("/dashboard")
def dashboard():
    if "user_id" not in session:
        return redirect("/login")

    return render_template("dashboard.html", username=session["username"])


# ---------------- ADD RECIPE ---------------- #

@app.route("/add_recipe", methods=["GET", "POST"])
def add_recipe():
    if "user_id" not in session:
        return redirect("/login")

    if request.method == "POST":
        title = request.form["title"]
        ingredients = request.form["ingredients"]
        instructions = request.form["instructions"]
        user_id = session["user_id"]

        new_recipe = Recipe(
            user_id=user_id,
            title=title,
            ingredients=ingredients,
            instructions=instructions
        )

        db.session.add(new_recipe)
        db.session.commit()

        return redirect("/dashboard")

    return render_template("add_recipe.html")


# ---------------- RECIPES (FIXED) ---------------- #

@app.route("/recipes")
def recipes():
    if "user_id" not in session:
        return redirect("/login")

    user_id = session["user_id"]
    all_recipes = Recipe.query.filter_by(user_id=user_id).all()

    # Convert database objects into explicit index-mapped lists for your HTML frontend
    formatted_recipes = []
    for r in all_recipes:
        formatted_recipes.append([
            r.id,           # recipe[0]
            r.user_id,      # recipe[1]
            r.title,        # recipe[2]
            r.ingredients,  # recipe[3]
            r.instructions  # recipe[4]
        ])

    return render_template("recipes.html", recipes=formatted_recipes)


# ---------------- DELETE RECIPE ---------------- #

@app.route("/delete_recipe/<int:id>")
def delete_recipe(id):
    if "user_id" not in session:
        return redirect("/login")

    recipe = Recipe.query.get(id)
    db.session.delete(recipe)
    db.session.commit()

    return redirect("/recipes")


# ---------------- MEAL PLANNER ---------------- #

@app.route("/meal_planner", methods=["GET", "POST"])
def meal_planner():
    if "user_id" not in session:
        return redirect("/login")

    user_id = session["user_id"]

    if request.method == "POST":
        day = request.form["day"]
        recipe_id = request.form.get("recipe_id")

        if not recipe_id:
            return "Please add recipes first"

        new_plan = MealPlan(user_id=user_id, day=day, recipe_id=recipe_id)
        db.session.add(new_plan)
        db.session.commit()

    recipes = Recipe.query.filter_by(user_id=user_id).all()
    plans = MealPlan.query.filter_by(user_id=user_id).all()

    return render_template("meal_planner.html", recipes=recipes, plans=plans)


# ---------------- DELETE MEAL ---------------- #

@app.route("/delete_meal/<int:id>")
def delete_meal(id):
    if "user_id" not in session:
        return redirect("/login")

    plan = MealPlan.query.get(id)
    db.session.delete(plan)
    db.session.commit()

    return redirect("/meal_planner")


# ---------------- NUTRITION PLANNER ---------------- #

@app.route("/nutrition_planner", methods=["GET", "POST"])
def nutrition_planner():
    if "user_id" not in session:
        return redirect("/login")

    result = ""
    bmi_message = ""
    ingredients = ""

    if request.method == "POST":
        age = request.form["age"]
        weight = request.form["weight"]
        height = request.form["height"]
        goal = request.form["goal"]
        ingredients = request.form["ingredients"]

        weight_float = float(weight)
        height_meter = float(height) / 100
        bmi = weight_float / (height_meter ** 2)

        if bmi < 18.5 and goal == "Weight Loss":
            bmi_message = (
                "⚠️ According to your BMI, you are underweight. "
                "Weight loss is not recommended. "
                "Please focus on healthy weight gain and balanced nutrition."
            )
        elif bmi > 25 and goal == "Weight Gain":
            bmi_message = (
                "⚠️ According to your BMI, you are overweight. "
                "Weight gain is not recommended. "
                "Please focus on healthy weight loss, exercise, and balanced nutrition."
            )
        elif 18.5 <= bmi <= 24.9:
            bmi_message = f"✅ Your BMI is healthy. You can safely follow your selected goal: {goal}"

        prompt = f"""
Create a personalized nutrition meal plan.

User Details:
- Age: {age}
- Weight: {weight} kg
- Height: {height} cm
- Goal: {goal}

Available Ingredients:
{ingredients}

Rules:
- Use only available ingredients
- Suggest healthy meals
- Mention estimated calories
- Mention protein amount
- Mention whether meal is healthy
- Keep language simple
- Use emojis
- Make response beautiful and clean

Format:

🍽️ Meal Name

🔥 Calories:
💪 Protein:
🥗 Benefits:

🥕 Ingredients:
• item 1
• item 2

👨‍🍳 Steps:
1. Step
2. Step

📅 Weekly Suggestion:
Monday:
Tuesday:
Wednesday:
"""

        try:
            chat_completion = client.chat.completions.create(
                messages=[{"role": "user", "content": prompt}],
                model="llama-3.1-8b-instant"
            )
            result = chat_completion.choices[0].message.content
        except Exception as e:
            result = str(e)

    return render_template(
        "nutrition_planner.html",
        result=result,
        bmi_message=bmi_message,
        ingredients=ingredients
    )


# ---------------- SAVE NUTRITION RECIPE ---------------- #

@app.route("/save_nutrition_recipe", methods=["POST"])
def save_nutrition_recipe():
    if "user_id" not in session:
        return redirect("/login")

    title = request.form["title"]
    ingredients = request.form["ingredients"]
    instructions = request.form["instructions"]
    user_id = session["user_id"]

    new_recipe = Recipe(
        user_id=user_id,
        title=title,
        ingredients=ingredients,
        instructions=instructions
    )

    db.session.add(new_recipe)
    db.session.commit()

    return redirect("/recipes")


# ---------------- AI GENERATOR ---------------- #

# ---------------- AI GENERATOR PROMPT UPDATE ---------------- #

@app.route("/ai_generator", methods=["GET", "POST"])
def ai_generator():
    if "user_id" not in session:
        return redirect("/login")

    generated_recipe = ""
    ingredients_payload = ""

    if request.method == "POST":
        ingredients_payload = request.form["ingredients"]
        
        # We rewrite the prompt to demand long, highly comprehensive instructions
        prompt = (
            f"Create an incredibly detailed, comprehensive, and large recipe using these primary ingredients: {ingredients_payload}.\n\n"
            f"Structure your response beautifully with Emojis and markdown headers:\n"
            f"1. A creative title for the recipe.\n"
            f"2. A thorough, expanded breakdown of the Ingredients (including prep states like chopping sizes).\n"
            f"3. High-quality, long, and deeply descriptive Step-by-Step cooking instructions. Explain the culinary techniques, what visual cues to look for (e.g., 'until golden brown and aromatic'), and precise management of heat levels.\n"
            f"4. Pro-chef tips for presentation, plating, and advanced flavor enhancements."
        )

        try:
            chat_completion = client.chat.completions.create(
                messages=[{"role": "user", "content": prompt}],
                model="llama-3.1-8b-instant"
            )
            generated_recipe = chat_completion.choices[0].message.content
        except Exception as e:
            generated_recipe = f"API Error context: {str(e)}"

    return render_template("ai_generator.html", recipe=generated_recipe, raw_ingredients=ingredients_payload)


# ---------------- RECIPE SEARCH ---------------- #

@app.route("/recipe_search")
def recipe_search():
    if "user_id" not in session:
        return redirect("/login")

    recipe_name = request.args.get("recipe")
    result = ""

    if recipe_name:
        prompt = f"""
Generate a beautiful recipe for:

{recipe_name}

Include:

🍽️ Recipe Name

🥕 Ingredients

👨‍🍳 Instructions

🔥 Calories

💪 Protein

⏰ Cooking Time

💡 Cooking Tips

Use beautiful formatting with emojis.
Keep language simple and clean.
"""

        try:
            chat_completion = client.chat.completions.create(
                messages=[{"role": "user", "content": prompt}],
                model="llama-3.1-8b-instant"
            )
            result = chat_completion.choices[0].message.content
        except Exception as e:
            result = str(e)

    return render_template("recipe_search.html", result=result, recipe_name=recipe_name)


# ---------------- SAVE AI RECIPE ---------------- #

# ---------------- SAVE AI RECIPE (DYNAMIC FIX) ---------------- #

@app.route("/save_ai_recipe", methods=["POST"])
def save_ai_recipe():
    if "user_id" not in session:
        return redirect("/login")

    title = request.form["title"]
    
    # Captures the actual text input values sent from your form fields
    ingredients = request.form.get("ingredients", "AI Generated Blend")
    instructions = request.form.get("instructions", "")

    # Saves the real API recipe text directly into the database
    new_recipe = Recipe(
        user_id=session["user_id"],
        title=title,
        ingredients=ingredients,
        instructions=instructions
    )

    db.session.add(new_recipe)
    db.session.commit()

    return redirect("/recipes")


# ---------------- GENERATE RECIPE DETAILS ---------------- #

@app.route("/generate_recipe_details", methods=["POST"])
def generate_recipe_details():
    recipe_name = request.form["recipe_name"]

    prompt = f"""
Generate recipe details for:

{recipe_name}

Return ONLY this format:

INGREDIENTS:
ingredient 1,
ingredient 2

INSTRUCTIONS:
1. Step one
2. Step two
"""

    try:
        chat_completion = client.chat.completions.create(
            messages=[{"role": "user", "content": prompt}],
            model="llama-3.1-8b-instant"
        )
        return chat_completion.choices[0].message.content
    except Exception as e:
        return str(e)


# ---------------- LOGOUT ---------------- #

@app.route("/logout")
def logout():
    session.clear()
    return redirect("/login")


# ---------------- RUN APP ---------------- #
# Note: Do not add if __name__ == "__main__" here.
# Vercel imports this file directly and needs
# the `app` variable accessible at module level.
