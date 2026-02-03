# Recipe Generator & Meal Planner

A web-based application that generates recipes based on ingredients and dietary preferences, creates personalized meal plans, and calculates nutrition information.

## Features

- **AI-Powered Recipe Generation**: Generate recipes from available ingredients using Together.ai
- **Dietary Preferences**: Support for vegetarian, vegan, gluten-free, low-carb, keto, and dairy-free options
- **Meal Planning**: Create weekly meal plans with customizable days and meals per day
- **Nutrition Calculation**: Automatic nutrition estimation for recipes
- **Beautiful UI**: Modern, responsive interface with recipe cards and calendar-style meal planner

## Quick Start

### 1. Install Dependencies
```bash
cd server
pip install -r requirements.txt
```

### 2. Set Up API Key
The `.env` file is already configured with the API key. Or create your own:
```
TOGETHER_AI_API_KEY=your-api-key-here
```

### 3. Run the Server
```bash
cd server
python main.py
```

### 4. Open in Browser
Visit: **http://localhost:8001**

## Project Structure

```
recipe-meal-planner/
├── server/
│   ├── main.py              # FastAPI application
│   ├── requirements.txt     # Python dependencies
│   └── .env                 # Environment variables
├── client/
│   ├── index.html           # Main frontend page
│   └── static/
│       ├── css/
│       │   └── style.css    # Styling
│       └── js/
│           └── app.js       # Frontend logic
└── prompts/                 # Archived prompts
```

## Usage

### Generate a Recipe
1. Enter ingredients (comma-separated)
2. Select cuisine type and meal type (optional)
3. Choose dietary preferences
4. Set number of servings
5. Click "Generate Recipe"

### Create a Meal Plan
1. Set number of days (1-14)
2. Choose meals per day (3 or 4)
3. Optionally set target calories per day
4. Select dietary preferences
5. Click "Generate Meal Plan"

## API Endpoints

- `POST /api/generate-recipe` - Generate a recipe
- `POST /api/generate-meal-plan` - Generate a meal plan
- `GET /api/recipe/{recipe_id}` - Get a specific recipe
- `GET /api/meal-plan/{plan_id}` - Get a specific meal plan

## Technologies

- **Backend**: FastAPI, Python
- **AI**: Together.ai (LLM)
- **Frontend**: HTML, CSS, JavaScript
- **Nutrition**: Basic nutrition database (can be extended with external APIs)

## Future Enhancements

- Integration with nutrition APIs (USDA, Edamam)
- Recipe saving and favorites
- Shopping list generation
- Recipe scaling
- Image generation for recipes
- Export meal plans to PDF
