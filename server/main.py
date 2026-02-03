"""
FastAPI server for Recipe Generator & Meal Planner
Generates recipes, creates meal plans, and calculates nutrition
"""

from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
import httpx
import json
import os
from datetime import datetime, timedelta
import uuid
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

app = FastAPI(title="Recipe Generator & Meal Planner", version="1.0.0")

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Get base directory (parent of server directory)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CLIENT_STATIC_DIR = os.path.join(BASE_DIR, "client", "static")
CLIENT_HTML_DIR = os.path.join(BASE_DIR, "client")

print(f"DEBUG: BASE_DIR: {BASE_DIR}")
print(f"DEBUG: CLIENT_STATIC_DIR: {CLIENT_STATIC_DIR}")
print(f"DEBUG: CLIENT_HTML_DIR: {CLIENT_HTML_DIR}")

# Configuration
TOGETHER_AI_API_KEY = os.getenv("TOGETHER_AI_API_KEY", "tgp_v1_pMCB-qUW938Aww7f-PUcrwi_u_qzgxmDBlfSCaCbwrw")
TOGETHER_AI_API_URL = "https://api.together.xyz/v1/chat/completions"
TOGETHER_AI_MODEL = "mistralai/Mixtral-8x7B-Instruct-v0.1"

# Storage (in production, use a database)
recipes_storage: Dict[str, Dict] = {}
meal_plans_storage: Dict[str, Dict] = {}

# Basic nutrition database (simplified - in production, use a proper API)
NUTRITION_DB = {
    "chicken": {"calories": 165, "protein": 31, "carbs": 0, "fat": 3.6},
    "beef": {"calories": 250, "protein": 26, "carbs": 0, "fat": 17},
    "pasta": {"calories": 131, "protein": 5, "carbs": 25, "fat": 1.1},
    "rice": {"calories": 130, "protein": 2.7, "carbs": 28, "fat": 0.3},
    "tomato": {"calories": 18, "protein": 0.9, "carbs": 3.9, "fat": 0.2},
    "cheese": {"calories": 113, "protein": 7, "carbs": 0.9, "fat": 9},
    "bread": {"calories": 265, "protein": 9, "carbs": 49, "fat": 3.2},
    "egg": {"calories": 155, "protein": 13, "carbs": 1.1, "fat": 11},
    "milk": {"calories": 42, "protein": 3.4, "carbs": 5, "fat": 1},
    "fish": {"calories": 206, "protein": 22, "carbs": 0, "fat": 12},
}


# Data Models
class RecipeRequest(BaseModel):
    ingredients: List[str]
    dietary_preferences: Optional[List[str]] = None
    cuisine_type: Optional[str] = None
    meal_type: Optional[str] = None  # breakfast, lunch, dinner, snack
    servings: int = 4


class MealPlanRequest(BaseModel):
    dietary_preferences: Optional[List[str]] = None
    days: int = 7
    meals_per_day: int = 3  # breakfast, lunch, dinner
    target_calories: Optional[int] = None


# Prompt Templates
RECIPE_GENERATION_TEMPLATE = """You are a professional chef and nutritionist creating a recipe.

User's Ingredients: {ingredients}
Dietary Preferences: {dietary_preferences}
Cuisine Type: {cuisine_type}
Meal Type: {meal_type}
Servings: {servings}

Create a detailed recipe using the provided ingredients. The recipe should:
- Use the provided ingredients as the main components
- Match the dietary preferences
- Be appropriate for the specified meal type
- Make {servings} servings

Return a JSON object with this exact structure:
{{
    "name": "Recipe name",
    "description": "Brief description of the recipe",
    "cuisine": "{cuisine_display}",
    "meal_type": "{meal_display}",
    "servings": {servings},
    "prep_time_minutes": <number>,
    "cook_time_minutes": <number>,
    "ingredients": [
        {{
            "name": "ingredient name",
            "amount": "quantity",
            "unit": "unit (cups, tbsp, etc.)"
        }}
    ],
    "instructions": [
        "Step 1",
        "Step 2",
        "Step 3"
    ],
    "nutrition_estimate": {{
        "calories_per_serving": <number>,
        "protein_grams": <number>,
        "carbs_grams": <number>,
        "fat_grams": <number>
    }},
    "tags": ["tag1", "tag2"]
}}

Return ONLY valid JSON, no additional text before or after.
"""

MEAL_PLAN_TEMPLATE = """You are a meal planning expert creating a {days}-day meal plan.

Dietary Preferences: {dietary_preferences}
Target Calories per day: {target_calories}
Meals per day: {meals_per_day}

Create a {days}-day meal plan with {meals_per_day} meals per day. For each meal, provide:
- Meal name/recipe name
- Brief description
- Meal type (breakfast, lunch, dinner, snack)
- Estimated calories

Return a JSON object with this exact structure:
{{
    "days": [
        {{
            "day": 1,
            "date": "YYYY-MM-DD",
            "meals": [
                {{
                    "meal_type": "breakfast",
                    "name": "Meal name",
                    "description": "Brief description",
                    "estimated_calories": <number>
                }},
                {{
                    "meal_type": "lunch",
                    "name": "Meal name",
                    "description": "Brief description",
                    "estimated_calories": <number>
                }},
                {{
                    "meal_type": "dinner",
                    "name": "Meal name",
                    "description": "Brief description",
                    "estimated_calories": <number>
                }}
            ]
        }}
    ],
    "total_days": {days}
}}

Return ONLY valid JSON, no additional text before or after.
"""


async def call_together_ai(prompt: str, system_prompt: str = "You are a helpful assistant.") -> str:
    """Call Together.ai API"""
    headers = {
        "Authorization": f"Bearer {TOGETHER_AI_API_KEY}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "model": TOGETHER_AI_MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.7,
        "max_tokens": 3000
    }
    
    try:
        print(f"DEBUG: Calling Together.ai API with model: {TOGETHER_AI_MODEL}")
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(TOGETHER_AI_API_URL, headers=headers, json=payload)
            print(f"DEBUG: API Response status: {response.status_code}")
            
            if response.status_code != 200:
                error_text = response.text
                print(f"DEBUG: API Error response: {error_text}")
                raise HTTPException(
                    status_code=response.status_code,
                    detail=f"Together.ai API error: {error_text}"
                )
            
            result = response.json()
            if "choices" not in result or len(result["choices"]) == 0:
                print(f"DEBUG: Unexpected API response format: {result}")
                raise HTTPException(
                    status_code=500,
                    detail="Unexpected response format from Together.ai API"
                )
            
            content = result["choices"][0]["message"]["content"]
            print(f"DEBUG: Received response from LLM ({len(content)} chars)")
            if not content or not content.strip():
                print("DEBUG: WARNING - Empty response from LLM")
                raise HTTPException(
                    status_code=500,
                    detail="Empty response from LLM. Please try again."
                )
            return content
    except httpx.TimeoutException:
        print("DEBUG: Request to Together.ai timed out")
        raise HTTPException(status_code=500, detail="Request to LLM timed out. Please try again.")
    except httpx.HTTPStatusError as e:
        print(f"DEBUG: HTTP error: {e.response.status_code} - {e.response.text}")
        raise HTTPException(
            status_code=500,
            detail=f"Together.ai API HTTP error: {e.response.status_code} - {e.response.text}"
        )
    except Exception as e:
        print(f"DEBUG: Unexpected error calling Together.ai: {type(e).__name__}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"LLM API error: {str(e)}")


def extract_json_from_response(text: str) -> Dict[str, Any]:
    """Extract JSON from LLM response"""
    text = text.strip()
    print(f"DEBUG: Extracting JSON from response (first 300 chars: {text[:300]})")
    
    if not text:
        raise ValueError("Empty response from LLM")
    
    # Remove markdown code blocks
    if text.startswith("```"):
        lines = text.split("\n")
        closing_idx = -1
        for i, line in enumerate(lines[1:], 1):
            if line.strip().startswith("```"):
                closing_idx = i
                break
        if closing_idx > 0:
            text = "\n".join(lines[1:closing_idx])
            print("DEBUG: Removed markdown code block markers")
        else:
            text = "\n".join(lines[1:])
    
    # Find JSON
    array_start = text.find("[")
    object_start = text.find("{")
    
    if array_start != -1 and (object_start == -1 or array_start < object_start):
        start_idx = array_start
        start_char = '['
        end_char = ']'
        print("DEBUG: Detected JSON array")
    elif object_start != -1:
        start_idx = object_start
        start_char = '{'
        end_char = '}'
        print("DEBUG: Detected JSON object")
    else:
        print(f"DEBUG: No JSON found. Full response: {text[:1000]}")
        raise ValueError(f"No JSON found in response. Response starts with: {text[:100]}")
    
    # Match brackets
    count = 0
    end_idx = start_idx
    in_string = False
    escape_next = False
    
    for i in range(start_idx, len(text)):
        char = text[i]
        if escape_next:
            escape_next = False
            continue
        if char == '\\':
            escape_next = True
            continue
        if char == '"' and not escape_next:
            in_string = not in_string
            continue
        if not in_string:
            if char == start_char:
                count += 1
            elif char == end_char:
                count -= 1
                if count == 0:
                    end_idx = i + 1
                    break
    
    if count != 0:
        print(f"DEBUG: Warning - bracket count mismatch ({count}). Using fallback.")
        end_idx = text.rfind(end_char) + 1
        if end_idx <= start_idx:
            raise ValueError(f"Could not find complete JSON. Unmatched brackets (count: {count})")
    
    json_str = text[start_idx:end_idx]
    print(f"DEBUG: Extracted JSON string ({len(json_str)} chars)")
    
    # Fix common issues
    json_str = json_str.replace('\\_', '_')
    import re
    json_str = re.sub(r',\s*}', '}', json_str)
    json_str = re.sub(r',\s*]', ']', json_str)
    
    try:
        parsed = json.loads(json_str)
        print(f"DEBUG: Successfully parsed JSON (type: {type(parsed).__name__})")
        return parsed
    except json.JSONDecodeError as e:
        print(f"DEBUG: JSON parse error: {e}")
        print(f"DEBUG: Problematic JSON (first 1000 chars): {json_str[:1000]}")
        raise ValueError(f"Invalid JSON in LLM response: {str(e)}")


def calculate_nutrition(recipe_data: Dict[str, Any]) -> Dict[str, float]:
    """Calculate nutrition from recipe ingredients"""
    total_calories = 0
    total_protein = 0
    total_carbs = 0
    total_fat = 0
    
    # Simple estimation based on ingredients
    for ingredient in recipe_data.get("ingredients", []):
        ing_name = ingredient.get("name", "").lower()
        amount_str = ingredient.get("amount", "1")
        
        # Try to extract number
        try:
            amount = float(amount_str.split()[0])
        except:
            amount = 1
        
        # Look up in nutrition DB
        for food, nutrition in NUTRITION_DB.items():
            if food in ing_name:
                # Rough estimation (assumes 100g servings in DB)
                total_calories += nutrition["calories"] * amount / 100
                total_protein += nutrition["protein"] * amount / 100
                total_carbs += nutrition["carbs"] * amount / 100
                total_fat += nutrition["fat"] * amount / 100
                break
    
    servings = recipe_data.get("servings", 4)
    return {
        "calories_per_serving": round(total_calories / servings, 1),
        "protein_grams": round(total_protein / servings, 1),
        "carbs_grams": round(total_carbs / servings, 1),
        "fat_grams": round(total_fat / servings, 1)
    }


@app.get("/", response_class=HTMLResponse)
async def root():
    """Serve the main frontend page"""
    html_path = os.path.join(CLIENT_HTML_DIR, "index.html")
    try:
        if not os.path.exists(html_path):
            return HTMLResponse(
                content=f"<h1>Frontend not found</h1><p>Path: {html_path}</p>", 
                status_code=404
            )
        with open(html_path, "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read())
    except Exception as e:
        return HTMLResponse(
            content=f"<h1>Error loading frontend</h1><p>Error: {str(e)}</p>", 
            status_code=500
        )


@app.post("/api/generate-recipe")
async def generate_recipe(request: RecipeRequest):
    """Generate a recipe based on ingredients and preferences"""
    try:
        # Prepare values for template (evaluate Python expressions first)
        cuisine_display = request.cuisine_type if request.cuisine_type else "Various"
        meal_display = request.meal_type if request.meal_type else "Any"
        dietary_display = ", ".join(request.dietary_preferences) if request.dietary_preferences else "None"
        ingredients_str = ", ".join(request.ingredients)
        
        print(f"DEBUG: Generating recipe - Ingredients: {ingredients_str}")
        print(f"DEBUG: Cuisine: {cuisine_display}, Meal: {meal_display}, Servings: {request.servings}")
        
        prompt = RECIPE_GENERATION_TEMPLATE.format(
            ingredients=ingredients_str,
            dietary_preferences=dietary_display,
            cuisine_type=request.cuisine_type or "Any",
            meal_type=request.meal_type or "Any",
            servings=request.servings,
            cuisine_display=cuisine_display,
            meal_display=meal_display
        )
        
        llm_response = await call_together_ai(
            prompt,
            system_prompt="You are a professional chef. Always return valid JSON."
        )
        
        print(f"DEBUG: Received LLM response ({len(llm_response)} chars)")
        print(f"DEBUG: Response preview: {llm_response[:500]}")
        
        try:
            recipe_data = extract_json_from_response(llm_response)
            print(f"DEBUG: Successfully parsed recipe data")
        except ValueError as e:
            print(f"DEBUG: JSON extraction failed: {e}")
            print(f"DEBUG: Full LLM response: {llm_response}")
            raise HTTPException(
                status_code=500,
                detail=f"Failed to parse LLM response as JSON: {str(e)}"
            )
        
        # Calculate nutrition if not provided or incomplete
        if ("nutrition_estimate" not in recipe_data or 
            not recipe_data.get("nutrition_estimate") or 
            not recipe_data["nutrition_estimate"].get("calories_per_serving")):
            print("DEBUG: Calculating nutrition from ingredients")
            calculated_nutrition = calculate_nutrition(recipe_data)
            if "nutrition_estimate" not in recipe_data:
                recipe_data["nutrition_estimate"] = {}
            recipe_data["nutrition_estimate"].update(calculated_nutrition)
        
        recipe_id = str(uuid.uuid4())
        recipe_data["recipe_id"] = recipe_id
        recipe_data["created_at"] = datetime.now().isoformat()
        
        recipes_storage[recipe_id] = recipe_data
        
        return recipe_data
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error generating recipe: {str(e)}")


@app.post("/api/generate-meal-plan")
async def generate_meal_plan(request: MealPlanRequest):
    """Generate a weekly meal plan"""
    try:
        start_date = datetime.now().date()
        
        prompt = MEAL_PLAN_TEMPLATE.format(
            days=request.days,
            dietary_preferences=", ".join(request.dietary_preferences) if request.dietary_preferences else "None",
            target_calories=request.target_calories or "No specific target",
            meals_per_day=request.meals_per_day
        )
        
        llm_response = await call_together_ai(
            prompt,
            system_prompt="You are a meal planning expert. Always return valid JSON."
        )
        
        plan_data = extract_json_from_response(llm_response)
        
        # Add dates to days
        for i, day in enumerate(plan_data.get("days", [])):
            day["date"] = (start_date + timedelta(days=i)).isoformat()
            day["day_number"] = i + 1
            
            # Calculate daily totals
            total_calories = sum(meal.get("estimated_calories", 0) for meal in day.get("meals", []))
            day["total_calories"] = total_calories
        
        plan_id = str(uuid.uuid4())
        plan_data["plan_id"] = plan_id
        plan_data["created_at"] = datetime.now().isoformat()
        plan_data["dietary_preferences"] = request.dietary_preferences
        plan_data["target_calories"] = request.target_calories
        
        meal_plans_storage[plan_id] = plan_data
        
        return plan_data
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error generating meal plan: {str(e)}")


@app.get("/api/recipe/{recipe_id}")
async def get_recipe(recipe_id: str):
    """Get a specific recipe"""
    if recipe_id not in recipes_storage:
        raise HTTPException(status_code=404, detail="Recipe not found")
    return recipes_storage[recipe_id]


@app.get("/api/meal-plan/{plan_id}")
async def get_meal_plan(plan_id: str):
    """Get a specific meal plan"""
    if plan_id not in meal_plans_storage:
        raise HTTPException(status_code=404, detail="Meal plan not found")
    return meal_plans_storage[plan_id]


@app.get("/api/recipes")
async def list_recipes():
    """List all stored recipes"""
    return {"recipes": list(recipes_storage.values())}


# Mount static files
app.mount("/static", StaticFiles(directory=CLIENT_STATIC_DIR), name="static")


if __name__ == "__main__":
    import uvicorn
    print("=" * 50)
    print("Starting Recipe Generator & Meal Planner Server...")
    print(f"Serving from: {BASE_DIR}")
    print("=" * 50)
    uvicorn.run(app, host="0.0.0.0", port=8001, log_level="info")
