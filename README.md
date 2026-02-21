# Recipe Generator & Meal Planner

A web-based application that generates recipes based on ingredients and dietary preferences, creates personalized meal plans, and calculates nutrition information.

## Features

- **AI-Powered Recipe Generation**: Generate recipes from available ingredients using Together.ai
- **Dietary Preferences**: Support for vegetarian, vegan, gluten-free, low-carb, keto, and dairy-free options
- **Meal Planning**: Create weekly meal plans with customizable days and meals per day
- **Nutrition Calculation**: Automatic nutrition estimation using USDA and Edamam APIs (with fallback to local database)
- **Recipe Saving & Favorites**: Save and favorite your favorite recipes for easy access
- **Shopping List Generation**: Automatically generate shopping lists from recipes or meal plans
- **Recipe Scaling**: Scale recipes to different serving sizes with automatic ingredient and nutrition adjustments
- **AI Image Generation**: Generate beautiful images for recipes using OpenAI DALL-E
- **PDF Export**: Export meal plans as PDF documents for printing or sharing
- **Beautiful UI**: Modern, responsive interface with recipe cards and calendar-style meal planner

## Quick Start

### 1. Install Dependencies
```bash
cd server
pip install -r requirements.txt
```

### 2. Set Up API Keys
Create a `.env` file in the `server/` directory with the following variables:

**Required:**
```
TOGETHER_AI_API_KEY=your-together-ai-api-key-here
```

**Optional (for enhanced features):**
```
# For AI-generated recipe images
OPENAI_API_KEY=your-openai-api-key-here

# For enhanced nutrition data (Edamam)
EDAMAM_APP_ID=your-edamam-app-id
EDAMAM_APP_KEY=your-edamam-app-key

# For enhanced nutrition data (USDA)
USDA_API_KEY=your-usda-api-key-here
```

**Note:** The app will work with just the Together.ai API key. Other APIs are optional and provide enhanced features.

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

### Recipe Endpoints
- `POST /api/generate-recipe` - Generate a recipe
- `GET /api/recipe/{recipe_id}` - Get a specific recipe
- `GET /api/recipes` - List all stored recipes
- `POST /api/recipe/{recipe_id}/save` - Save a recipe
- `POST /api/recipe/{recipe_id}/favorite` - Toggle favorite status
- `GET /api/recipe/{recipe_id}/image` - Generate/get recipe image
- `POST /api/scale-recipe` - Scale a recipe to different servings

### Meal Plan Endpoints
- `POST /api/generate-meal-plan` - Generate a meal plan
- `GET /api/meal-plan/{plan_id}` - Get a specific meal plan
- `GET /api/meal-plan/{plan_id}/export-pdf` - Export meal plan as PDF

### Other Endpoints
- `GET /api/favorites` - Get all favorite recipes
- `POST /api/shopping-list` - Generate shopping list from recipes or meal plan

## Technologies

- **Backend**: FastAPI, Python
- **AI**: Together.ai (LLM), OpenAI DALL-E (image generation)
- **Frontend**: HTML, CSS, JavaScript
- **Nutrition APIs**: USDA FoodData Central, Edamam Nutrition API
- **PDF Generation**: ReportLab
- **Storage**: In-memory (can be extended to use a database)

## New Features Usage

### Recipe Favorites
- Click the "Favorite" button on any recipe to add it to your favorites
- Access all favorites from the "Favorites" tab
- Click "Unfavorite" to remove from favorites

### Recipe Scaling
- Use the "Scale to servings" input on any recipe
- Click "Scale Recipe" to automatically adjust all ingredients and nutrition values

### Shopping List
- Go to the "Shopping List" tab
- Select one or more recipes from the dropdown
- Click "Generate Shopping List" to see all ingredients needed
- You can also generate shopping lists from meal plans

### Recipe Images
- Recipe images are automatically generated when creating recipes (if OpenAI API key is set)
- Click "Generate Image" on any recipe to create a new image

### PDF Export
- After generating a meal plan, click "Export PDF" to download a formatted PDF
- The PDF includes all days, meals, and nutrition information
