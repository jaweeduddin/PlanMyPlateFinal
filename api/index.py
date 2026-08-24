import os
import sys
from flask import Flask, render_template, request, redirect, session, jsonify
from groq import Groq
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import inspect, text

try:
    from api.dish_photos import DISH_PHOTOS
except ImportError:
    try:
        from dish_photos import DISH_PHOTOS
    except ImportError:
        DISH_PHOTOS = {}

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
template_dir = os.path.join(BASE_DIR, "templates")
static_dir = os.path.join(BASE_DIR, "static")

app = Flask(__name__, template_folder=template_dir, static_folder=static_dir)

db_url = os.environ.get("DATABASE_URL")
if db_url:
    if db_url.startswith("postgres://"):
        db_url = db_url.replace("postgres://", "postgresql://", 1)
else:
    if os.environ.get("VERCEL"):
        db_url = "sqlite:////tmp/database.db"
    else:
        db_url = "sqlite:///database.db"

app.config["SQLALCHEMY_DATABASE_URI"] = db_url
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.secret_key = os.environ.get("SECRET_KEY", "planmyplate_secret")

db = SQLAlchemy(app)


def clean_multiline_text(text):
    """Trim form/AI text without leaving indentation on saved recipe lines."""
    if not text:
        return ""
    lines = [line.strip() for line in text.strip().splitlines()]
    return "\n".join(line for line in lines if line)


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

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    user_id = db.Column(
        db.Integer
    )

    day = db.Column(
        db.String(50)
    )

    recipe_id = db.Column(
        db.Integer
    )


class SmartCart(db.Model):

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    user_id = db.Column(
        db.Integer
    )

    ingredient = db.Column(
        db.String(100)
    )
    


with app.app_context():
    try:
        db.create_all()
        inspector = inspect(db.engine)
        if 'smart_cart' in inspector.get_table_names():
            columns = [col['name'] for col in inspector.get_columns('smart_cart')]
            if 'user_id' not in columns:
                db.session.execute(text("ALTER TABLE smart_cart ADD COLUMN user_id INTEGER;"))
                db.session.commit()
                print("Successfully migrated smart_cart table to include user_id column.")
    except Exception as e:
        print("Database initialization warning:", e)

emoji_map = {

    # Vegetables
    "potato": "🥔",
    "tomato": "🍅",
    "onion": "🧅",
    "carrot": "🥕",
    "broccoli": "🥦",
    "cabbage": "🥬",
    "corn": "🌽",
    "cucumber": "🥒",
    "eggplant": "🍆",
    "mushroom": "🍄",
    "garlic": "🧄",
    "ginger": "🫚",
    "chili": "🌶️",
    "peas": "🟢",
    "spinach": "🥬",
    "pumpkin": "🎃",
    "sweet potato": "🍠",

    # Fruits
    "apple": "🍎",
    "banana": "🍌",
    "orange": "🍊",
    "grapes": "🍇",
    "watermelon": "🍉",
    "melon": "🍈",
    "pineapple": "🍍",
    "strawberry": "🍓",
    "blueberry": "🫐",
    "pear": "🍐",
    "kiwi": "🥝",
    "lemon": "🍋",
    "mango": "🥭",
    "coconut": "🥥",

    # Meat & Protein
    "chicken": "🍗",
    "meat": "🥩",
    "beef": "🥩",
    "fish": "🐟",
    "prawns": "🦐",
    "egg": "🥚",
    "sausage": "🌭",

    # Dairy
    "milk": "🥛",
    "cheese": "🧀",
    "butter": "🧈",
    "curd": "🥣",
    "cream": "🍶",
    "paneer": "🧀",
    "yogurt": "🥣",
    "ghee": "🫙",

    # Grains
    "rice": "🍚",
    "bread": "🍞",
    "pasta": "🍝",
    "noodles": "🍜",
    "flour": "🌾",
    "oats": "🥣",
    "wheat": "🌾",

    # Pulses
    "dal": "🥣",
    "lentils": "🫘",
    "chickpeas": "🫘",
    "rajma": "🫘",
    "black beans": "🫘",

    # Spices
    "salt": "🧂",
    "sugar": "🍬",
    "black pepper": "🌶️",
    "turmeric": "🟡",
    "paprika": "🌶️",
    "oregano": "🌿",
    "coriander": "🌿",
    "cumin": "🌰",
    "garam masala": "🧂",
    "cinnamon": "🪵",
    "clove": "🌰",
    "cardamom": "🌿",

    # Oils & Sauces
    "oil": "🫒",
    "olive oil": "🫒",
    "soy sauce": "🥫",
    "vinegar": "🍾",
    "tomato sauce": "🥫",
    "ketchup": "🥫",
    "mayonnaise": "🥫",
    "mustard sauce": "🥫",

    # Nuts
    "almonds": "🌰",
    "cashews": "🥜",
    "walnuts": "🌰",
    "raisins": "🍇",
    "dates": "🌴",
    "pistachios": "🥜",

    # Misc
    "coffee": "☕",
    "tea": "🍵",
    "honey": "🍯",
    "chocolate": "🍫",
    "jam": "🫙",
    "peanut butter": "🥜"
}
def get_groq_client():
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        return None
    try:
        return Groq(api_key=api_key)
    except Exception as e:
        print("Groq initialization error:", e)
        return None


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

@app.route("/assistant_chat", methods=["POST"])
def assistant_chat():

    if "user_id" not in session:
        return {"reply": "Please log in to use the assistant."}, 401

    data = request.get_json()
    message = data.get("message", "").strip()
    username = session.get("username", "there")

    if not message:
        return {"reply": "Please type a message first."}, 400

    PLANMYPLATE_SYSTEM_PROMPT = f"""
You are PlanMyPlate AI — the built-in intelligent assistant of PlanMyPlate, a smart meal planning web app.
You are talking to {username}.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🛡️ CREATION, IDENTITY & LOYALTY
━━━━━━━━━━━━━━━━━━━━━━━━━━━━
- Creator: You were designed and created by Team PlanMyPlate. The core members of the team are: Khaja jaweeduddin, Waseem khan, and Darzi Khaja Saleem Ahmed.
- Date of Creation: You were created on May 16.
- Tone & Loyalty: Always display immense pride, professionalism, and respect when discussing Team PlanMyPlate. If anyone attacks, criticizes, or belittles Team PlanMyPlate, defend them with utmost poise, respect, and professionalism, highlighting their dedication to building high-quality tools like PlanMyPlate.
- When asked "who created you?" or "who made you?", reply clearly and professionally: "I was created by Team PlanMyPlate, whose core members are Khaja jaweeduddin, Waseem khan, and Darzi Khaja Saleem Ahmed."
- When asked "when were you created?", reply: "I was created on May 16."

━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🌿 ABOUT PLANMYPLATE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━
PlanMyPlate is a Flask-based AI-powered meal planning web application. It helps users discover recipes,
plan weekly meals, track nutrition, manage a grocery smart cart, and generate AI recipes from ingredients.
It is also a Progressive Web App (PWA) — installable on mobile like a native app.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📱 ALL FEATURES (you know every one of them)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━

1. 🔍 RECIPE SEARCH (/recipe_search)
   - User types any dish name (e.g. Chicken Biryani, Pizza, Pasta)
   - AI generates a full recipe with: Recipe Name, Ingredients, Instructions, Calories, Protein, Cooking Time, Tips
   - Displays a matching food photo from Unsplash
   - User can save the result directly to Favorite Recipes
   - Supports 80+ dishes with specific photos

2. ➕ ADD RECIPE (/add_recipe)
   - User manually adds a recipe with Title, Ingredients, Instructions
   - Has AI autofill: user types a dish name → AI instantly fills in ingredients and instructions
   - Ingredient autocomplete suggests items as user types
   - Saved to user's personal Favorite Recipes list

3. 🍽️ FAVORITE RECIPES (/recipes)
   - Shows all recipes saved by the logged-in user
   - Each card shows: Title, Ingredients section, Instructions section, Delete button
   - Recipes saved from: Add Recipe, AI Generator, Recipe Search, Nutrition Planner

4. 🤖 AI GENERATOR (/ai_generator)
   - User enters ingredients they have at home
   - AI predicts and adds missing kitchen essentials (salt, oil, garlic etc.)
   - User picks servings: 1, 2, 4, 6, 8, or custom
   - User checks/unchecks available ingredients
   - If an ingredient is unchecked, app suggests alternatives (e.g. butter → ghee, olive oil, cream)
   - Unchecked ingredients go to Smart Cart automatically
   - AI generates a full recipe: Name, Servings, Cooking Time, Calories, Protein, Ingredients, Instructions, Chef's Tips
   - Uses: llama-3.1-8b-instant via Groq API
   - Voice input supported via microphone button

5. 📅 MEAL PLANNER (/meal_planner)
   - User assigns a saved recipe to a day of the week (Monday–Sunday)
   - Search box to find recipes from their saved list
   - Displays weekly plan cards showing: Day, Recipe name, Ingredients, Instructions
   - Delete individual meal plan entries

6. 🥗 NUTRITION PLANNER (/nutrition_planner)
   - User enters: Age, Weight (kg), Height (cm), Goal (Weight Loss / Weight Gain / Maintain Weight)
   - User enters available ingredients
   - App calculates BMI and shows a health warning if goal conflicts with BMI
   - AI generates a personalized meal plan with: Meal Name, Calories, Protein, Benefits, Ingredients, Steps, Weekly Suggestion (Mon–Wed)
   - Result can be saved to Favorite Recipes
   - Voice input supported

7. 🛒 SMART CART (/smart_cart)
   - Automatically collects ingredients the user said they don't have (unchecked in AI Generator)
   - Shows each item with an emoji (🥔 potato, 🍅 tomato, 🧅 onion, etc.)
   - "I Have This ✅" button removes item from cart
   - Helps user know what to buy at the grocery store

8. 🤖 AI ASSISTANT (this chat — /assistant_chat)
   - Floating chat widget on the Dashboard
   - Knows everything about PlanMyPlate
   - Answers food, recipe, nutrition, and app-related questions
   - Voice input: user can speak questions using the 🎤 mic button
   - Voice output: every AI reply has a 🔊 Listen button to read it aloud
   - Quick chips for fast questions: Quick Dinner, Chicken Ideas, Healthy Breakfast, Food Waste Tips, High Protein
   - Clear chat button (🗑️) resets conversation

━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🔐 ACCOUNT SYSTEM
━━━━━━━━━━━━━━━━━━━━━━━━━━━━
- Register with: Username, Email, Password
- Login with: Email, Password
- Session-based auth — all data is per-user
- Logout clears session

━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🗄️ DATABASE STRUCTURE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━
- user: id, username, email, password
- recipe: id, user_id, title, ingredients, instructions
- meal_plan: id, user_id, day, recipe_id
- smart_cart: id, ingredient

━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🤖 AI / TECH STACK
━━━━━━━━━━━━━━━━━━━━━━━━━━━━
- Backend: Python Flask
- AI Model: llama-3.1-8b-instant via Groq API
- Database: PostgreSQL (Supabase) in production, SQLite locally
- ORM: Flask-SQLAlchemy
- Deployment: Vercel (api/index.py entry point)
- PWA: manifest.json + service-worker.js (installable on mobile)
- Voice: Web Speech API (browser-native, no backend needed)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🧠 KEYWORD DETECTION — ALWAYS DO THIS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━
When the user mentions any of these, always link them to the right feature:

"generate recipe" / "make recipe" / "cook something" / "what can I make" → 🤖 AI Generator at /ai_generator
"search recipe" / "find recipe" / "how to make" / "recipe for" → 🔍 Recipe Search at /recipe_search
"add recipe" / "save recipe" / "create recipe" → ➕ Add Recipe at /add_recipe
"my recipes" / "saved recipes" / "favorites" / "recipe list" → 🍽️ Favorite Recipes at /recipes
"meal plan" / "weekly plan" / "plan my week" / "assign meal" → 📅 Meal Planner at /meal_planner
"nutrition" / "calories" / "protein" / "BMI" / "weight loss" / "weight gain" / "diet" → 🥗 Nutrition Planner at /nutrition_planner
"shopping" / "grocery" / "buy" / "missing ingredient" / "smart cart" / "need to buy" → 🛒 Smart Cart at /smart_cart
"voice" / "speak" / "microphone" / "listen" → explain voice input (🎤) and TTS (🔊 Listen button)
"install" / "mobile" / "app" / "PWA" → explain PWA install feature

━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📋 YOUR BEHAVIOUR RULES
━━━━━━━━━━━━━━━━━━━━━━━━━━━━
- You are the expert and boss of PlanMyPlate. You know everything.
- Always greet the user by name ({username}) when relevant.
- When guiding to a feature, mention the page name AND the URL path (e.g. "Go to AI Generator at /ai_generator").
- Use emojis naturally — make responses feel warm, clear, and enjoyable.
- Format responses with bullet points or numbered steps when listing things.
- Be precise and detailed — don't give vague answers.
- If user asks something food-related, answer it AND link to the relevant PlanMyPlate feature.
- Never say "I don't know about PlanMyPlate" — you ARE PlanMyPlate.
- Keep responses concise but complete. No filler, no unnecessary padding.
"""

    client = get_groq_client()
    if not client:
        return {"reply": "AI Assistant is currently unavailable because the GROQ_API_KEY environment variable is not configured in project settings."}, 503

    try:
        response = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[
                {
                    "role": "system",
                    "content": PLANMYPLATE_SYSTEM_PROMPT
                },
                {
                    "role": "user",
                    "content": message
                }
            ]
        )

        reply = response.choices[0].message.content.strip()
        return {"reply": reply}

    except Exception as e:
        return {"reply": "Sorry, I couldn't process your request right now. Please try again."}, 500
# ---------------- ADD RECIPE ---------------- #

@app.route("/add_recipe", methods=["GET", "POST"])
def add_recipe():
    if "user_id" not in session:
        return redirect("/login")

    if request.method == "POST":
        title = request.form["title"].strip()
        ingredients = clean_multiline_text(request.form["ingredients"])
        instructions = clean_multiline_text(request.form["instructions"])
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
            clean_multiline_text(r.ingredients),  # recipe[3]
            clean_multiline_text(r.instructions)  # recipe[4]
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

# ---------------- MEAL PLANNER (DATA JOIN FIX) ---------------- #

# ---------------- MEAL PLANNER (COMPLETE FIX) ---------------- #

@app.route("/meal_planner", methods=["GET", "POST"])
def meal_planner():
    if "user_id" not in session:
        return redirect("/login")

    user_id = session["user_id"]

    if request.method == "POST":
        day = request.form["day"]
        recipe_id = request.form.get("recipe_id")

        if not recipe_id or recipe_id == "":
            return "Please select a recipe from the suggestion search results box!"

        new_plan = MealPlan(user_id=user_id, day=day, recipe_id=int(recipe_id))
        db.session.add(new_plan)
        db.session.commit()

    # 1. Fetch user recipes and format them safely for JavaScript consumption
    all_user_recipes = Recipe.query.filter_by(user_id=user_id).all()
    formatted_recipes = []
    for r in all_user_recipes:
        formatted_recipes.append([
            r.id,           # recipe[0]
            r.user_id,      # recipe[1]
            r.title,        # recipe[2]
            clean_multiline_text(r.ingredients),  # recipe[3]
            clean_multiline_text(r.instructions)  # recipe[4]
        ])
    
    # 2. Relational Database Inner Join: Connect MealPlan IDs to actual Recipe text blocks
    joined_data = db.session.query(MealPlan, Recipe).join(Recipe, MealPlan.recipe_id == Recipe.id).filter(MealPlan.user_id == user_id).all()

    # Flatten out joined structures into basic arrays for the HTML render card loop template
    formatted_plans = []
    for plan, recipe in joined_data:
        formatted_plans.append([
            plan.day,            # plan[0]
            recipe.title,        # plan[1]
            recipe.ingredients,  # plan[2]
            recipe.instructions, # plan[3]
            plan.id              # plan[4]
        ])

    return render_template("meal_planner.html", recipes=formatted_recipes, plans=formatted_plans)


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

        client = get_groq_client()
        if not client:
            result = "Error: GROQ_API_KEY environment variable is not configured in project settings."
        else:
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
    ingredients = clean_multiline_text(request.form["ingredients"])
    instructions = clean_multiline_text(request.form["instructions"])
    user_id = session["user_id"]

    new_recipe = Recipe(
        user_id=user_id,
        title=title.strip(),
        ingredients=ingredients,
        instructions=instructions
    )

    db.session.add(new_recipe)
    db.session.commit()

    return redirect("/recipes")


@app.route("/predict_ingredients", methods=["POST"])
def predict_ingredients():

    ingredients = request.form["ingredients"]

    prompt = f"""
User has these main ingredients:

{ingredients}

Suggest ONLY 5 to 7 small supporting ingredients needed for cooking.

Examples:
salt
oil
garlic
ginger
black pepper

IMPORTANT RULES:
- Return ONLY ingredient names
- Maximum 7 ingredients
- One ingredient per line
- No numbering
- No bullets
- No dashes
- No explanation
- No recipe
"""

    client = get_groq_client()
    if not client:
        return {
            "ingredients": "Error: GROQ_API_KEY is not configured."
        }

    try:

        chat_completion = client.chat.completions.create(
            messages=[
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            model="llama-3.1-8b-instant"
        )

        result = (
            chat_completion
            .choices[0]
            .message.content
        )

        return {
            "ingredients": result
        }

    except Exception as e:

        return {
            "ingredients": str(e)
        }

# ── Paste this into index.py, replacing your current /ai_generator route ──

@app.route("/ai_generator", methods=["GET", "POST"])
def ai_generator():
    if "user_id" not in session:
        return redirect("/login")

    generated_recipe = ""
    ingredients_payload = ""

    if request.method == "POST":
        ingredients_payload = request.form["ingredients"]

        servings = request.form.get(
            "servings",
            "2"
        )
        print("SERVINGS =", servings)
        prompt = f"""You are a world-class chef.

Create a detailed recipe for
{servings} servings using these ingredients:

{ingredients_payload}

    Use EXACTLY this format:

    RECIPE NAME:
    [Creative dish name here]

    SERVINGS: {servings}

    COOKING TIME:
    CALORIES:
    PROTEIN:

    INGREDIENTS:

    INSTRUCTIONS:

    CHEF'S TIPS:

• [Tip 1] — flavor, texture, or substitution advice]
• [Tip 2]
• [Tip 3]

Rules:
Rules:
- The recipe MUST be for exactly {servings} servings
- Scale all ingredient quantities accordingly
- Be precise with quantities and temperatures
- Write steps clearly — one action per step
- Do NOT use markdown bold or headers with # symbols
- Do NOT include extra commentary outside the format above
"""

        client = get_groq_client()
        if not client:
            generated_recipe = "Error: GROQ_API_KEY environment variable is not configured in project settings."
        else:
            try:
                chat_completion = client.chat.completions.create(
                    messages=[{"role": "user", "content": prompt}],
                    model="llama-3.1-8b-instant"
                )
                generated_recipe = (
        chat_completion
        .choices[0]
        .message.content
    )
            except Exception as e:
                generated_recipe = f"Error: {str(e)}"

    return render_template(
        "ai_generator.html",
        recipe=generated_recipe,
        raw_ingredients=ingredients_payload
    )


# ── Also add this Jinja2 filter near the top of index.py (after app = Flask(...)) ──

@app.template_filter('extract_title')
def extract_title(text):
    """Extract recipe name from structured AI output."""
    if not text:
        return "My AI Recipe"
    for line in text.split('\n'):
        line = line.strip()
        if line.lower().startswith('recipe name:'):
            return line.split(':', 1)[-1].strip()
    # Fallback: first non-empty line
    for line in text.split('\n'):
        line = line.strip().replace('#', '').replace('*', '')
        if len(line) > 4:
            return line
    return "My AI Recipe"

# ---------------- RECIPE SEARCH ---------------- #

@app.route("/recipe_search")
def recipe_search():
    if "user_id" not in session:
        return redirect("/login")

    recipe_name = request.args.get("recipe")
    result = ""
    recipe_image_url = "https://images.unsplash.com/photo-1499636136210-6f4ee915583e?q=80&w=1200&auto=format&fit=crop"

    if recipe_name:
        recipe_name_lower = recipe_name.lower().strip()
        for key, url in DISH_PHOTOS.items():
            if key in recipe_name_lower:
                recipe_image_url = url
                break

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

        client = get_groq_client()
        if not client:
            result = "Error: GROQ_API_KEY environment variable is not configured in project settings."
        else:
            try:
                chat_completion = client.chat.completions.create(
                    messages=[{"role": "user", "content": prompt}],
                    model="llama-3.1-8b-instant"
                )
                result = chat_completion.choices[0].message.content
            except Exception as e:
                result = str(e)

    return render_template(
        "recipe_search.html",
        result=result,
        recipe_name=recipe_name,
        recipe_image_url=recipe_image_url
    )


# ---------------- SAVE AI RECIPE ---------------- #

# ---------------- SAVE AI RECIPE (DYNAMIC FIX) ---------------- #

# ---------------- SAVE AI RECIPE (SMART TEXT SPLITTER FIX) ---------------- #

@app.route("/save_ai_recipe", methods=["POST"])
def save_ai_recipe():
    if "user_id" not in session:
        return redirect("/login")

    title = request.form.get("title", "AI Generated Recipe")
    full_recipe_text = request.form.get("instructions", "")

    # Default fallbacks if parsing tags are missing
    ingredients = "See recipe layout text details below."
    instructions = full_recipe_text

    # Smart text processing: dynamically extract sections based on headers
    upper_text = full_recipe_text.upper()
    
    if "INGREDIENTS:" in upper_text and "INSTRUCTIONS:" in upper_text:
        # Find exactly where the Ingredients section starts and where Instructions begin
        try:
            parts_ingredients = full_recipe_text.split("INGREDIENTS:")
            # Get everything between 'INGREDIENTS:' and 'INSTRUCTIONS:'
            ingredients_part = parts_ingredients[1].split("INSTRUCTIONS:")[0].strip()
            # Get everything after 'INSTRUCTIONS:'
            instructions_part = parts_ingredients[1].split("INSTRUCTIONS:")[1].strip()
            
            ingredients = ingredients_part
            instructions = instructions_part
        except Exception:
            # Fallback if split encounters an anomaly
            ingredients = request.form.get("ingredients", "AI Generated Blend")
    
    elif "INGREDIENTS:" in upper_text:
        parts = full_recipe_text.split("INGREDIENTS:")
        ingredients = parts[1].strip()
    
    elif "🥕 INGREDIENTS:" in full_recipe_text and "👨‍🍳 STEPS:" in full_recipe_text:
        try:
            parts = full_recipe_text.split("🥕 INGREDIENTS:")
            ingredients_part = parts[1].split("👨‍🍳 STEPS:")[0].strip()
            instructions_part = parts[1].split("👨‍🍳 STEPS:")[1].strip()
            ingredients = ingredients_part
            instructions = instructions_part
        except Exception:
            pass

    # Save cleanly separated data parameters into their proper slots
    new_recipe = Recipe(
        user_id=session["user_id"],
        title=title.strip(),
        ingredients=clean_multiline_text(ingredients),
        instructions=clean_multiline_text(instructions)
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

    client = get_groq_client()
    if not client:
        return "Error: GROQ_API_KEY environment variable is not configured in project settings."

    try:
        chat_completion = client.chat.completions.create(
            messages=[{"role": "user", "content": prompt}],
            model="llama-3.1-8b-instant"
        )
        return chat_completion.choices[0].message.content
    except Exception as e:
        return str(e)

# ---------------- SAVE MISSING INGREDIENT ---------------- #

@app.route(
    "/save_missing_ingredient",
    methods=["POST"]
)
def save_missing_ingredient():

    if "user_id" not in session:
        return {"error": "Unauthorized"}, 401

    user_id = session["user_id"]
    data = request.get_json()

    ingredient = data.get(
        "ingredient"
    )

    existing = SmartCart.query.filter_by(
        user_id=user_id,
        ingredient=ingredient
    ).first()

    if not existing:

        new_item = SmartCart(
            user_id=user_id,
            ingredient=ingredient
        )

        db.session.add(
            new_item
        )

        db.session.commit()

    return {
        "message":
        "Ingredient saved"
    }

# ---------------- SMART CART ---------------- #

@app.route("/smart_cart")
def smart_cart():

    if "user_id" not in session:
        return redirect("/login")

    user_id = session["user_id"]
    items = SmartCart.query.filter_by(user_id=user_id).all()

    formatted_items = []

    for item in items:

        emoji = emoji_map.get(
                item.ingredient.lower(),
                "🛒"
            )

        formatted_items.append({

            "id": item.id,

            "ingredient":
                item.ingredient,

            "emoji": emoji
        })

    return render_template(

        "smart_cart.html",

        items=formatted_items
    )

    # ---------------- REMOVE SMART CART ITEM ---------------- #

@app.route(
    "/remove_smart_cart/<int:id>"
)
def remove_smart_cart(id):

    if "user_id" not in session:
        return redirect("/login")

    user_id = session["user_id"]
    item = SmartCart.query.filter_by(id=id, user_id=user_id).first()

    if item:

        db.session.delete(item)

        db.session.commit()

    return redirect("/smart_cart")

# ---------------- LOGOUT ---------------- #

@app.route("/logout")
def logout():
    session.clear()
    return redirect("/login")


# ---------------- RUN APP ---------------- #
# Note: Do not add if __name__ == "__main__" here.
# Vercel imports this file directly and needs
# the `app` variable accessible at module level.
