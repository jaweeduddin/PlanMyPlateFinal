const ingredientsList = [

    "potato",
    "tomato",
    "onion",
    "carrot",
    "cabbage",
    "capsicum",
    "broccoli",
    "cauliflower",
    "spinach",
    "peas",
    "corn",
    "brinjal",
    "eggplant",
    "ladyfinger",
    "okra",
    "pumpkin",
    "bottle gourd",
    "radish",
    "beetroot",
    "sweet potato",
    "green beans",
    "mushroom",
    "lettuce",
    "cucumber",
    "zucchini",

    // Fruits
    "banana",
    "apple",
    "orange",
    "mango",
    "papaya",
    "watermelon",
    "melon",
    "grapes",
    "pineapple",
    "strawberry",
    "blueberry",
    "kiwi",
    "pear",
    "pomegranate",
    "avocado",
    "lemon",

    // Meats
    "chicken",
    "mutton",
    "beef",
    "fish",
    "prawns",
    "egg",
    "meat",
    "turkey",
    "sausage",

    // Dairy
    "milk",
    "cheese",
    "butter",
    "paneer",
    "curd",
    "yogurt",
    "cream",
    "ghee",

    // Grains
    "rice",
    "wheat",
    "flour",
    "oats",
    "bread",
    "pasta",
    "noodles",
    "quinoa",
    "cornflakes",

    // Pulses
    "dal",
    "lentils",
    "chickpeas",
    "rajma",
    "black beans",
    "soybeans",
    "peas",

    // Spices
    "salt",
    "sugar",
    "turmeric",
    "chili",
    "black pepper",
    "cumin",
    "coriander",
    "garam masala",
    "cardamom",
    "clove",
    "cinnamon",
    "mustard seeds",
    "paprika",
    "oregano",

    // Herbs
    "mint",
    "coriander leaves",
    "parsley",
    "basil",
    "methi",
    "curry leaves",

    // Oils & Sauces
    "oil",
    "olive oil",
    "soy sauce",
    "vinegar",
    "tomato sauce",
    "mayonnaise",
    "ketchup",
    "mustard sauce",

    // Nuts & Dry Fruits
    "almonds",
    "cashews",
    "walnuts",
    "raisins",
    "dates",
    "pistachios",

    // Misc
    "garlic",
    "ginger",
    "honey",
    "jam",
    "chocolate",
    "coffee",
    "tea",
    "coconut",
    "peanut butter"
];

function showSuggestions(textareaId, boxId) {

    const input =
        document.getElementById(textareaId);

    const box =
        document.getElementById(boxId);

    const words =
        input.value.toLowerCase().split(",");

    const value =
        words[words.length - 1].trim();

    box.innerHTML = "";
box.style.display = "none";
    if (value.length === 0) {

        return;
    }

    const filtered =
        ingredientsList.filter(item =>
            item.startsWith(value)
        );
if (filtered.length > 0) {

    box.style.display = "block";
}
    filtered.forEach(item => {

        const div =
            document.createElement("div");

        div.classList.add("suggestion-item");

        div.innerText = item;

        div.onclick = function() {

            words[words.length - 1] =
                " " + item;

            input.value =
                words.join(",");

            box.innerHTML = "";
            box.style.display = "none";
        };

        box.appendChild(div);
    });
}