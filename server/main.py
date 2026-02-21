"""
FastAPI server for Recipe Generator & Meal Planner
Generates recipes, creates meal plans, and calculates nutrition
"""

from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
import httpx
import json
import os
from datetime import datetime, timedelta
import uuid
from dotenv import load_dotenv
import requests
import urllib.parse
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, Image
from reportlab.lib import colors
from io import BytesIO
import base64
from PIL import Image as PILImage

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
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
EDAMAM_APP_ID = os.getenv("EDAMAM_APP_ID", "")
EDAMAM_APP_KEY = os.getenv("EDAMAM_APP_KEY", "")
USDA_API_KEY = os.getenv("USDA_API_KEY", "")

# Storage (in production, use a database)
recipes_storage: Dict[str, Dict] = {}
meal_plans_storage: Dict[str, Dict] = {}
favorites_storage: List[str] = []  # List of recipe IDs

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
    include_images: bool = False  # Disable images by default since they often don't match recipes


class ScaleRecipeRequest(BaseModel):
    recipe_id: str
    new_servings: int


class ShoppingListRequest(BaseModel):
    recipe_ids: Optional[List[str]] = None
    meal_plan_id: Optional[str] = None


# Prompt Templates
RECIPE_GENERATION_TEMPLATE = """You are a professional chef and nutritionist creating a recipe.

{dietary_restrictions}

User's Ingredients: {ingredients}
Dietary Preferences: {dietary_preferences}
Cuisine Type: {cuisine_type}
Meal Type: {meal_type}
Servings: {servings}

Create a detailed recipe using the provided ingredients. The recipe should:
- Use the provided ingredients as the main components
- STRICTLY follow all dietary preferences and restrictions listed above - THIS IS MANDATORY
- Be appropriate for the specified meal type
- Make {servings} servings

REMINDER: {dietary_restrictions_reminder}

IMPORTANT: Instructions must be DETAILED and SPECIFIC. Each instruction should:
- Include specific actions (e.g., "Drain the tuna", "Chop the lettuce into bite-sized pieces")
- Specify temperatures, times, or cooking methods when applicable (e.g., "Heat oil in a pan over medium-high heat", "Cook for 3-4 minutes until golden brown")
- Include preparation details (e.g., "Season with salt and pepper to taste", "Mix until well combined")
- Be clear and actionable (avoid vague phrases like "assemble" or "serve" without context)

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
        "Detailed step 1 with specific actions, temperatures, and times",
        "Detailed step 2 with specific actions, temperatures, and times",
        "Detailed step 3 with specific actions, temperatures, and times",
        "Continue with 4-6 detailed steps total"
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

MEAL_PLAN_TEMPLATE = """Create a {days}-day meal plan with EXACTLY {meals_per_day} meals per day.

Dietary: {dietary_preferences}
{dietary_restrictions}
{calorie_instruction}

CRITICAL: Each day MUST have EXACTLY {meals_per_day} meals. Include breakfast, lunch, dinner (and snack if {meals_per_day} = 4).
STRICTLY follow all dietary restrictions listed above. DO NOT include any prohibited ingredients.

IMPORTANT: Instructions must be DETAILED and SPECIFIC. Each instruction should:
- Include specific actions (e.g., "Drain the tuna in a colander", "Chop the lettuce into bite-sized pieces")
- Specify temperatures, times, or cooking methods when applicable (e.g., "Heat oil in a pan over medium-high heat", "Cook for 3-4 minutes until golden brown")
- Include preparation details (e.g., "Season with salt and pepper to taste", "Mix until well combined")
- Be clear and actionable (avoid vague phrases like "assemble" or "serve" without context)
- Provide 4-6 detailed steps per meal

Return ONLY this JSON (no markdown, no extra text):
{{
    "days": [
        {{
            "day": 1,
            "meals": [
                {{
                    "meal_type": "breakfast",
                    "name": "Oatmeal with Berries",
                    "description": "Healthy breakfast",
                    "estimated_calories": 250,
                    "prep_time_minutes": 5,
                    "cook_time_minutes": 10,
                    "servings": 1,
                    "ingredients": [
                        {{"name": "rolled oats", "amount": "1/2", "unit": "cup"}},
                        {{"name": "milk", "amount": "1", "unit": "cup"}},
                        {{"name": "berries", "amount": "1/2", "unit": "cup"}}
                    ],
                    "instructions": [
                        "Heat milk until simmering",
                        "Add oats and cook 5-7 minutes",
                        "Remove from heat and let stand 2 minutes",
                        "Top with berries and serve"
                    ]
                }},
                {{
                    "meal_type": "lunch",
                    "name": "Grilled Chicken Salad",
                    "description": "Healthy lunch",
                    "estimated_calories": 400,
                    "prep_time_minutes": 10,
                    "cook_time_minutes": 15,
                    "servings": 1,
                    "ingredients": [
                        {{"name": "chicken breast", "amount": "1", "unit": "piece"}},
                        {{"name": "lettuce", "amount": "2", "unit": "cups"}},
                        {{"name": "tomato", "amount": "1", "unit": "medium"}}
                    ],
                    "instructions": [
                        "Season the chicken breast with salt, pepper, and your preferred herbs. Preheat a grill or grill pan over medium-high heat. Grill the chicken for 6-7 minutes per side, or until the internal temperature reaches 165°F and the chicken is no longer pink",
                        "While the chicken is cooking, wash and dry the lettuce, then chop it into bite-sized pieces. Dice the tomato into small cubes",
                        "Let the grilled chicken rest for 2-3 minutes, then slice it into strips. Arrange the lettuce and tomato on a plate, top with the sliced chicken, and serve immediately"
                    ]
                }},
                {{
                    "meal_type": "dinner",
                    "name": "Pasta with Marinara",
                    "description": "Classic dinner",
                    "estimated_calories": 500,
                    "prep_time_minutes": 5,
                    "cook_time_minutes": 20,
                    "servings": 1,
                    "ingredients": [
                        {{"name": "pasta", "amount": "2", "unit": "oz"}},
                        {{"name": "marinara sauce", "amount": "1/2", "unit": "cup"}}
                    ],
                    "instructions": [
                        "Bring a large pot of salted water to a rolling boil over high heat. Add the pasta and cook according to package directions (usually 8-12 minutes) until al dente, stirring occasionally",
                        "While the pasta is cooking, pour the marinara sauce into a small saucepan and heat over medium heat, stirring occasionally, until it's warmed through (about 5 minutes)",
                        "Drain the cooked pasta, reserving 1-2 tablespoons of pasta water. Return the pasta to the pot, add the warm marinara sauce and reserved pasta water, and toss to combine. Serve immediately, optionally topped with grated cheese"
                    ]
                }}
            ]
        }}
    ]
}}

CRITICAL: Each day MUST have EXACTLY {meals_per_day} meals. Root key must be "days" (plural). Return ONLY valid JSON.
"""


async def call_together_ai(prompt: str, system_prompt: str = "You are a helpful assistant.", max_tokens: int = 3000) -> str:
    """Call Together.ai API with retry logic"""
    headers = {
        "Authorization": f"Bearer {TOGETHER_AI_API_KEY}",
        "Content-Type": "application/json"
    }
    
    # Cap max_tokens to prevent API errors (Together.ai has limits)
    max_tokens = min(max_tokens, 4000)  # Cap at 4000 to avoid API errors
    
    payload = {
        "model": TOGETHER_AI_MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.7,
        "max_tokens": max_tokens
    }
    
    # Validate API key
    if not TOGETHER_AI_API_KEY or TOGETHER_AI_API_KEY == "":
        raise HTTPException(status_code=500, detail="Together.ai API key is not configured")
    
    # Retry logic for transient errors
    max_retries = 2
    retry_delay = 2  # seconds
    
    for attempt in range(max_retries + 1):
            try:
                print(f"DEBUG: Calling Together.ai API (attempt {attempt + 1}/{max_retries + 1}) with model: {TOGETHER_AI_MODEL}, max_tokens: {max_tokens}")
                async with httpx.AsyncClient(timeout=120.0) as client:  # Increased timeout to 120 seconds
                    response = await client.post(TOGETHER_AI_API_URL, headers=headers, json=payload)
                    print(f"DEBUG: API Response status: {response.status_code}")
                    
                    if response.status_code != 200:
                        error_text = response.text
                        print(f"DEBUG: API Error response: {error_text}")
                        
                        # Try to parse error JSON
                        try:
                            error_json = response.json()
                            error_msg = error_json.get("error", {}).get("message", error_text[:200])
                            error_type = error_json.get("error", {}).get("type", "unknown")
                        except:
                            error_msg = error_text[:200]
                            error_type = "unknown"
                        
                        # If it's a server error and we have retries left, retry
                        if response.status_code == 500 and attempt < max_retries:
                            print(f"DEBUG: Server error, retrying in {retry_delay} seconds...")
                            import asyncio
                            await asyncio.sleep(retry_delay)
                            continue
                        
                        # Provide user-friendly error message
                        if response.status_code == 500:
                            raise HTTPException(
                                status_code=503,  # Service Unavailable
                                detail=f"Together.ai service is temporarily unavailable (server error). Please try again in a few moments. Error: {error_msg}"
                            )
                        else:
                            raise HTTPException(
                                status_code=500,
                                detail=f"Together.ai API error (status {response.status_code}): {error_msg}"
                            )
                    
                    # Success - parse response
                    try:
                        result = response.json()
                    except Exception as json_error:
                        print(f"DEBUG: Failed to parse JSON response: {json_error}")
                        print(f"DEBUG: Response text: {response.text[:500]}")
                        raise HTTPException(
                            status_code=500,
                            detail=f"Invalid JSON response from Together.ai API: {str(json_error)}"
                        )
                    
                    if "choices" not in result or len(result["choices"]) == 0:
                        print(f"DEBUG: Unexpected API response format: {result}")
                        raise HTTPException(
                            status_code=500,
                            detail="Unexpected response format from Together.ai API - no choices in response"
                        )
                    
                    content = result["choices"][0]["message"].get("content")
                    if content is None:
                        print("DEBUG: WARNING - Content is None in LLM response")
                        raise HTTPException(
                            status_code=500,
                            detail="Empty response from LLM (content is None). Please try again."
                        )
                    content = str(content)  # Ensure it's a string
                    print(f"DEBUG: Received response from LLM ({len(content)} chars)")
                    if not content.strip():
                        print("DEBUG: WARNING - Empty response from LLM")
                        raise HTTPException(
                            status_code=500,
                            detail="Empty response from LLM. Please try again."
                        )
                    return content
            except HTTPException:
                # Re-raise HTTPExceptions as-is
                raise
            except httpx.ConnectError as e:
                error_msg = str(e)
                print(f"DEBUG: Connection error to Together.ai API (attempt {attempt + 1}): {error_msg}")
                if attempt < max_retries:
                    print(f"DEBUG: Retrying in {retry_delay} seconds...")
                    import asyncio
                    await asyncio.sleep(retry_delay)
                    continue
                # After all retries failed
                if "getaddrinfo failed" in error_msg or "11001" in error_msg:
                    raise HTTPException(
                        status_code=503,
                        detail="Network error: Cannot connect to Together.ai API. Please check your internet connection and DNS settings. The API server may be temporarily unavailable."
                    )
                else:
                    raise HTTPException(
                        status_code=503,
                        detail=f"Connection error: Cannot reach Together.ai API after {max_retries + 1} attempts. {error_msg[:200]}"
                    )
            except httpx.TimeoutException as e:
                print(f"DEBUG: Timeout error (attempt {attempt + 1}): {e}")
                if attempt < max_retries:
                    print(f"DEBUG: Retrying in {retry_delay} seconds...")
                    import asyncio
                    await asyncio.sleep(retry_delay)
                    continue
                raise HTTPException(
                    status_code=504,
                    detail="Request to Together.ai API timed out. The service may be slow or unavailable. Please try again."
                )
            except httpx.HTTPStatusError as e:
                print(f"DEBUG: HTTP error: {e.response.status_code} - {e.response.text}")
                raise HTTPException(
                    status_code=500,
                    detail=f"Together.ai API HTTP error: {e.response.status_code} - {e.response.text[:500]}"
                )
            except Exception as e:
                error_type = type(e).__name__
                error_msg = str(e) if str(e) else repr(e)
                print(f"DEBUG: Unexpected error in API call (attempt {attempt + 1}): {error_type}: {error_msg}")
                if attempt < max_retries:
                    print(f"DEBUG: Retrying in {retry_delay} seconds...")
                    import asyncio
                    await asyncio.sleep(retry_delay)
                    continue
                # After all retries failed
                import traceback
                traceback_str = traceback.format_exc()
                print(f"DEBUG: Full traceback:\n{traceback_str}")
                
                # Check for common network errors
                if "getaddrinfo failed" in error_msg or "11001" in error_msg or "Name or service not known" in error_msg:
                    raise HTTPException(
                        status_code=503,
                        detail="Network error: Cannot resolve Together.ai API hostname. Please check your internet connection and DNS settings."
                    )
                elif "Connection refused" in error_msg or "Connection reset" in error_msg:
                    raise HTTPException(
                        status_code=503,
                        detail="Connection error: Cannot connect to Together.ai API. The service may be temporarily unavailable."
                    )
                else:
                    raise HTTPException(
                        status_code=500, 
                        detail=f"Unexpected error calling Together.ai API: {error_type}: {error_msg[:300]}" if error_msg else f"Unexpected error: {error_type}"
                    )
    
    # If we get here, all retries failed (shouldn't happen due to exceptions above)
    raise HTTPException(
        status_code=503,
        detail="Together.ai service is temporarily unavailable after multiple retry attempts. Please try again in a few moments."
    )


def extract_json_from_response(text: str) -> Dict[str, Any]:
    """Extract JSON from LLM response"""
    if text is None:
        raise ValueError("Response text is None")
    
    text = str(text).strip()  # Ensure it's a string and strip whitespace
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
    
    # Fix single quotes in JSON property names (common LLM error)
    # Convert 'key': to "key": but preserve single quotes in string values
    import re
    # Pattern: single quote, word/key, single quote, colon (property name)
    # We need to be careful not to replace single quotes inside string values
    # Strategy: Replace 'key': with "key": but only when it's a property name (before colon)
    def fix_single_quotes_in_property_names(json_str: str) -> str:
        """Convert single quotes to double quotes in JSON property names"""
        # Pattern to match property names with single quotes: 'key': or 'key' :
        # This matches: single quote, one or more word chars/underscores, single quote, optional whitespace, colon
        pattern = r"'([a-zA-Z_][a-zA-Z0-9_]*)'\s*:"
        def replace_func(match):
            key = match.group(1)
            return f'"{key}":'
        return re.sub(pattern, replace_func, json_str)
    
    # Apply the fix
    original_text = text
    text = fix_single_quotes_in_property_names(text)
    if text != original_text:
        print("DEBUG: Fixed single quotes in JSON property names")
    
    # PRIORITY: Try to find JSON object with "days" key first (for meal plans)
    import re
    days_match = None  # Initialize to None
    start_idx = None
    start_char = None
    end_char = None
    
    # CRITICAL: If "days" exists anywhere in the text, we MUST extract the root object containing it
    # This prevents extracting nested ingredient objects
    has_days_keyword = '"days"' in text or "'days'" in text
    
    # ALWAYS start from the first { if "days" exists - this should be the root object
    found_root = False
    if has_days_keyword:
        first_brace = text.find('{')
        if first_brace != -1:
            print(f"DEBUG: 'days' keyword found - extracting from first {{ at position {first_brace}...")
            # Extract the root object from first brace
            brace_count = 0
            in_str = False
            escape = False
            end_brace = -1
            
            for i in range(first_brace, len(text)):
                c = text[i]
                if escape:
                    escape = False
                    continue
                if c == '\\':
                    escape = True
                    continue
                if c == '"' and not escape:
                    in_str = not in_str
                    continue
                if not in_str:
                    if c == '{':
                        brace_count += 1
                    elif c == '}':
                        brace_count -= 1
                        if brace_count == 0:
                            end_brace = i + 1
                            break
            
            if end_brace > first_brace:
                try:
                    root_obj_text = text[first_brace:end_brace]
                    root_obj = json.loads(root_obj_text)
                    if isinstance(root_obj, dict) and "days" in root_obj:
                        print(f"DEBUG: SUCCESS - First {{ extraction found root object with 'days'!")
                        return root_obj
                    else:
                        print(f"DEBUG: First {{ object doesn't have 'days'. Keys: {list(root_obj.keys())[:10] if isinstance(root_obj, dict) else 'Not a dict'}")
                        # If first object doesn't have "days", it might be a nested object
                        # Continue to search for the actual root object
                except Exception as first_brace_error:
                    print(f"DEBUG: First {{ extraction failed: {first_brace_error}")
                    # Continue to other strategies
    
    if has_days_keyword and not found_root:
        print("DEBUG: 'days' keyword found in response - prioritizing root object extraction")
        
        # Strategy 1: Find the first { that contains "days" by searching backwards from "days"
        days_pos = text.find('"days"')
        if days_pos == -1:
            days_pos = text.find("'days'")
        
        if days_pos != -1:
            print(f"DEBUG: Found 'days' at position {days_pos}, searching backwards for root object")
            # Search backwards from "days" to find the outermost { that contains it
            # Start searching from a reasonable distance before "days"
            search_start = max(0, days_pos - 20000)  # Search up to 20000 chars before
            
            # Find all { positions before "days"
            brace_positions = []
            for i in range(search_start, days_pos):
                if text[i] == '{':
                    brace_positions.append(i)
            
            # Try each brace position from the last one (most likely to be root)
            # and extract the object to see if it contains "days"
            found_root = False
            best_candidate = None
            best_size = 0
            
            for brace_start in reversed(brace_positions):
                # Extract object from this brace
                brace_count = 0
                in_str = False
                escape = False
                end_brace = -1
                
                for i in range(brace_start, len(text)):
                    c = text[i]
                    if escape:
                        escape = False
                        continue
                    if c == '\\':
                        escape = True
                        continue
                    if c == '"' and not escape:
                        in_str = not in_str
                        continue
                    if not in_str:
                        if c == '{':
                            brace_count += 1
                        elif c == '}':
                            brace_count -= 1
                            if brace_count == 0:
                                end_brace = i + 1
                                break
                
                if end_brace > brace_start:
                    try:
                        obj_text = text[brace_start:end_brace]
                        test_obj = json.loads(obj_text)
                        if isinstance(test_obj, dict) and "days" in test_obj:
                            # Check if "days" is at the root level (not nested)
                            days_value = test_obj.get("days")
                            if isinstance(days_value, list):
                                # This looks like a valid meal plan - prefer larger objects (more complete)
                                obj_size = end_brace - brace_start
                                if obj_size > best_size:
                                    best_candidate = (brace_start, end_brace)
                                    best_size = obj_size
                                    print(f"DEBUG: Found candidate root object with 'days' at brace position {brace_start} (size: {obj_size})")
                    except Exception as e:
                        continue
            
            if best_candidate:
                start_idx, end_brace = best_candidate
                # Validate by parsing again
                try:
                    obj_text = text[start_idx:end_brace]
                    test_obj = json.loads(obj_text)
                    if isinstance(test_obj, dict) and "days" in test_obj and isinstance(test_obj.get("days"), list):
                        print(f"DEBUG: SUCCESS - Using best candidate root object with 'days' at position {start_idx}!")
                        return test_obj
                except:
                    pass
            
            if not best_candidate:
                print("DEBUG: Could not find root object with 'days' by searching backwards, trying all brace positions...")
                # Strategy 2: Try ALL brace positions and find the largest valid object with "days"
                all_braces = [i for i, c in enumerate(text) if c == '{']
                best_candidate_obj = None
                best_size = 0
                
                for brace_start in reversed(all_braces):
                    # Extract object from this brace
                    brace_count = 0
                    in_str = False
                    escape = False
                    end_brace = -1
                    
                    for i in range(brace_start, min(brace_start + 50000, len(text))):  # Limit search to 50k chars
                        c = text[i]
                        if escape:
                            escape = False
                            continue
                        if c == '\\':
                            escape = True
                            continue
                        if c == '"' and not escape:
                            in_str = not in_str
                            continue
                        if not in_str:
                            if c == '{':
                                brace_count += 1
                            elif c == '}':
                                brace_count -= 1
                                if brace_count == 0:
                                    end_brace = i + 1
                                    break
                    
                    if end_brace > brace_start:
                        try:
                            obj_text = text[brace_start:end_brace]
                            test_obj = json.loads(obj_text)
                            if isinstance(test_obj, dict) and "days" in test_obj:
                                days_value = test_obj.get("days")
                                if isinstance(days_value, list):
                                    # This looks like a valid meal plan - prefer larger objects
                                    obj_size = end_brace - brace_start
                                    if obj_size > best_size:
                                        best_candidate_obj = test_obj
                                        best_size = obj_size
                                        print(f"DEBUG: Found candidate root object with 'days' at position {brace_start} (size: {obj_size})")
                        except:
                            continue
                
                if best_candidate_obj:
                    print(f"DEBUG: SUCCESS - Using best candidate root object (size: {best_size})!")
                    return best_candidate_obj
    
    # If we still haven't found the root object with "days", try the original regex approach
    if not best_candidate:
        root_days_match = re.search(r'\{\s*"days"\s*:\s*\[', text)
        if not root_days_match:
            root_days_match = re.search(r'\{[^{}]*"days"\s*:\s*\[', text)
        
        if root_days_match:
            print("DEBUG: Found root object with 'days' key via regex, using that as start")
            start_idx = root_days_match.start()
            start_char = '{'
            end_char = '}'
            days_match = True
            print(f"DEBUG: Found root 'days' object at position {start_idx}")
        else:
            days_match = None
    
    # If start_idx is already set (from days_match logic), skip the array/object detection
    if start_idx is None:
        # Initialize array_start and object_start
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
    else:
        # start_idx and start_char/end_char are already set from days_match logic
        print(f"DEBUG: Using pre-set start_idx: {start_idx}, start_char: {start_char}, end_char: {end_char}")
    
    # Validate start_idx is valid
    if start_idx < 0 or start_idx >= len(text):
        print(f"DEBUG: ERROR - Invalid start_idx: {start_idx}, text length: {len(text)}")
        # Fall back to normal extraction
        array_start = text.find("[")
        object_start = text.find("{")
        if object_start != -1:
            start_idx = object_start
            start_char = '{'
            end_char = '}'
            print(f"DEBUG: Fallback to first {{ at position {start_idx}")
        elif array_start != -1:
            start_idx = array_start
            start_char = '['
            end_char = ']'
            print(f"DEBUG: Fallback to first [ at position {start_idx}")
        else:
            raise ValueError(f"Could not find valid JSON start position. Text length: {len(text)}")
    
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
    
    # Validate that we extracted something meaningful
    if len(json_str) == 0:
        print(f"DEBUG: ERROR - Extracted empty JSON string!")
        print(f"DEBUG: start_idx: {start_idx}, end_idx: {end_idx}, text length: {len(text)}")
        raise ValueError("Extracted empty JSON string from response")
    
    if len(json_str) < 10:
        print(f"DEBUG: WARNING - Extracted very short JSON string: {json_str[:100]}")
    
    # Ensure it starts with { or [
    if not (json_str.strip().startswith('{') or json_str.strip().startswith('[')):
        print(f"DEBUG: WARNING - Extracted JSON doesn't start with {{ or [: {json_str[:100]}")
        # Try to find the actual start
        first_brace = json_str.find('{')
        first_bracket = json_str.find('[')
        if first_brace != -1 and (first_bracket == -1 or first_brace < first_bracket):
            json_str = json_str[first_brace:]
            print(f"DEBUG: Trimmed to start at first {{")
        elif first_bracket != -1:
            json_str = json_str[first_bracket:]
            print(f"DEBUG: Trimmed to start at first [")
    
    # Fix common issues
    json_str = json_str.replace('\\_', '_')
    
    # Fix single quotes in property names in the extracted JSON string too
    json_str = fix_single_quotes_in_property_names(json_str)
    
    # Remove trailing commas before } or ]
    json_str = re.sub(r',\s*}', '}', json_str)
    json_str = re.sub(r',\s*]', ']', json_str)
    
    # Fix common JSON syntax errors
    # Fix unescaped quotes in strings (but be careful not to break valid JSON)
    # Replace single quotes with double quotes (but only outside of strings)
    # This is complex, so we'll try a simpler approach first
    
    try:
        parsed = json.loads(json_str)
        print(f"DEBUG: Successfully parsed JSON (type: {type(parsed).__name__})")
        
        # CRITICAL: If "days" exists in the original text but we extracted an ingredient object, reject it
        if isinstance(parsed, dict) and ('"days"' in text or "'days'" in text):
            # Check if this looks like an ingredient object
            has_ingredient_keys = any(key in parsed for key in ['name', 'amount', 'unit'])
            has_meal_keys = any(key in parsed for key in ['meals', 'days'])
            
            if has_ingredient_keys and not has_meal_keys:
                print(f"DEBUG: CRITICAL - Extracted ingredient object but 'days' exists in response. Rejecting and forcing root object extraction...")
                # Force extraction of root object - find the FIRST { in the text and extract from there
                first_brace = text.find('{')
                if first_brace != -1:
                    print(f"DEBUG: Found first {{ at position {first_brace}, extracting root object...")
                    # Extract root object from first brace
                    brace_count = 0
                    in_str = False
                    escape = False
                    end_brace = -1
                    for i in range(first_brace, len(text)):
                        c = text[i]
                        if escape:
                            escape = False
                            continue
                        if c == '\\':
                            escape = True
                            continue
                        if c == '"' and not escape:
                            in_str = not in_str
                            continue
                        if not in_str:
                            if c == '{':
                                brace_count += 1
                            elif c == '}':
                                brace_count -= 1
                                if brace_count == 0:
                                    end_brace = i + 1
                                    break
                    if end_brace > first_brace:
                        try:
                            root_text = text[first_brace:end_brace]
                            root_parsed = json.loads(root_text)
                            if isinstance(root_parsed, dict) and "days" in root_parsed:
                                print(f"DEBUG: SUCCESS - Found root object with 'days'! Using that instead.")
                                return root_parsed
                            else:
                                print(f"DEBUG: Root object doesn't have 'days' key. Keys: {list(root_parsed.keys())[:10] if isinstance(root_parsed, dict) else 'Not a dict'}")
                        except Exception as root_error:
                            print(f"DEBUG: Failed to parse root object: {root_error}")
            
            # Also check: if we don't have "days" but it exists in text, we MUST have extracted wrong object
            if "days" not in parsed:
                print(f"DEBUG: CRITICAL - Extracted object doesn't have 'days' but 'days' exists in text. Forcing re-extraction...")
                # Try to find and extract root object with "days"
                days_pos = text.find('"days"')
                if days_pos == -1:
                    days_pos = text.find("'days'")
                
                if days_pos != -1:
                    # Find the outermost { that contains "days" by checking all braces before it
                    search_start = max(0, days_pos - 50000)  # Search up to 50000 chars before
                    brace_positions = []
                    for i in range(search_start, days_pos):
                        if text[i] == '{':
                            brace_positions.append(i)
                    
                    # Test each brace from earliest to latest to find the one that contains "days"
                    for brace_start in brace_positions:
                        brace_count = 0
                        in_str = False
                        escape = False
                        end_brace = -1
                        for i in range(brace_start, len(text)):
                            c = text[i]
                            if escape:
                                escape = False
                                continue
                            if c == '\\':
                                escape = True
                                continue
                            if c == '"' and not escape:
                                in_str = not in_str
                                continue
                            if not in_str:
                                if c == '{':
                                    brace_count += 1
                                elif c == '}':
                                    brace_count -= 1
                                    if brace_count == 0:
                                        end_brace = i + 1
                                        break
                        
                        if end_brace > brace_start:
                            try:
                                obj_text = text[brace_start:end_brace]
                                test_obj = json.loads(obj_text)
                                if isinstance(test_obj, dict) and "days" in test_obj:
                                    print(f"DEBUG: SUCCESS - Found root object with 'days' at position {brace_start}!")
                                    return test_obj
                            except:
                                continue
        
        return parsed
    except json.JSONDecodeError as e:
        print(f"DEBUG: JSON parse error: {e}")
        print(f"DEBUG: Error at position {e.pos if hasattr(e, 'pos') else 'unknown'}")
        
        # Try to show context around the error
        if hasattr(e, 'pos') and e.pos:
            start = max(0, e.pos - 150)
            end = min(len(json_str), e.pos + 150)
            print(f"DEBUG: Context around error (char {e.pos}): ...{json_str[start:end]}...")
            print(f"DEBUG: Error line/column: line {e.lineno if hasattr(e, 'lineno') else 'unknown'}, col {e.colno if hasattr(e, 'colno') else 'unknown'}")
        
        # Try multiple fix strategies
        fix_attempts = []
        
        # Strategy 1: Remove trailing text after last }
        try:
            last_brace = json_str.rfind('}')
            if last_brace > 0:
                json_str_fixed = json_str[:last_brace+1]
                # Find matching opening brace
                brace_count = 0
                start_idx = last_brace
                for i in range(last_brace, -1, -1):
                    if json_str_fixed[i] == '}':
                        brace_count += 1
                    elif json_str_fixed[i] == '{':
                        brace_count -= 1
                        if brace_count == 0:
                            start_idx = i
                            break
                json_str_fixed = json_str_fixed[start_idx:]
                parsed = json.loads(json_str_fixed)
                print(f"DEBUG: Successfully parsed JSON after removing trailing text")
                return parsed
        except Exception as fix_error:
            fix_attempts.append(f"Trailing text removal: {fix_error}")
        
        # Strategy 2: Fix missing colons (common error: "key" "value" instead of "key": "value")
        try:
            if hasattr(e, 'pos') and e.pos and "Expecting ':'" in str(e):
                error_pos = e.pos
                print(f"DEBUG: Attempting to fix missing colon at position {error_pos}")
                
                # Strategy 2a: Look for pattern "key" "value" -> "key": "value"
                # Search backwards from error position for a closing quote followed by whitespace and another quote
                pattern = re.compile(r'"\s+"')
                matches = list(pattern.finditer(json_str))
                for match in reversed(matches):
                    if match.end() <= error_pos + 100:  # Within reasonable distance of error
                        # Check if there's no colon between the quotes
                        between = json_str[match.start():match.end()]
                        if ':' not in between:
                            # Insert colon after first quote
                            fixed_pos = match.start() + 1
                            json_str_fixed = json_str[:fixed_pos] + '": ' + json_str[fixed_pos:]
                            try:
                                parsed = json.loads(json_str_fixed)
                                print(f"DEBUG: Successfully parsed JSON after inserting missing colon (pattern match)")
                                return parsed
                            except:
                                pass
                
                # Strategy 2b: Look backwards from error position for a quote and insert colon
                # Find the previous quote before the error
                search_start = max(0, error_pos - 200)
                search_text = json_str[search_start:error_pos + 50]
                
                # Find all quote positions in the search area
                quote_positions = [i + search_start for i, char in enumerate(search_text) if char == '"']
                
                if len(quote_positions) >= 2:
                    # Try inserting colon after the second-to-last quote (likely the key)
                    for i in range(len(quote_positions) - 1, 0, -1):
                        quote_pos = quote_positions[i - 1]
                        if quote_pos < error_pos:
                            # Check if there's already a colon after this quote
                            after_quote = json_str[quote_pos + 1:min(quote_pos + 10, len(json_str))]
                            if ':' not in after_quote[:5]:  # Check first few chars after quote
                                # Insert colon
                                json_str_fixed = json_str[:quote_pos + 1] + ': ' + json_str[quote_pos + 1:]
                                try:
                                    parsed = json.loads(json_str_fixed)
                                    print(f"DEBUG: Successfully parsed JSON after inserting missing colon (quote-based)")
                                    return parsed
                                except:
                                    pass
                
                # Strategy 2c: More aggressive - find quote-quote patterns near error and fix them
                # Look for "word" "word" patterns and convert to "word": "word"
                near_error = json_str[max(0, error_pos - 100):min(len(json_str), error_pos + 100)]
                quote_quote_pattern = re.compile(r'"([^"]+)"\s+"([^"]+)"')
                for match in quote_quote_pattern.finditer(near_error):
                    match_start = match.start() + max(0, error_pos - 100)
                    match_end = match.end() + max(0, error_pos - 100)
                    # Insert colon after first quote group
                    colon_pos = match.start(2) + max(0, error_pos - 100) - 1
                    json_str_fixed = json_str[:colon_pos] + ': ' + json_str[colon_pos:]
                    try:
                        parsed = json.loads(json_str_fixed)
                        print(f"DEBUG: Successfully parsed JSON after inserting missing colon (aggressive pattern)")
                        return parsed
                    except:
                        pass
        except Exception as fix_error:
            fix_attempts.append(f"Missing colon fix: {fix_error}")
        
        # Strategy 3: Fix common syntax errors around the error position
        try:
            if hasattr(e, 'pos') and e.pos:
                # Try to fix issues around the error position
                json_str_fixed = json_str
                error_pos = e.pos
                
                # Look backwards for a quote and check if colon is missing
                if error_pos > 0:
                    # Find the previous quote
                    quote_pos = json_str.rfind('"', 0, error_pos)
                    if quote_pos > 0:
                        # Check if there's a colon after this quote
                        after_quote = json_str[quote_pos+1:error_pos].strip()
                        if after_quote and not after_quote.startswith(':') and '"' in after_quote:
                            # Missing colon - insert it
                            colon_pos = quote_pos + 1
                            json_str_fixed = json_str[:colon_pos] + ': ' + json_str[colon_pos:]
                            try:
                                parsed = json.loads(json_str_fixed)
                                print(f"DEBUG: Successfully parsed JSON after inserting colon after quote")
                                return parsed
                            except:
                                pass
                
                # Fix missing comma before closing brace/bracket
                if error_pos > 0 and error_pos < len(json_str_fixed):
                    char_before = json_str_fixed[error_pos - 1] if error_pos > 0 else ''
                    char_at = json_str_fixed[error_pos] if error_pos < len(json_str_fixed) else ''
                    
                    # If we're expecting a comma, try inserting one
                    if char_before not in [',', '[', '{', ':'] and char_at in ['}', ']']:
                        json_str_fixed = json_str_fixed[:error_pos] + ',' + json_str_fixed[error_pos:]
                        try:
                            parsed = json.loads(json_str_fixed)
                            print(f"DEBUG: Successfully parsed JSON after inserting comma")
                            return parsed
                        except:
                            pass
                
                # Try removing the problematic character and retrying
                json_str_fixed = json_str[:error_pos] + json_str[error_pos+1:]
                try:
                    parsed = json.loads(json_str_fixed)
                    print(f"DEBUG: Successfully parsed JSON after removing problematic character")
                    return parsed
                except:
                    pass
        except Exception as fix_error:
            fix_attempts.append(f"Character fix: {fix_error}")
        
        # Strategy 4: Try to extract just the days array if it exists
        try:
            days_match = re.search(r'"days"\s*:\s*\[', json_str)
            if days_match:
                # Find the matching closing bracket
                start_pos = days_match.end() - 1  # Position of [
                bracket_count = 0
                end_pos = start_pos
                for i in range(start_pos, len(json_str)):
                    if json_str[i] == '[':
                        bracket_count += 1
                    elif json_str[i] == ']':
                        bracket_count -= 1
                        if bracket_count == 0:
                            end_pos = i + 1
                            break
                
                if end_pos > start_pos:
                    days_array_str = json_str[start_pos:end_pos]
                    days_array = json.loads(days_array_str)
                    # Wrap in proper structure
                    parsed = {"days": days_array}
                    print(f"DEBUG: Successfully parsed JSON by extracting days array")
                    return parsed
        except Exception as fix_error:
            fix_attempts.append(f"Days extraction: {fix_error}")
        
        print(f"DEBUG: All fix attempts failed: {fix_attempts}")
        print(f"DEBUG: Problematic JSON (first 3000 chars): {json_str[:3000]}")
        raise ValueError(f"Invalid JSON in LLM response: {str(e)}")


async def get_nutrition_from_edamam(ingredient_name: str, quantity: float = 100) -> Optional[Dict[str, float]]:
    """Get nutrition data from Edamam API"""
    if not EDAMAM_APP_ID or not EDAMAM_APP_KEY:
        return None
    
    try:
        url = "https://api.edamam.com/api/nutrition-data"
        params = {
            "app_id": EDAMAM_APP_ID,
            "app_key": EDAMAM_APP_KEY,
            "ingr": f"{quantity}g {ingredient_name}"
        }
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(url, params=params)
            if response.status_code == 200:
                data = response.json()
                return {
                    "calories": data.get("calories", 0),
                    "protein": data.get("totalNutrients", {}).get("PROCNT", {}).get("quantity", 0),
                    "carbs": data.get("totalNutrients", {}).get("CHOCDF", {}).get("quantity", 0),
                    "fat": data.get("totalNutrients", {}).get("FAT", {}).get("quantity", 0)
                }
    except Exception as e:
        print(f"Edamam API error: {e}")
    return None


async def get_nutrition_from_usda(food_name: str) -> Optional[Dict[str, float]]:
    """Get nutrition data from USDA API"""
    if not USDA_API_KEY:
        return None
    
    try:
        # Search for food
        search_url = "https://api.nal.usda.gov/fdc/v1/foods/search"
        params = {
            "api_key": USDA_API_KEY,
            "query": food_name,
            "pageSize": 1
        }
        async with httpx.AsyncClient(timeout=10.0) as client:
            search_response = await client.get(search_url, params=params)
            if search_response.status_code == 200:
                search_data = search_response.json()
                if search_data.get("foods") and len(search_data["foods"]) > 0:
                    fdc_id = search_data["foods"][0].get("fdcId")
                    if fdc_id:
                        # Get detailed nutrition
                        detail_url = f"https://api.nal.usda.gov/fdc/v1/food/{fdc_id}"
                        detail_params = {"api_key": USDA_API_KEY}
                        detail_response = await client.get(detail_url, params=detail_params)
                        if detail_response.status_code == 200:
                            detail_data = detail_response.json()
                            nutrients = {n["name"]: n["amount"] for n in detail_data.get("foodNutrients", [])}
                            return {
                                "calories": nutrients.get("Energy", 0),
                                "protein": nutrients.get("Protein", 0),
                                "carbs": nutrients.get("Carbohydrate, by difference", 0),
                                "fat": nutrients.get("Total lipid (fat)", 0)
                            }
    except Exception as e:
        print(f"USDA API error: {e}")
    return None


async def calculate_nutrition(recipe_data: Dict[str, Any]) -> Dict[str, float]:
    """Calculate nutrition from recipe ingredients using APIs or fallback"""
    total_calories = 0
    total_protein = 0
    total_carbs = 0
    total_fat = 0
    
    for ingredient in recipe_data.get("ingredients", []):
        ing_name = ingredient.get("name", "").lower()
        amount_str = ingredient.get("amount", "1")
        
        # Try to extract number
        try:
            amount = float(amount_str.split()[0])
        except:
            amount = 100  # Default to 100g
        
        # Try Edamam first
        nutrition = await get_nutrition_from_edamam(ing_name, amount)
        
        # Fallback to USDA
        if not nutrition:
            nutrition = await get_nutrition_from_usda(ing_name)
        
        # Fallback to local DB
        if not nutrition:
            for food, nut in NUTRITION_DB.items():
                if food in ing_name:
                    nutrition = {
                        "calories": nut["calories"] * amount / 100,
                        "protein": nut["protein"] * amount / 100,
                        "carbs": nut["carbs"] * amount / 100,
                        "fat": nut["fat"] * amount / 100
                    }
                break
        
        if nutrition:
            total_calories += nutrition.get("calories", 0)
            total_protein += nutrition.get("protein", 0)
            total_carbs += nutrition.get("carbs", 0)
            total_fat += nutrition.get("fat", 0)
    
    servings = recipe_data.get("servings", 4)
    return {
        "calories_per_serving": round(total_calories / servings, 1) if servings > 0 else 0,
        "protein_grams": round(total_protein / servings, 1) if servings > 0 else 0,
        "carbs_grams": round(total_carbs / servings, 1) if servings > 0 else 0,
        "fat_grams": round(total_fat / servings, 1) if servings > 0 else 0
    }


async def generate_recipe_image(recipe_name: str, description: str) -> Optional[str]:
    """Generate an image for a recipe using OpenAI DALL-E or food-specific APIs"""
    # Try OpenAI DALL-E first if API key is available
    if OPENAI_API_KEY:
        try:
            prompt = f"A beautiful, appetizing photo of {recipe_name}. {description}. Professional food photography, high quality, well-lit."
            
            url = "https://api.openai.com/v1/images/generations"
            headers = {
                "Authorization": f"Bearer {OPENAI_API_KEY}",
                "Content-Type": "application/json"
            }
            payload = {
                "model": "dall-e-3",
                "prompt": prompt,
                "n": 1,
                "size": "1024x1024"
            }
            
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(url, headers=headers, json=payload)
                if response.status_code == 200:
                    data = response.json()
                    image_url = data.get("data", [{}])[0].get("url")
                    if image_url:
                        print(f"DEBUG: Using OpenAI DALL-E image for {recipe_name}")
                        return image_url
        except Exception as e:
            print(f"OpenAI image generation error: {e}")
    
    # Primary: Use Foodish API - provides food-specific images
    recipe_lower = recipe_name.lower()
    category = None
    
    # Improved category mapping for better matching
    if any(word in recipe_lower for word in ['pasta', 'spaghetti', 'noodles', 'fettuccine', 'penne', 'macaroni', 'linguine']):
        category = "pasta"
    elif any(word in recipe_lower for word in ['pizza', 'margherita', 'pepperoni', 'calzone']):
        category = "pizza"
    elif any(word in recipe_lower for word in ['burger', 'hamburger', 'cheeseburger', 'patty']):
        category = "burger"
    elif any(word in recipe_lower for word in ['rice', 'fried rice', 'risotto', 'pilaf']):
        category = "rice"
    elif any(word in recipe_lower for word in ['chicken', 'poultry', 'roast chicken', 'grilled chicken']):
        category = "butter-chicken"
    elif any(word in recipe_lower for word in ['biryani']):
        category = "biryani"
    elif any(word in recipe_lower for word in ['dosa']):
        category = "dosa"
    elif any(word in recipe_lower for word in ['idly', 'idli']):
        category = "idly"
    elif any(word in recipe_lower for word in ['samosa']):
        category = "samosa"
    elif any(word in recipe_lower for word in ['dessert', 'cake', 'cookie', 'sweet', 'pie', 'pastry']):
        category = "dessert"
    elif any(word in recipe_lower for word in ['oatmeal', 'oats', 'cereal', 'porridge', 'granola']):
        # For breakfast items, try pasta as closest match, or dessert
        category = "dessert"
    elif any(word in recipe_lower for word in ['salad', 'greens', 'lettuce', 'caesar', 'spinach']):
        # Salad doesn't have a category, use dessert as fallback
        category = "dessert"
    elif any(word in recipe_lower for word in ['soup', 'stew', 'broth']):
        category = "rice"  # Closest match
    elif any(word in recipe_lower for word in ['toast', 'bread', 'sandwich']):
        category = "burger"  # Closest match
    elif any(word in recipe_lower for word in ['egg', 'scrambled', 'omelet', 'omelette']):
        category = "burger"  # Closest match
    
    # Use Spoonacular Food API for food images (free tier available)
    # Alternative: Use a food image search service
    # Since Foodish API is down, we'll use a combination of approaches
    
    # Try TheMealDB API for food images (free, no API key needed for basic usage)
    # Try multiple search strategies
    search_strategies = [
        recipe_name,  # Full name
        recipe_name.split()[0] if recipe_name.split() else recipe_name,  # First word
    ]
    
    # Extract key food words from recipe name
    food_keywords = []
    for word in recipe_lower.split():
        if word not in ['with', 'and', 'the', 'a', 'an', 'for', 'to', 'of', 'in', 'on', 'at', 'by']:
            if len(word) > 3:  # Only meaningful words
                food_keywords.append(word)
    
    if food_keywords:
        search_strategies.extend(food_keywords[:3])  # Add up to 3 keywords
    
    for search_term in search_strategies:
        try:
            themedb_url = f"https://www.themealdb.com/api/json/v1/1/search.php?s={urllib.parse.quote(search_term)}"
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(themedb_url)
                if response.status_code == 200:
                    data = response.json()
                    if data.get("meals") and len(data["meals"]) > 0:
                        image_url = data["meals"][0].get("strMealThumb")
                        if image_url:
                            print(f"DEBUG: Using TheMealDB image for '{recipe_name}' (searched: '{search_term}'): {image_url}")
                            return image_url
        except Exception as e:
            print(f"DEBUG: TheMealDB API error for '{search_term}': {e}")
            continue
    
    # If no match found, try random meals from relevant categories
    try:
        # Try to get a random meal from a category that matches
        category_map = {
            'pasta': 'Seafood',  # TheMealDB categories
            'pizza': 'Miscellaneous',
            'chicken': 'Chicken',
            'beef': 'Beef',
            'dessert': 'Dessert',
            'vegetarian': 'Vegetarian',
            'breakfast': 'Breakfast'
        }
        
        # Find matching category
        themedb_category = None
        for key, cat in category_map.items():
            if key in recipe_lower:
                themedb_category = cat
                break
        
        if themedb_category:
            # Get random meal from category
            random_url = f"https://www.themealdb.com/api/json/v1/1/filter.php?c={urllib.parse.quote(themedb_category)}"
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(random_url)
                if response.status_code == 200:
                    data = response.json()
                    if data.get("meals") and len(data["meals"]) > 0:
                        import random
                        meal = random.choice(data["meals"])
                        image_url = meal.get("strMealThumb")
                        if image_url:
                            print(f"DEBUG: Using TheMealDB random image from category '{themedb_category}' for '{recipe_name}': {image_url}")
                            return image_url
    except Exception as e:
        print(f"DEBUG: TheMealDB category search error: {e}")
    
    # Try Foodish API (may be down, but worth trying)
    if category:
        try:
            foodish_url = f"https://foodish-api.herokuapp.com/api/images/{category}"
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(foodish_url)
                if response.status_code == 200:
                    data = response.json()
                    image_url = data.get("image")
                    if image_url:
                        print(f"DEBUG: Using Foodish API image for '{recipe_name}' -> category '{category}': {image_url}")
                        return image_url
        except Exception as e:
            print(f"DEBUG: Foodish API error for category '{category}': {e}")
    
    # Fallback: Try to get a random food image from TheMealDB (better than placeholder)
    try:
        # Get a random meal image as fallback
        random_url = "https://www.themealdb.com/api/json/v1/1/random.php"
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(random_url)
            if response.status_code == 200:
                data = response.json()
                if data.get("meals") and len(data["meals"]) > 0:
                    image_url = data["meals"][0].get("strMealThumb")
                    if image_url:
                        print(f"DEBUG: Using TheMealDB random image as fallback for '{recipe_name}': {image_url}")
                        return image_url
    except Exception as e:
        print(f"DEBUG: TheMealDB random fallback error: {e}")
    
    # Last resort: Use a working placeholder service with recipe name
    try:
        # Use placehold.co which is more reliable
        placeholder_text = urllib.parse.quote(f"Food: {recipe_name[:15]}")
        placeholder_url = f"https://placehold.co/800x600/FF6B6B/FFFFFF?text={placeholder_text}"
        print(f"DEBUG: Using placeholder for '{recipe_name}' (all food APIs unavailable)")
        return placeholder_url
    except Exception as e:
        print(f"DEBUG: Placeholder generation error: {e}")
        # Last resort: return None and let frontend handle it
        return None


def scale_recipe_ingredients(recipe: Dict[str, Any], original_servings: int, new_servings: int) -> List[Dict[str, Any]]:
    """Scale recipe ingredients to new serving size"""
    if new_servings <= 0:
        return recipe.get("ingredients", [])
    
    scale_factor = new_servings / original_servings
    scaled_ingredients = []
    
    for ingredient in recipe.get("ingredients", []):
        amount_str = ingredient.get("amount", "1")
        try:
            # Try to extract number
            amount = float(amount_str.split()[0])
            unit = " ".join(amount_str.split()[1:]) if len(amount_str.split()) > 1 else ingredient.get("unit", "")
            new_amount = round(amount * scale_factor, 2)
            scaled_ingredients.append({
                "name": ingredient.get("name"),
                "amount": f"{new_amount}",
                "unit": unit
            })
        except:
            # If we can't parse, keep original
            scaled_ingredients.append(ingredient)
    
    return scaled_ingredients


def generate_shopping_list(recipe_ids: Optional[List[str]] = None, meal_plan_id: Optional[str] = None) -> Dict[str, Any]:
    """Generate a shopping list from recipes or meal plan"""
    ingredients_dict: Dict[str, Dict[str, Any]] = {}
    
    if meal_plan_id and meal_plan_id in meal_plans_storage:
        plan = meal_plans_storage[meal_plan_id]
        # Extract ingredients from all meals in the meal plan
        for day in plan.get("days", []):
            for meal in day.get("meals", []):
                for ingredient in meal.get("ingredients", []):
                    name = ingredient.get("name", "").lower()
                    amount = ingredient.get("amount", "")
                    unit = ingredient.get("unit", "")
                    
                    if name in ingredients_dict:
                        # Try to combine amounts
                        ingredients_dict[name]["count"] += 1
                    else:
                        ingredients_dict[name] = {
                            "name": ingredient.get("name"),
                            "amount": amount,
                            "unit": unit,
                            "count": 1
                        }
    
    if recipe_ids:
        for recipe_id in recipe_ids:
            if recipe_id in recipes_storage:
                recipe = recipes_storage[recipe_id]
                for ingredient in recipe.get("ingredients", []):
                    name = ingredient.get("name", "").lower()
                    amount = ingredient.get("amount", "")
                    unit = ingredient.get("unit", "")
                    
                    if name in ingredients_dict:
                        # Try to combine amounts
                        ingredients_dict[name]["count"] += 1
                    else:
                        ingredients_dict[name] = {
                            "name": ingredient.get("name"),
                            "amount": amount,
                            "unit": unit,
                            "count": 1
                        }
    
    shopping_list = list(ingredients_dict.values())
    return {
        "items": shopping_list,
        "total_items": len(shopping_list),
        "generated_at": datetime.now().isoformat()
    }


def generate_meal_plan_pdf(meal_plan: Dict[str, Any]) -> BytesIO:
    """Generate a PDF from meal plan"""
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter)
    story = []
    
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=24,
        textColor=colors.HexColor('#667eea'),
        spaceAfter=30
    )
    
    # Title
    story.append(Paragraph(f"{meal_plan.get('total_days', 7)}-Day Meal Plan", title_style))
    story.append(Spacer(1, 0.2*inch))
    
    # Summary
    total_calories = sum(day.get("total_calories", 0) for day in meal_plan.get("days", []))
    avg_calories = round(total_calories / len(meal_plan.get("days", [1]))) if meal_plan.get("days") else 0
    story.append(Paragraph(f"<b>Summary:</b> Average {avg_calories} calories/day | Total {total_calories} calories", styles['Normal']))
    story.append(Spacer(1, 0.3*inch))
    
    # Days
    for day in meal_plan.get("days", []):
        # Parse date consistently - handle both date-only and datetime strings
        date_str = day.get("date", "")
        if date_str:
            try:
                # If it's just a date (YYYY-MM-DD), parse it as date
                if len(date_str) == 10 and date_str.count("-") == 2:
                    date_obj = datetime.strptime(date_str, "%Y-%m-%d").date()
                else:
                    # Otherwise parse as ISO datetime
                    date_obj = datetime.fromisoformat(date_str.replace("Z", "+00:00")).date()
            except:
                # Fallback to today if parsing fails
                date_obj = datetime.now().date()
        else:
            date_obj = datetime.now().date()
        date = date_obj.strftime("%B %d, %Y")
        story.append(Paragraph(f"<b>Day {day.get('day_number', 1)} - {date}</b>", styles['Heading2']))
        story.append(Spacer(1, 0.1*inch))
        
        # Meals table - use Paragraphs for text wrapping
        meal_data = [[
            Paragraph("<b>Meal</b>", styles['Normal']),
            Paragraph("<b>Name</b>", styles['Normal']),
            Paragraph("<b>Description</b>", styles['Normal']),
            Paragraph("<b>Calories</b>", styles['Normal'])
        ]]
        
        # Create a style for table cells with smaller font and tighter spacing
        cell_style = ParagraphStyle(
            'TableCell',
            parent=styles['Normal'],
            fontSize=7,
            leading=9,
            spaceAfter=3,
            spaceBefore=1
        )
        
        name_style = ParagraphStyle(
            'TableCellName',
            parent=styles['Normal'],
            fontSize=7,
            leading=9,
            spaceAfter=3,
            spaceBefore=1
        )
        
        for meal in day.get("meals", []):
            meal_type = meal.get("meal_type", "").title()
            meal_name = meal.get("name", "")
            # Truncate long names
            if len(meal_name) > 25:
                meal_name = meal_name[:22] + "..."
            meal_desc = meal.get("description", "") or ""
            # Limit description length more aggressively for PDF
            if len(meal_desc) > 50:
                meal_desc = meal_desc[:47] + "..."
            calories = str(meal.get("estimated_calories", 0))
            
            meal_data.append([
                Paragraph(meal_type, cell_style),
                Paragraph(meal_name, name_style),
                Paragraph(meal_desc, cell_style),
                Paragraph(calories, cell_style)
            ])
        
        # Better column widths - letter size is 8.5 inches, use 7.2 for content (leave margins)
        # Meal: 0.9, Name: 1.8, Description: 3.8, Calories: 0.7
        table = Table(meal_data, colWidths=[0.9*inch, 1.8*inch, 3.8*inch, 0.7*inch])
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#667eea')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 9),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 10),
            ('TOPPADDING', (0, 1), (-1, -1), 6),
            ('BOTTOMPADDING', (0, 1), (-1, -1), 6),
            ('LEFTPADDING', (0, 0), (-1, -1), 4),
            ('RIGHTPADDING', (0, 0), (-1, -1), 4),
            ('FONTSIZE', (0, 1), (-1, -1), 8),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('WORDWRAP', (0, 0), (-1, -1), True)
        ]))
        story.append(table)
        story.append(Spacer(1, 0.15*inch))
        
        # Add full recipe details for each meal
        for meal in day.get("meals", []):
            story.append(Spacer(1, 0.1*inch))
            story.append(Paragraph(f"<b>{meal.get('meal_type', '').title()}: {meal.get('name', '')}</b>", styles['Heading3']))
            
            # Add image if available
            if meal.get("image_url"):
                try:
                    # Download and embed image synchronously for PDF
                    import requests
                    img_response = requests.get(meal.get("image_url"), timeout=10)
                    if img_response.status_code == 200:
                        img_buffer = BytesIO(img_response.content)
                        # Create PIL Image to resize if needed
                        pil_img = PILImage.open(img_buffer)
                        # Resize to fit PDF (max width 4 inches = 288 points)
                        max_width_pts = 4 * 72  # 4 inches in points
                        if pil_img.width > max_width_pts:
                            ratio = max_width_pts / pil_img.width
                            new_height = int(pil_img.height * ratio)
                            pil_img = pil_img.resize((int(max_width_pts), new_height), PILImage.Resampling.LANCZOS)
                        
                        # Save to buffer
                        img_buffer = BytesIO()
                        pil_img.save(img_buffer, format='PNG')
                        img_buffer.seek(0)
                        
                        # Add to PDF (convert pixels to points - 1 pixel = 1 point at 72 DPI)
                        reportlab_img = Image(img_buffer, width=min(max_width_pts, pil_img.width), height=pil_img.height)
                        story.append(reportlab_img)
                        story.append(Spacer(1, 0.1*inch))
                except Exception as e:
                    print(f"Failed to add image to PDF for {meal.get('name')}: {e}")
                    # Continue without image
            
            if meal.get("ingredients"):
                story.append(Paragraph("<b>Ingredients:</b>", styles['Normal']))
                ingredients_text = ", ".join([
                    f"{ing.get('name', '')} ({ing.get('amount', '')} {ing.get('unit', '')})"
                    for ing in meal.get("ingredients", [])
                ])
                # Break long ingredient lists into multiple lines
                if len(ingredients_text) > 100:
                    words = ingredients_text.split(", ")
                    lines = []
                    current_line = ""
                    for word in words:
                        if len(current_line + word) > 100:
                            lines.append(current_line)
                            current_line = word + ", "
                        else:
                            current_line += word + ", "
                    if current_line:
                        lines.append(current_line.rstrip(", "))
                    ingredients_text = "<br/>".join(lines)
                story.append(Paragraph(ingredients_text, cell_style))
            
            if meal.get("instructions"):
                story.append(Spacer(1, 0.1*inch))
                story.append(Paragraph("<b>Instructions:</b>", styles['Normal']))
                for idx, instruction in enumerate(meal.get("instructions", [])[:5], 1):  # Limit to 5 steps
                    story.append(Paragraph(f"{idx}. {instruction[:150]}", cell_style))
            
            story.append(Spacer(1, 0.1*inch))
        
        story.append(Spacer(1, 0.2*inch))
        story.append(Paragraph(f"<b>Daily Total: {day.get('total_calories', 0)} calories</b>", styles['Normal']))
        story.append(PageBreak())
    
    doc.build(story)
    buffer.seek(0)
    return buffer


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
        
        # Build dietary restrictions text
        dietary_restrictions = ""
        dietary_restrictions_reminder = ""
        if request.dietary_preferences:
            restrictions = []
            reminders = []
            if "vegan" in request.dietary_preferences:
                restrictions.append("⚠️ CRITICAL VEGAN RESTRICTIONS - ABSOLUTELY MANDATORY ⚠️\nNO animal products are allowed. DO NOT use ANY of the following:\n- Meat: chicken, beef, pork, lamb, turkey, duck, etc.\n- Seafood: fish, shrimp, crab, lobster, tuna, salmon, etc.\n- Dairy: milk, cheese, butter, yogurt, cream, sour cream, etc.\n- Eggs: NO eggs in any form (whole eggs, egg whites, egg yolks)\n- Honey: NO honey\n- Any other animal-derived ingredients\n\nMUST USE plant-based alternatives:\n- Plant milk (almond milk, soy milk, oat milk, coconut milk)\n- Vegan cheese, vegan butter\n- Tofu, tempeh, legumes for protein\n- Nutritional yeast, plant-based proteins")
                reminders.append("REMINDER: Recipe is VEGAN - NO eggs, dairy, meat, fish, or any animal products!")
            if "vegetarian" in request.dietary_preferences and "vegan" not in request.dietary_preferences:
                restrictions.append("CRITICAL VEGETARIAN RESTRICTIONS: NO meat, poultry, or seafood allowed. DO NOT use: chicken, beef, pork, fish, seafood, or any meat products. Dairy and eggs are allowed.")
            if "gluten-free" in request.dietary_preferences:
                restrictions.append("CRITICAL GLUTEN-FREE RESTRICTIONS: NO wheat, barley, rye, or gluten-containing ingredients. Use gluten-free alternatives (rice, quinoa, gluten-free pasta, etc.).")
            if "dairy-free" in request.dietary_preferences:
                restrictions.append("CRITICAL DAIRY-FREE RESTRICTIONS: NO dairy products allowed. DO NOT use: milk, cheese, butter, yogurt, cream, or any dairy products. Use dairy-free alternatives.")
            if "low-carb" in request.dietary_preferences:
                restrictions.append("CRITICAL LOW-CARB RESTRICTIONS: Minimize carbohydrates. Avoid or limit: bread, pasta, rice, potatoes, sugar, and high-carb foods.")
            if "keto" in request.dietary_preferences:
                restrictions.append("CRITICAL KETO RESTRICTIONS: Very low carbohydrates (under 20g net carbs per serving). NO: bread, pasta, rice, potatoes, sugar, grains, or high-carb foods. Focus on: meat, fish, eggs, low-carb vegetables, healthy fats.")
            
            if restrictions:
                dietary_restrictions = "\n".join(restrictions) + "\n"
            if reminders:
                dietary_restrictions_reminder = " ".join(reminders)
        
        print(f"DEBUG: Generating recipe - Ingredients: {ingredients_str}")
        print(f"DEBUG: Cuisine: {cuisine_display}, Meal: {meal_display}, Servings: {request.servings}")
        print(f"DEBUG: Dietary preferences: {dietary_display}")
        
        prompt = RECIPE_GENERATION_TEMPLATE.format(
            ingredients=ingredients_str,
            dietary_preferences=dietary_display,
            dietary_restrictions=dietary_restrictions,
            dietary_restrictions_reminder=dietary_restrictions_reminder if dietary_restrictions_reminder else "Follow all dietary preferences listed above.",
            cuisine_type=request.cuisine_type or "Any",
            meal_type=request.meal_type or "Any",
            servings=request.servings,
            cuisine_display=cuisine_display,
            meal_display=meal_display
        )
        
        # Enhanced system prompt for vegan recipes
        system_prompt = "You are a professional chef. Always return valid JSON. Provide detailed, step-by-step instructions with specific actions, temperatures, times, and preparation details. Avoid vague instructions."
        if request.dietary_preferences and "vegan" in request.dietary_preferences:
            system_prompt += " CRITICAL: This recipe MUST be vegan. DO NOT include eggs, dairy, meat, fish, or any animal products. Use only plant-based ingredients."
        
        llm_response = await call_together_ai(
            prompt,
            system_prompt=system_prompt
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
        
        # Post-process: Remove animal products if vegan is selected
        if request.dietary_preferences and "vegan" in request.dietary_preferences:
            import re
            # Comprehensive animal product patterns - including variations with punctuation
            animal_patterns = [
                # Eggs - most comprehensive (including typos like "eeg" and shortened "eg")
                r'\begg\b', r'\beggs\b', r'\beeg\b', r'\beegs\b',  # Standard and typo variations
                r'\beg\b', r'\begs\b',  # Shortened form "eg" (but not in "vegetable", "leg", etc.)
                r'\begg\s+white', r'\begg\s+whites', r'\begg\s+yolk', r'\begg\s+yolks',
                r'\begg,', r'\beggs,', r'\begg\.', r'\beggs\.', r'\begg\s', r'\beggs\s',
                r'\beeg,', r'\beegs,', r'\beeg\.', r'\beegs\.', r'\beeg\s', r'\beegs\s',  # Typo variations
                r'\beg,', r'\begs,', r'\beg\.', r'\begs\.', r'\beg\s', r'\begs\s',  # Shortened form variations
                r'\begg\s*-\s*\d', r'\beggs\s*-\s*\d',  # "egg - 1" or "eggs - 1"
                r'\begg-\d', r'\beggs-\d',  # "egg-1" or "eggs-1" (no spaces)
                r'\beeg\s*-\s*\d', r'\beegs\s*-\s*\d',  # "eeg - 1" (typo)
                r'\beeg-\d', r'\beegs-\d',  # "eeg-1" (typo, no spaces)
                r'\beg\s*-\s*\d', r'\begs\s*-\s*\d',  # "eg - 1" (shortened)
                r'\beg-\d', r'\begs-\d',  # "eg-1" or "egs-1" (shortened, no spaces)
                r'\begg\s*-\s*\d+\s+\w+', r'\beggs\s*-\s*\d+\s+\w+',  # "egg - 1 large"
                r'\beeg\s*-\s*\d+\s+\w+', r'\beegs\s*-\s*\d+\s+\w+',  # "eeg - 1 large" (typo)
                r'\beg\s*-\s*\d+\s+\w+', r'\begs\s*-\s*\d+\s+\w+',  # "eg - 1 large" (shortened)
                # Compound phrases with egg
                r'\bpoached\s+egg', r'\bpoached\s+eggs', r'\bpoached\s+eeg', r'\bpoached\s+eegs', r'\bpoached\s+eg', r'\bpoached\s+egs',  # "poached egg"
                r'\bfried\s+egg', r'\bfried\s+eggs', r'\bfried\s+eeg', r'\bfried\s+eegs', r'\bfried\s+eg', r'\bfried\s+egs',  # "fried egg"
                r'\bscrambled\s+egg', r'\bscrambled\s+eggs', r'\bscrambled\s+eeg', r'\bscrambled\s+eegs', r'\bscrambled\s+eg', r'\bscrambled\s+egs',  # "scrambled egg"
                r'\bboiled\s+egg', r'\bboiled\s+eggs', r'\bboiled\s+eeg', r'\bboiled\s+eegs', r'\bboiled\s+eg', r'\bboiled\s+egs',  # "boiled egg"
                r'\bhard\s+boiled\s+egg', r'\bhard\s+boiled\s+eggs',  # "hard boiled egg"
                r'\bsoft\s+boiled\s+egg', r'\bsoft\s+boiled\s+eggs',  # "soft boiled egg"
                r'\bsunny\s+side\s+up\s+egg', r'\bsunny\s+side\s+up\s+eggs',  # "sunny side up egg"
                r'\bover\s+easy\s+egg', r'\bover\s+easy\s+eggs',  # "over easy egg"
                r'\braw\s+egg', r'\braw\s+eggs', r'\braw\s+eg', r'\braw\s+egs',  # "raw egg"
                r'\bwhole\s+egg', r'\bwhole\s+eggs', r'\bwhole\s+eg', r'\bwhole\s+egs',  # "whole egg"
                r'\btoast\s+with\s+eg', r'\btoast\s+with\s+egs',  # "toast with eg"
                # Meat
                r'\bchicken\b', r'\bbeef\b', r'\bpork\b', r'\blamb\b', r'\bturkey\b', r'\bduck\b',
                r'\bchicken\s+breast\b', r'\bground\s+beef\b', r'\bmeat\b', r'\bpoultry\b',
                # Seafood
                r'\bfish\b', r'\bsalmon\b', r'\btuna\b', r'\bshrimp\b', r'\bcrab\b', r'\blobster\b', r'\bseafood\b',
                # Dairy
                r'\bmilk\b', r'\bcheese\b', r'\bbutter\b', r'\byogurt\b', r'\bcream\b', r'\bsour\s+cream\b', r'\bdairy\b',
                # Other animal products
                r'\bhoney\b', r'\bgelatin\b', r'\bwhey\b', r'\bcasein\b', r'\blard\b', r'\bbacon\b', r'\bham\b'
            ]
            
            def contains_animal_product(text):
                """Check if text contains any animal product - case insensitive"""
                if not text:
                    return False
                text_lower = str(text).lower().strip()
                
                # FIRST: Quick check for any "egg" followed by hyphen and number (most common case)
                # This catches "egg - 1", "eggs - 3", "egg-1", "eggs-3", "egg - 1 large", "eggs - 3 large", etc.
                if re.search(r'\b(eeg|egg|eg|eggs|egs)\s*-\s*\d', text_lower):
                    if 'eggplant' not in text_lower and 'eggshell' not in text_lower:
                        print(f"DEBUG: contains_animal_product QUICK MATCH: '{text_lower}'")
                        return True
                
                # Check for exact word matches and also partial matches for compound words
                for pattern in animal_patterns:
                    if re.search(pattern, text_lower):
                        return True
                
                # Additional aggressive check for "egg" variations (including with hyphens, spaces, punctuation)
                # Check for "egg" or "eggs" as standalone words or with punctuation
                egg_variations = [
                    r'\begg\b', r'\beggs\b',  # Word boundaries
                    r'\beeg\b', r'\beegs\b',  # Typo variations
                    r'\beg\b', r'\begs\b',  # Shortened form "eg" (but not in "vegetable", "leg", etc.)
                    r'\begg\s', r'\beggs\s',  # Followed by space
                    r'\beeg\s', r'\beegs\s',  # Typo followed by space
                    r'\beg\s', r'\begs\s',  # Shortened form followed by space
                    r'\begg-', r'\beggs-',  # Followed by hyphen
                    r'\beeg-', r'\beegs-',  # Typo followed by hyphen
                    r'\beg-', r'\begs-',  # Shortened form followed by hyphen
                    r'\begg,', r'\beggs,',  # Followed by comma
                    r'\beeg,', r'\beegs,',  # Typo followed by comma
                    r'\beg,', r'\begs,',  # Shortened form followed by comma
                    r'\begg\.', r'\beggs\.',  # Followed by period
                    r'\beeg\.', r'\beegs\.',  # Typo followed by period
                    r'\beg\.', r'\begs\.',  # Shortened form followed by period
                    r'^egg', r'^eggs', r'^eeg', r'^eegs', r'^eg', r'^egs',  # At start of string
                    r'egg$', r'eggs$', r'eeg$', r'eegs$', r'eg$', r'egs$',  # At end of string
                    r'\begg\s*-\s*\d',  # "egg - 1" or "egg-1"
                    r'\begg-\d', r'\beggs-\d',  # "egg-1" or "eggs-1" (no spaces)
                    r'\beggs\s*-\s*\d',  # "eggs - 1" or "eggs-1"
                    r'\beeg\s*-\s*\d',  # "eeg - 1" or "eeg-1" (typo)
                    r'\beeg-\d', r'\beegs-\d',  # "eeg-1" or "eegs-1" (typo, no spaces)
                    r'\beegs\s*-\s*\d',  # "eegs - 1" or "eegs-1" (typo)
                    r'\beg\s*-\s*\d',  # "eg - 1" or "eg-1" (shortened)
                    r'\beg-\d', r'\begs-\d',  # "eg-1" or "egs-1" (shortened, no spaces)
                    r'\begs\s*-\s*\d',  # "egs - 1" or "egs-1" (shortened)
                    r'\begg\s*-\s*\d+\s+\w+',  # "egg - 1 large" or "egg-1 large"
                    r'\beggs\s*-\s*\d+\s+\w+',  # "eggs - 1 large" or "eggs-1 large"
                    r'\beeg\s*-\s*\d+\s+\w+',  # "eeg - 1 large" or "eeg-1 large" (typo)
                    r'\beegs\s*-\s*\d+\s+\w+',  # "eegs - 1 large" or "eegs-1 large" (typo)
                    r'\beg\s*-\s*\d+\s+\w+',  # "eg - 1 large" or "eg-1 large" (shortened)
                    r'\begs\s*-\s*\d+\s+\w+',  # "egs - 1 large" or "egs-1 large" (shortened)
                    # Compound phrases
                    r'\bpoached\s+egg', r'\bpoached\s+eggs', r'\bpoached\s+eeg', r'\bpoached\s+eegs', r'\bpoached\s+eg', r'\bpoached\s+egs',
                    r'\bfried\s+egg', r'\bfried\s+eggs', r'\bfried\s+eeg', r'\bfried\s+eegs', r'\bfried\s+eg', r'\bfried\s+egs',
                    r'\bscrambled\s+egg', r'\bscrambled\s+eggs', r'\bscrambled\s+eeg', r'\bscrambled\s+eegs', r'\bscrambled\s+eg', r'\bscrambled\s+egs',
                    r'\bboiled\s+egg', r'\bboiled\s+eggs', r'\bboiled\s+eeg', r'\bboiled\s+eegs', r'\bboiled\s+eg', r'\bboiled\s+egs',
                    r'\bhard\s+boiled\s+egg', r'\bhard\s+boiled\s+eggs',
                    r'\bsoft\s+boiled\s+egg', r'\bsoft\s+boiled\s+eggs',
                    r'\btoast\s+with\s+eg', r'\btoast\s+with\s+egs',  # "toast with eg"
                ]
                
                for pattern in egg_variations:
                    if re.search(pattern, text_lower):
                        # Make sure it's not "eggplant" or "eggshell"
                        if 'eggplant' not in text_lower and 'eggshell' not in text_lower:
                            return True
                
                # Also check if the text is just "egg" or "eggs" (possibly with numbers or punctuation), including typos and shortened forms
                if text_lower in ['egg', 'eggs', 'eeg', 'eegs', 'eg', 'egs'] or re.match(r'^(egg|eggs|eeg|eegs|eg|egs)[\s\-,\d\.]*$', text_lower):
                    # Make sure it's not part of other words like "vegetable", "leg", "beg", "eggplant", "eggshell"
                    if 'eggplant' not in text_lower and 'eggshell' not in text_lower and 'vegetable' not in text_lower and 'leg' not in text_lower and 'beg' not in text_lower:
                        return True
                
                # Check for patterns like "eeg - 1 large" or "egg - 1 large" or "eg - 1" (with typo or shortened)
                # This includes patterns with spaces: "egg - 1", "egg - 1 large", "eggs - 3 large"
                if re.search(r'\b(eeg|egg|eg|eggs|egs)\s*-\s*\d+', text_lower, re.IGNORECASE):
                    if 'eggplant' not in text_lower and 'eggshell' not in text_lower and 'vegetable' not in text_lower and 'leg' not in text_lower and 'beg' not in text_lower:
                        return True
                
                # Check for "egg-1" (no spaces) or "egg1" or "eg-1" patterns
                if re.search(r'\b(eeg|egg|eg|eggs|egs)\s*-\s*\d+|\b(eeg|egg|eg|eggs|egs)\d+', text_lower, re.IGNORECASE):
                    if 'eggplant' not in text_lower and 'eggshell' not in text_lower and 'vegetable' not in text_lower and 'leg' not in text_lower and 'beg' not in text_lower:
                        return True
                
                # Specifically check for patterns like "egg - 1 large", "eggs - 3 large" (with word after number)
                # This is a critical check - must catch "egg - 1 large" exactly
                if re.search(r'\b(eeg|egg|eg|eggs|egs)\s*-\s*\d+\s+\w+', text_lower, re.IGNORECASE):
                    if 'eggplant' not in text_lower and 'eggshell' not in text_lower:
                        print(f"DEBUG: contains_animal_product matched pattern 'egg - N word': '{text_lower}'")
                        return True
                
                # Check for patterns without hyphen: "egg 1 large", "eggs 3 large"
                if re.search(r'\b(eeg|egg|eg|eggs|egs)\s+\d+\s+\w+', text_lower, re.IGNORECASE):
                    if 'eggplant' not in text_lower and 'eggshell' not in text_lower:
                        print(f"DEBUG: contains_animal_product matched pattern 'egg N word': '{text_lower}'")
                        return True
                
                # Additional check: if text contains "egg" or "eggs" followed by "-" and a number, it's likely an egg
                if re.search(r'\b(eeg|egg|eg|eggs|egs)\s*-\s*\d', text_lower, re.IGNORECASE):
                    if 'eggplant' not in text_lower and 'eggshell' not in text_lower:
                        print(f"DEBUG: contains_animal_product matched pattern 'egg - N': '{text_lower}'")
                        return True
                
                # Check for compound phrases like "poached egg", "fried egg", "toast with eg", etc.
                if re.search(r'\b(poached|fried|scrambled|boiled|hard\s+boiled|soft\s+boiled|sunny\s+side\s+up|over\s+easy|raw|whole|toast\s+with)\s+(eeg|egg|eg)', text_lower, re.IGNORECASE):
                    if 'eggplant' not in text_lower and 'eggshell' not in text_lower:
                        return True
                
                # FINAL CATCH-ALL: If text contains "egg" or "eggs" anywhere (as a word), and it's not "eggplant" or "eggshell", flag it
                # This catches any remaining cases we might have missed
                if re.search(r'\b(eeg|egg|eg|eggs|egs)\b', text_lower):
                    if 'eggplant' not in text_lower and 'eggshell' not in text_lower:
                        # Additional check: if it's followed by a hyphen and number, definitely an egg
                        if re.search(r'\b(eeg|egg|eg|eggs|egs)\s*-\s*\d', text_lower):
                            print(f"DEBUG: contains_animal_product FINAL CATCH-ALL MATCH: '{text_lower}'")
                            return True
                        # Or if it's a standalone word (not part of another word)
                        if text_lower in ['egg', 'eggs', 'eeg', 'eegs', 'eg', 'egs']:
                            print(f"DEBUG: contains_animal_product FINAL CATCH-ALL MATCH (standalone): '{text_lower}'")
                            return True
                    
                return False
            
            # Filter ingredients - multiple passes to be thorough
            if "ingredients" in recipe_data:
                original_ingredients = recipe_data["ingredients"].copy()
                original_count = len(recipe_data["ingredients"])
                
                # Filter ingredients - check all fields thoroughly
                filtered_ingredients = []
                for ing in recipe_data["ingredients"]:
                    ing_name = str(ing.get("name", "")).strip()
                    ing_amount = str(ing.get("amount", "")).strip()
                    ing_unit = str(ing.get("unit", "")).strip()
                    
                    # Create multiple string combinations to check
                    full_ing_str = f"{ing_name} {ing_amount} {ing_unit}".strip()
                    alt_ing_str = f"{ing_name}-{ing_amount} {ing_unit}".strip()
                    alt_ing_str2 = f"{ing_name} - {ing_amount} {ing_unit}".strip()
                    # Also check with amount and unit swapped positions
                    alt_ing_str3 = f"{ing_name} {ing_unit} {ing_amount}".strip()
                    alt_ing_str4 = f"{ing_name} - {ing_amount} - {ing_unit}".strip()
                    alt_ing_str5 = f"{ing_name}-{ing_amount}-{ing_unit}".strip()
                    
                    # Debug: print what we're checking
                    print(f"DEBUG: Checking ingredient: name='{ing_name}', amount='{ing_amount}', unit='{ing_unit}'")
                    print(f"DEBUG: Full string: '{full_ing_str}'")
                    
                    # Check all fields and combinations - be very aggressive
                    name_check = contains_animal_product(ing_name)
                    amount_check = contains_animal_product(ing_amount)
                    unit_check = contains_animal_product(ing_unit)
                    full_check = contains_animal_product(full_ing_str)
                    alt1_check = contains_animal_product(alt_ing_str)
                    alt2_check = contains_animal_product(alt_ing_str2)
                    alt3_check = contains_animal_product(alt_ing_str3)
                    alt4_check = contains_animal_product(alt_ing_str4)
                    alt5_check = contains_animal_product(alt_ing_str5)
                    
                    if (not name_check and 
                        not amount_check and 
                        not unit_check and
                        not full_check and
                        not alt1_check and
                        not alt2_check and
                        not alt3_check and
                        not alt4_check and
                        not alt5_check):
                        filtered_ingredients.append(ing)
                    else:
                        print(f"DEBUG: Removed non-vegan ingredient: {ing.get('name')}")
                        print(f"DEBUG:   name_check={name_check}, amount_check={amount_check}, unit_check={unit_check}")
                        print(f"DEBUG:   full_check={full_check}, alt1_check={alt1_check}, alt2_check={alt2_check}")
                        print(f"DEBUG:   alt3_check={alt3_check}, alt4_check={alt4_check}, alt5_check={alt5_check}")
                        print(f"DEBUG:   Full string was: '{full_ing_str}'")
                
                recipe_data["ingredients"] = filtered_ingredients
                removed_count = original_count - len(recipe_data["ingredients"])
                
                # If we removed egg ingredients and the recipe name/instructions mention tofu, add tofu to ingredients
                removed_names = [ing.get("name") for ing in original_ingredients if ing not in filtered_ingredients]
                egg_removed = any(contains_animal_product(str(ing.get("name", ""))) for ing in original_ingredients if ing not in filtered_ingredients)
                
                if removed_count > 0:
                    print(f"DEBUG: Removed {removed_count} non-vegan ingredient(s) from recipe")
                    print(f"DEBUG: Removed ingredients: {removed_names}")
                
                # Store flag for later use (after name/instructions are filtered)
                recipe_data["_egg_removed"] = egg_removed
                
                recipe_data["ingredients"] = filtered_ingredients
            
            # Filter recipe name - replace animal product mentions
            if "name" in recipe_data:
                recipe_name = str(recipe_data.get("name", "")).strip()
                original_name = recipe_name
                
                if contains_animal_product(recipe_name):
                    print(f"DEBUG: Recipe name contains animal products: '{recipe_name}'")
                    # Replace common egg phrases in recipe names
                    recipe_name = re.sub(r'\bpoached\s+egg\b', 'poached tofu', recipe_name, flags=re.IGNORECASE)
                    recipe_name = re.sub(r'\bpoached\s+eggs\b', 'poached tofu', recipe_name, flags=re.IGNORECASE)
                    recipe_name = re.sub(r'\bpoached\s+eeg\b', 'poached tofu', recipe_name, flags=re.IGNORECASE)
                    recipe_name = re.sub(r'\bpoached\s+eegs\b', 'poached tofu', recipe_name, flags=re.IGNORECASE)
                    recipe_name = re.sub(r'\bpoached\s+eg\b', 'poached tofu', recipe_name, flags=re.IGNORECASE)
                    recipe_name = re.sub(r'\bpoached\s+egs\b', 'poached tofu', recipe_name, flags=re.IGNORECASE)
                    recipe_name = re.sub(r'\bfried\s+egg\b', 'fried tofu', recipe_name, flags=re.IGNORECASE)
                    recipe_name = re.sub(r'\bfried\s+eggs\b', 'fried tofu', recipe_name, flags=re.IGNORECASE)
                    recipe_name = re.sub(r'\bscrambled\s+egg\b', 'scrambled tofu', recipe_name, flags=re.IGNORECASE)
                    recipe_name = re.sub(r'\bscrambled\s+eggs\b', 'scrambled tofu', recipe_name, flags=re.IGNORECASE)
                    recipe_name = re.sub(r'\btoast\s+with\s+eg\b', 'toast with tofu', recipe_name, flags=re.IGNORECASE)
                    recipe_name = re.sub(r'\btoast\s+with\s+egs\b', 'toast with tofu', recipe_name, flags=re.IGNORECASE)
                    recipe_name = re.sub(r'\btoast\s+with\s+egg\b', 'toast with tofu', recipe_name, flags=re.IGNORECASE)
                    recipe_name = re.sub(r'\btoast\s+with\s+eggs\b', 'toast with tofu', recipe_name, flags=re.IGNORECASE)
                    # Generic egg replacements
                    recipe_name = re.sub(r'\begg\b', 'tofu', recipe_name, flags=re.IGNORECASE)
                    recipe_name = re.sub(r'\beggs\b', 'tofu', recipe_name, flags=re.IGNORECASE)
                    recipe_name = re.sub(r'\beeg\b', 'tofu', recipe_name, flags=re.IGNORECASE)
                    recipe_name = re.sub(r'\beegs\b', 'tofu', recipe_name, flags=re.IGNORECASE)
                    recipe_name = re.sub(r'\beg\b', 'tofu', recipe_name, flags=re.IGNORECASE)
                    recipe_name = re.sub(r'\begs\b', 'tofu', recipe_name, flags=re.IGNORECASE)
                    
                    # Make sure we didn't create "eggplant" or "eggshell"
                    recipe_name = recipe_name.replace('tofuplant', 'eggplant').replace('tofushell', 'eggshell')
                    
                    recipe_data["name"] = recipe_name
                    print(f"DEBUG: Updated recipe name from '{original_name}' to '{recipe_name}'")
            
            # Filter instructions - replace animal product mentions
            if "instructions" in recipe_data:
                filtered_instructions = []
                for inst in recipe_data["instructions"]:
                    inst_str = str(inst)
                    original_inst = inst_str
                    
                    if contains_animal_product(inst_str):
                        # Replace common egg phrases in instructions
                        inst_str = re.sub(r'\bpoached\s+egg\b', 'poached tofu', inst_str, flags=re.IGNORECASE)
                        inst_str = re.sub(r'\bpoached\s+eggs\b', 'poached tofu', inst_str, flags=re.IGNORECASE)
                        inst_str = re.sub(r'\bpoached\s+eeg\b', 'poached tofu', inst_str, flags=re.IGNORECASE)
                        inst_str = re.sub(r'\bpoached\s+eegs\b', 'poached tofu', inst_str, flags=re.IGNORECASE)
                        inst_str = re.sub(r'\bpoached\s+eg\b', 'poached tofu', inst_str, flags=re.IGNORECASE)
                        inst_str = re.sub(r'\bpoached\s+egs\b', 'poached tofu', inst_str, flags=re.IGNORECASE)
                        inst_str = re.sub(r'\bfried\s+egg\b', 'fried tofu', inst_str, flags=re.IGNORECASE)
                        inst_str = re.sub(r'\bfried\s+eggs\b', 'fried tofu', inst_str, flags=re.IGNORECASE)
                        inst_str = re.sub(r'\bscrambled\s+egg\b', 'scrambled tofu', inst_str, flags=re.IGNORECASE)
                        inst_str = re.sub(r'\bscrambled\s+eggs\b', 'scrambled tofu', inst_str, flags=re.IGNORECASE)
                        inst_str = re.sub(r'\bboiled\s+egg\b', 'boiled tofu', inst_str, flags=re.IGNORECASE)
                        inst_str = re.sub(r'\bboiled\s+eggs\b', 'boiled tofu', inst_str, flags=re.IGNORECASE)
                        inst_str = re.sub(r'\btoast\s+with\s+eg\b', 'toast with tofu', inst_str, flags=re.IGNORECASE)
                        inst_str = re.sub(r'\btoast\s+with\s+egs\b', 'toast with tofu', inst_str, flags=re.IGNORECASE)
                        inst_str = re.sub(r'\btoast\s+with\s+egg\b', 'toast with tofu', inst_str, flags=re.IGNORECASE)
                        inst_str = re.sub(r'\btoast\s+with\s+eggs\b', 'toast with tofu', inst_str, flags=re.IGNORECASE)
                        # Generic egg replacements
                        inst_str = re.sub(r'\begg\b', 'tofu', inst_str, flags=re.IGNORECASE)
                        inst_str = re.sub(r'\beggs\b', 'tofu', inst_str, flags=re.IGNORECASE)
                        inst_str = re.sub(r'\beeg\b', 'tofu', inst_str, flags=re.IGNORECASE)
                        inst_str = re.sub(r'\beegs\b', 'tofu', inst_str, flags=re.IGNORECASE)
                        inst_str = re.sub(r'\beg\b', 'tofu', inst_str, flags=re.IGNORECASE)
                        inst_str = re.sub(r'\begs\b', 'tofu', inst_str, flags=re.IGNORECASE)
                        # Replace "egg - 1", "eggs - 3" patterns
                        inst_str = re.sub(r'\begg\s*-\s*\d+', 'tofu', inst_str, flags=re.IGNORECASE)
                        inst_str = re.sub(r'\beggs\s*-\s*\d+', 'tofu', inst_str, flags=re.IGNORECASE)
                        inst_str = re.sub(r'\beeg\s*-\s*\d+', 'tofu', inst_str, flags=re.IGNORECASE)
                        inst_str = re.sub(r'\beegs\s*-\s*\d+', 'tofu', inst_str, flags=re.IGNORECASE)
                        inst_str = re.sub(r'\beg\s*-\s*\d+', 'tofu', inst_str, flags=re.IGNORECASE)
                        inst_str = re.sub(r'\begs\s*-\s*\d+', 'tofu', inst_str, flags=re.IGNORECASE)
                        
                        # Make sure we didn't create "eggplant" or "eggshell"
                        inst_str = inst_str.replace('tofuplant', 'eggplant').replace('tofushell', 'eggshell')
                        
                        # Remove other animal products (not eggs, which we already handled)
                        for pattern in animal_patterns:
                            if pattern not in [r'\begg\b', r'\beggs\b', r'\beeg\b', r'\beegs\b', r'\beg\b', r'\begs\b']:  # Skip egg patterns we already handled
                                inst_str = re.sub(pattern, "[removed - non-vegan]", inst_str, flags=re.IGNORECASE)
                    
                    if inst_str.strip() and inst_str.strip() != "[removed - non-vegan]":
                        filtered_instructions.append(inst_str)
                    elif original_inst.strip():
                        print(f"DEBUG: Removed instruction containing animal products: {original_inst[:100]}")
                
                recipe_data["instructions"] = filtered_instructions
        
        # Calculate nutrition if not provided or incomplete
        if ("nutrition_estimate" not in recipe_data or 
            not recipe_data.get("nutrition_estimate") or 
            not recipe_data["nutrition_estimate"].get("calories_per_serving")):
            print("DEBUG: Calculating nutrition from ingredients")
            calculated_nutrition = await calculate_nutrition(recipe_data)
            if "nutrition_estimate" not in recipe_data:
                recipe_data["nutrition_estimate"] = {}
            recipe_data["nutrition_estimate"].update(calculated_nutrition)
        
        recipe_id = str(uuid.uuid4())
        recipe_data["recipe_id"] = recipe_id
        recipe_data["created_at"] = datetime.now().isoformat()
        
        # Always try to generate image (with fallback to Unsplash)
        try:
            image_url = await generate_recipe_image(
                recipe_data.get("name", ""),
                recipe_data.get("description", "")
            )
            if image_url:
                recipe_data["image_url"] = image_url
                print(f"DEBUG: Generated image URL for recipe: {image_url[:50]}...")
        except Exception as e:
            print(f"Image generation failed (non-blocking): {e}")
        
        recipes_storage[recipe_id] = recipe_data
        
        return recipe_data
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error generating recipe: {str(e)}")


@app.post("/api/generate-meal-plan")
async def generate_meal_plan(request: MealPlanRequest):
    """Generate a weekly meal plan"""
    try:
        # Build calorie instruction
        if request.target_calories:
            breakfast_cals = int(request.target_calories * 0.25)
            lunch_cals = int(request.target_calories * 0.35)
            dinner_cals = int(request.target_calories * 0.35)
            snack_cals = int(request.target_calories * 0.05) if request.meals_per_day == 4 else 0
            
            calorie_instruction = f"""TARGET CALORIES PER DAY: {request.target_calories} calories.

CRITICAL: The SUM of ALL meals per day MUST equal EXACTLY {request.target_calories} calories (±50 calories tolerance).
- Breakfast: ~{breakfast_cals} calories
- Lunch: ~{lunch_cals} calories
- Dinner: ~{dinner_cals} calories
{f"- Snack: ~{snack_cals} calories" if request.meals_per_day == 4 else ""}

IMPORTANT: Adjust serving sizes and ingredient amounts to meet calorie targets. Increase serving sizes if calories are too low."""
        else:
            calorie_instruction = "No specific calorie target."
        
        # Build dietary restrictions text
        dietary_restrictions = ""
        if request.dietary_preferences:
            restrictions = []
            if "vegan" in request.dietary_preferences:
                restrictions.append("⚠️ CRITICAL VEGAN RESTRICTIONS - ABSOLUTELY MANDATORY ⚠️\nNO animal products are allowed. DO NOT use ANY of the following:\n- Meat: chicken, beef, pork, lamb, turkey, duck, etc.\n- Seafood: fish, shrimp, crab, lobster, tuna, salmon, etc.\n- Dairy: milk, cheese, butter, yogurt, cream, sour cream, etc.\n- Eggs: NO eggs in any form (whole eggs, egg whites, egg yolks)\n- Honey: NO honey\n- Any other animal-derived ingredients\n\nMUST USE plant-based alternatives:\n- Plant milk (almond milk, soy milk, oat milk, coconut milk)\n- Vegan cheese, vegan butter\n- Tofu, tempeh, legumes for protein\n- Nutritional yeast, plant-based proteins")
            if "vegetarian" in request.dietary_preferences and "vegan" not in request.dietary_preferences:
                restrictions.append("CRITICAL VEGETARIAN RESTRICTIONS: NO meat, poultry, or seafood allowed. DO NOT use: chicken, beef, pork, fish, seafood, or any meat products. Dairy and eggs are allowed.")
            if "gluten-free" in request.dietary_preferences:
                restrictions.append("CRITICAL GLUTEN-FREE RESTRICTIONS: NO wheat, barley, rye, or gluten-containing ingredients. Use gluten-free alternatives (rice, quinoa, gluten-free pasta, etc.).")
            if "dairy-free" in request.dietary_preferences:
                restrictions.append("CRITICAL DAIRY-FREE RESTRICTIONS: NO dairy products allowed. DO NOT use: milk, cheese, butter, yogurt, cream, or any dairy products. Use dairy-free alternatives.")
            if "low-carb" in request.dietary_preferences:
                restrictions.append("CRITICAL LOW-CARB RESTRICTIONS: Minimize carbohydrates. Avoid or limit: bread, pasta, rice, potatoes, sugar, and high-carb foods.")
            if "keto" in request.dietary_preferences:
                restrictions.append("CRITICAL KETO RESTRICTIONS: Very low carbohydrates (under 20g net carbs per serving). NO: bread, pasta, rice, potatoes, sugar, grains, or high-carb foods. Focus on: meat, fish, eggs, low-carb vegetables, healthy fats.")
            
            if restrictions:
                dietary_restrictions = "\n".join(restrictions) + "\n"
        
        prompt = MEAL_PLAN_TEMPLATE.format(
            days=request.days,
            dietary_preferences=", ".join(request.dietary_preferences) if request.dietary_preferences else "None",
            dietary_restrictions=dietary_restrictions,
            calorie_instruction=calorie_instruction,
            meals_per_day=request.meals_per_day
        )
        
        print(f"DEBUG: Generating meal plan - Days: {request.days}, Meals per day: {request.meals_per_day}")
        
        # Cap days at 3 to ensure reliable responses (4+ day plans often get truncated or malformed JSON)
        if request.days > 3:
            raise HTTPException(
                status_code=400,
                detail=f"Maximum 3 days supported for reliable meal plan generation. You requested {request.days} days. Please reduce to 1-3 days. For longer plans, generate multiple shorter plans separately."
            )
        
        # For plans with 3 days, use a slightly more concise format
        if request.days == 3:
            # Use minimal detail but ensure we get useful instructions
            # Build calorie instruction for 3-day plans
            if request.target_calories:
                breakfast_cals = int(request.target_calories * 0.25)
                lunch_cals = int(request.target_calories * 0.35)
                dinner_cals = int(request.target_calories * 0.35)
                snack_cals = int(request.target_calories * 0.05) if request.meals_per_day == 4 else 0
                
                calorie_instruction = f"""TARGET CALORIES PER DAY: {request.target_calories} calories.

CRITICAL CALORIE REQUIREMENTS:
- The SUM of ALL meals per day MUST equal EXACTLY {request.target_calories} calories (±50 calories tolerance)
- Breakfast: approximately {breakfast_cals} calories
- Lunch: approximately {lunch_cals} calories  
- Dinner: approximately {dinner_cals} calories
{f"- Snack: approximately {snack_cals} calories" if request.meals_per_day == 4 else ""}
- Total per day: {request.target_calories} calories (breakfast + lunch + dinner{f" + snack" if request.meals_per_day == 4 else ""})

IMPORTANT: Adjust serving sizes and ingredient amounts to meet these calorie targets. If calories are too low, increase serving sizes (e.g., use 1.5 cups instead of 1 cup, or 2 servings instead of 1) or add more calorie-dense ingredients. If calories are too high, reduce serving sizes."""
            else:
                calorie_instruction = "No specific calorie target."
            
            prompt = f"""Create {request.days}-day meal plan with EXACTLY {request.meals_per_day} meals per day.

Dietary: {", ".join(request.dietary_preferences) if request.dietary_preferences else "Any"}
{calorie_instruction}

CRITICAL: Generate ALL {request.days} days. Each day MUST have EXACTLY {request.meals_per_day} meals (breakfast, lunch, dinner, and snack if 4 meals). Each meal needs 3-4 detailed instruction steps and 4-6 ingredients.

IMPORTANT: Instructions must be DETAILED and SPECIFIC with actions, temperatures, times, and preparation details. Keep each instruction step concise but informative. Avoid vague instructions like "assemble" or "serve" without context.

JSON:
{{
    "days": [
        {{
            "day": 1,
            "meals": [
                {{
                    "meal_type": "breakfast",
                    "name": "Oatmeal with Berries",
                    "description": "Healthy breakfast",
                    "estimated_calories": 250,
                    "prep_time_minutes": 5,
                    "cook_time_minutes": 10,
                    "servings": 1,
                    "ingredients": [
                        {{"name": "rolled oats", "amount": "1/2", "unit": "cup"}},
                        {{"name": "milk", "amount": "1", "unit": "cup"}},
                        {{"name": "berries", "amount": "1/2", "unit": "cup"}},
                        {{"name": "honey", "amount": "1", "unit": "tbsp"}}
                    ],
                    "instructions": [
                        "Pour milk into a medium saucepan and heat over medium heat until it begins to simmer (small bubbles form around the edges)",
                        "Stir in the rolled oats and reduce heat to low. Cook for 5-7 minutes, stirring occasionally, until the oats are tender and the mixture has thickened",
                        "Remove the saucepan from heat and let the oatmeal stand for 2 minutes to allow it to thicken further",
                        "Transfer to a bowl, top with fresh berries and drizzle with honey, then serve immediately while warm"
                    ]
                }},
                {{
                    "meal_type": "lunch",
                    "name": "Grilled Chicken Salad",
                    "description": "Healthy lunch",
                    "estimated_calories": 400,
                    "prep_time_minutes": 10,
                    "cook_time_minutes": 15,
                    "servings": 1,
                    "ingredients": [
                        {{"name": "chicken breast", "amount": "1", "unit": "piece"}},
                        {{"name": "lettuce", "amount": "2", "unit": "cups"}},
                        {{"name": "tomato", "amount": "1", "unit": "medium"}},
                        {{"name": "olive oil", "amount": "1", "unit": "tbsp"}}
                    ],
                    "instructions": [
                        "Season the chicken breast with salt, pepper, and your preferred herbs. Preheat a grill or grill pan over medium-high heat. Grill the chicken for 6-7 minutes per side, or until the internal temperature reaches 165°F and the chicken is no longer pink",
                        "While the chicken is cooking, wash and dry the lettuce, then chop it into bite-sized pieces. Dice the tomato into small cubes",
                        "Let the grilled chicken rest for 2-3 minutes, then slice it into strips. Arrange the lettuce and tomato on a plate",
                        "Drizzle the salad with olive oil, top with the sliced chicken, and serve immediately"
                    ]
                }},
                {{
                    "meal_type": "dinner",
                    "name": "Pasta with Marinara",
                    "description": "Classic dinner",
                    "estimated_calories": 500,
                    "prep_time_minutes": 5,
                    "cook_time_minutes": 20,
                    "servings": 1,
                    "ingredients": [
                        {{"name": "pasta", "amount": "2", "unit": "oz"}},
                        {{"name": "marinara sauce", "amount": "1/2", "unit": "cup"}},
                        {{"name": "garlic", "amount": "2", "unit": "cloves"}},
                        {{"name": "parmesan", "amount": "2", "unit": "tbsp"}}
                    ],
                    "instructions": [
                        "Bring a large pot of salted water to a rolling boil over high heat. Add the pasta and cook according to package directions (usually 8-12 minutes) until al dente, stirring occasionally",
                        "While the pasta is cooking, mince the garlic cloves. Heat the marinara sauce in a small saucepan over medium heat, add the minced garlic, and stir occasionally until warmed through (about 5 minutes)",
                        "Drain the cooked pasta, reserving 1-2 tablespoons of pasta water. Return the pasta to the pot, add the warm marinara sauce and reserved pasta water, and toss to combine",
                        "Transfer to a serving bowl, top with grated parmesan cheese, and serve immediately"
                    ]
                }}
            ]
        }}
    ]
}}

CRITICAL: Each day MUST have EXACTLY {request.meals_per_day} meals. Return ALL {request.days} days. Return ONLY JSON."""
            system_prompt = "You are a meal planning expert. Return ONLY valid JSON. Generate ALL requested days with EXACTLY the requested meals per day. Provide 3-4 detailed instruction steps per meal with specific actions, temperatures, times, and preparation details. Keep instructions concise but informative. Avoid vague instructions."
        else:
            # Use normal prompt for shorter plans
            # Build calorie instruction
            if request.target_calories:
                calorie_instruction = f"TARGET CALORIES PER DAY: {request.target_calories} calories. The SUM of all meals per day MUST equal approximately {request.target_calories} calories (±100 calories). Distribute calories appropriately across meals."
            else:
                calorie_instruction = "No specific calorie target."
            
            # Build dietary restrictions for shorter plans
            dietary_restrictions_short = ""
            if request.dietary_preferences:
                restrictions = []
                if "vegan" in request.dietary_preferences:
                    restrictions.append("⚠️ CRITICAL VEGAN RESTRICTIONS - ABSOLUTELY MANDATORY ⚠️\nNO animal products are allowed. DO NOT use ANY of the following:\n- Meat: chicken, beef, pork, lamb, turkey, duck, etc.\n- Seafood: fish, shrimp, crab, lobster, tuna, salmon, etc.\n- Dairy: milk, cheese, butter, yogurt, cream, sour cream, etc.\n- Eggs: NO eggs in any form (whole eggs, egg whites, egg yolks)\n- Honey: NO honey\n- Any other animal-derived ingredients\n\nMUST USE plant-based alternatives:\n- Plant milk (almond milk, soy milk, oat milk, coconut milk)\n- Vegan cheese, vegan butter\n- Tofu, tempeh, legumes for protein\n- Nutritional yeast, plant-based proteins")
                if "vegetarian" in request.dietary_preferences and "vegan" not in request.dietary_preferences:
                    restrictions.append("CRITICAL VEGETARIAN RESTRICTIONS: NO meat, poultry, or seafood allowed. DO NOT use: chicken, beef, pork, fish, seafood, or any meat products. Dairy and eggs are allowed.")
                if "gluten-free" in request.dietary_preferences:
                    restrictions.append("CRITICAL GLUTEN-FREE RESTRICTIONS: NO wheat, barley, rye, or gluten-containing ingredients. Use gluten-free alternatives (rice, quinoa, gluten-free pasta, etc.).")
                if "dairy-free" in request.dietary_preferences:
                    restrictions.append("CRITICAL DAIRY-FREE RESTRICTIONS: NO dairy products allowed. DO NOT use: milk, cheese, butter, yogurt, cream, or any dairy products. Use dairy-free alternatives.")
                if "low-carb" in request.dietary_preferences:
                    restrictions.append("CRITICAL LOW-CARB RESTRICTIONS: Minimize carbohydrates. Avoid or limit: bread, pasta, rice, potatoes, sugar, and high-carb foods.")
                if "keto" in request.dietary_preferences:
                    restrictions.append("CRITICAL KETO RESTRICTIONS: Very low carbohydrates (under 20g net carbs per serving). NO: bread, pasta, rice, potatoes, sugar, grains, or high-carb foods. Focus on: meat, fish, eggs, low-carb vegetables, healthy fats.")
                
                if restrictions:
                    dietary_restrictions_short = "\n".join(restrictions) + "\n"
            
            prompt = MEAL_PLAN_TEMPLATE.format(
                days=request.days,
                dietary_preferences=", ".join(request.dietary_preferences) if request.dietary_preferences else "None",
                dietary_restrictions=dietary_restrictions_short,
                calorie_instruction=calorie_instruction,
                meals_per_day=request.meals_per_day
            )
            system_prompt = "You are a meal planning expert. Return ONLY valid JSON. Provide detailed, step-by-step instructions with specific actions, temperatures, times, and preparation details. Avoid vague instructions like 'assemble' or 'serve' without context."
        
        # Calculate tokens based on plan size
        # With detailed instructions, each meal needs more tokens
        if request.days == 3:
            # For 3-day plans, detailed instructions mean ~350 tokens per meal
            estimated_tokens_needed = request.days * request.meals_per_day * 350
        elif request.days == 2:
            estimated_tokens_needed = request.days * request.meals_per_day * 320
        else:
            estimated_tokens_needed = request.days * request.meals_per_day * 300
        
        if request.days == 3:
            max_tokens = max(3800, estimated_tokens_needed + 800)  # Use high cap for 3-day plans
        elif request.days == 2:
            max_tokens = max(3600, estimated_tokens_needed + 700)
        else:
            max_tokens = max(3500, estimated_tokens_needed + 700)
        
        # Cap at 4000 to avoid API errors (enforced in call_together_ai)
        max_tokens = min(max_tokens, 4000)
        print(f"DEBUG: Calculated max_tokens: {max_tokens} (estimated needed: {estimated_tokens_needed})")
        
        try:
            llm_response = await call_together_ai(
                prompt,
                system_prompt=system_prompt,
                max_tokens=max_tokens
            )
        except HTTPException as he:
            # Re-raise HTTP exceptions as-is
            raise he
        except Exception as e:
            error_msg = f"Failed to call AI service: {str(e)}"
            print(f"DEBUG: Error calling LLM: {error_msg}")
            import traceback
            traceback.print_exc()
            raise HTTPException(status_code=500, detail=error_msg)
        
        print(f"DEBUG: Received LLM response ({len(llm_response)} chars)")
        print(f"DEBUG: Response preview: {llm_response[:500]}")
        print(f"DEBUG: Response ending: {llm_response[-500:]}")
        
        # Pre-check: If "days" exists in response, we MUST extract it, not an ingredient object
        has_days_in_response = '"days"' in llm_response or "'days'" in llm_response
        print(f"DEBUG: Response contains 'days' key: {has_days_in_response}")
        
        # If response starts with { and contains "days", try extracting from the very beginning first
        if has_days_in_response and llm_response.strip().startswith('{'):
            print(f"DEBUG: Response starts with {{ and contains 'days', trying direct extraction from start...")
            try:
                # Find the matching closing brace from the start
                brace_count = 0
                in_string = False
                escape_next = False
                end_pos = -1
                
                for i in range(len(llm_response)):
                    char = llm_response[i]
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
                        if char == '{':
                            brace_count += 1
                        elif char == '}':
                            brace_count -= 1
                            if brace_count == 0:
                                end_pos = i + 1
                                break
                
                if end_pos > 0:
                    root_obj_str = llm_response[:end_pos]
                    root_obj = json.loads(root_obj_str)
                    if "days" in root_obj:
                        print(f"DEBUG: Successfully extracted root object with 'days' from start!")
                        plan_data = root_obj
                    else:
                        print(f"DEBUG: Root object doesn't have 'days', falling back to normal extraction")
                        plan_data = extract_json_from_response(llm_response)
                else:
                    print(f"DEBUG: Could not find matching closing brace, falling back to normal extraction")
                    plan_data = extract_json_from_response(llm_response)
            except Exception as direct_extract_error:
                print(f"DEBUG: Direct extraction failed: {direct_extract_error}, falling back to normal extraction")
                plan_data = extract_json_from_response(llm_response            )
        else:
            # Try to parse JSON first - if it succeeds, the response is complete regardless of length
            plan_data = extract_json_from_response(llm_response)
        
        print(f"DEBUG: Successfully parsed meal plan data")
        print(f"DEBUG: Plan data keys: {list(plan_data.keys()) if isinstance(plan_data, dict) else 'Not a dict'}")
        print(f"DEBUG: Plan data type: {type(plan_data)}")
        
        # CRITICAL: Check if we extracted an ingredient object instead of meal plan
        # This must happen BEFORE the has_days_in_response check
        if isinstance(plan_data, dict):
            has_ingredient_keys = any(key in plan_data for key in ['name', 'amount', 'unit'])
            has_meal_keys = any(key in plan_data for key in ['meals', 'days'])
            
            # If it looks like an ingredient object but "days" exists in the response, force re-extraction
            if has_ingredient_keys and not has_meal_keys and ('"days"' in llm_response or "'days'" in llm_response):
                print(f"DEBUG: CRITICAL - Extracted ingredient object but 'days' exists in response. Forcing root object extraction...")
                print(f"DEBUG: Ingredient object keys: {list(plan_data.keys())}")
                
                # ALWAYS extract from the first { in the response - this should be the root object
                first_brace = llm_response.find('{')
                if first_brace != -1:
                    print(f"DEBUG: Extracting root object from first {{ at position {first_brace}...")
                    brace_count = 0
                    in_str = False
                    escape = False
                    end_brace = -1
                    
                    for i in range(first_brace, len(llm_response)):
                        c = llm_response[i]
                        if escape:
                            escape = False
                            continue
                        if c == '\\':
                            escape = True
                            continue
                        if c == '"' and not escape:
                            in_str = not in_str
                            continue
                        if not in_str:
                            if c == '{':
                                brace_count += 1
                            elif c == '}':
                                brace_count -= 1
                                if brace_count == 0:
                                    end_brace = i + 1
                                    break
                    
                    if end_brace > first_brace:
                        try:
                            root_text = llm_response[first_brace:end_brace]
                            print(f"DEBUG: Extracted {len(root_text)} chars from first {{")
                            root_parsed = json.loads(root_text)
                            if isinstance(root_parsed, dict) and "days" in root_parsed:
                                print(f"DEBUG: SUCCESS - First {{ extraction found 'days' key!")
                                plan_data = root_parsed
                            else:
                                print(f"DEBUG: First {{ object doesn't have 'days'. Keys: {list(root_parsed.keys())[:10] if isinstance(root_parsed, dict) else 'Not a dict'}")
                                # If first { doesn't have days, try searching backwards from "days"
                                days_pos = llm_response.find('"days"')
                                if days_pos == -1:
                                    days_pos = llm_response.find("'days'")
                                
                                if days_pos != -1 and days_pos > first_brace:
                                    print(f"DEBUG: Searching backwards from 'days' at position {days_pos}...")
                                    # Find the outermost { before "days"
                                    for search_pos in range(max(0, days_pos - 10000), days_pos):
                                        if llm_response[search_pos] == '{':
                                            # Try extracting from this position
                                            brace_count2 = 0
                                            in_str2 = False
                                            escape2 = False
                                            end_brace2 = -1
                                            
                                            for j in range(search_pos, len(llm_response)):
                                                c2 = llm_response[j]
                                                if escape2:
                                                    escape2 = False
                                                    continue
                                                if c2 == '\\':
                                                    escape2 = True
                                                    continue
                                                if c2 == '"' and not escape2:
                                                    in_str2 = not in_str2
                                                    continue
                                                if not in_str2:
                                                    if c2 == '{':
                                                        brace_count2 += 1
                                                    elif c2 == '}':
                                                        brace_count2 -= 1
                                                        if brace_count2 == 0:
                                                            end_brace2 = j + 1
                                                            break
                                            
                                            if end_brace2 > search_pos:
                                                try:
                                                    alt_text = llm_response[search_pos:end_brace2]
                                                    alt_parsed = json.loads(alt_text)
                                                    if isinstance(alt_parsed, dict) and "days" in alt_parsed:
                                                        print(f"DEBUG: SUCCESS - Found root object with 'days' at position {search_pos}!")
                                                        plan_data = alt_parsed
                                                        break
                                                except:
                                                    continue
                        except Exception as root_error:
                            print(f"DEBUG: Root object extraction failed: {root_error}")
                    else:
                        print(f"DEBUG: Could not find matching closing brace for first {{")
                else:
                    print(f"DEBUG: Could not find first {{ in response")
        
        # CRITICAL VALIDATION: If "days" exists in response, we MUST have it in plan_data
        # If we got an ingredient object instead, force re-extraction from the very beginning
        if has_days_in_response and isinstance(plan_data, dict) and "days" not in plan_data:
            print(f"DEBUG: CRITICAL ERROR - 'days' exists in response ({len(llm_response)} chars) but extracted object doesn't have it!")
            print(f"DEBUG: Extracted object keys: {list(plan_data.keys())}")
            print(f"DEBUG: This means we extracted a nested object instead of the root. Forcing re-extraction from start...")
            
            # Force extraction from the very first { in the response
            first_brace = llm_response.find('{')
            if first_brace != -1:
                print(f"DEBUG: Found first {{ at position {first_brace}, extracting root object...")
                try:
                    # Find matching closing brace
                    brace_count = 0
                    in_str = False
                    escape = False
                    end_brace = -1
                    
                    for i in range(first_brace, len(llm_response)):
                        c = llm_response[i]
                        if escape:
                            escape = False
                            continue
                        if c == '\\':
                            escape = True
                            continue
                        if c == '"' and not escape:
                            in_str = not in_str
                            continue
                        if not in_str:
                            if c == '{':
                                brace_count += 1
                            elif c == '}':
                                brace_count -= 1
                                if brace_count == 0:
                                    end_brace = i + 1
                                    break
                    
                    if end_brace > first_brace:
                        root_obj_text = llm_response[first_brace:end_brace]
                        print(f"DEBUG: Extracted root object ({len(root_obj_text)} chars)")
                        root_obj = json.loads(root_obj_text)
                        if "days" in root_obj:
                            print(f"DEBUG: SUCCESS! Root object has 'days' key!")
                            plan_data = root_obj
                        else:
                            print(f"DEBUG: Root object doesn't have 'days'. Keys: {list(root_obj.keys())[:10]}")
                except Exception as root_extract_error:
                    print(f"DEBUG: Root extraction failed: {root_extract_error}")
        
        # Additional check: If we still don't have "days", try one more time
        if has_days_in_response and isinstance(plan_data, dict) and "days" not in plan_data:
            print(f"DEBUG: CRITICAL - 'days' exists in response but not in extracted data! Forcing aggressive re-extraction...")
            # Try the most aggressive extraction: find "days" and extract the entire object containing it
            try:
                days_pos = llm_response.find('"days"')
                if days_pos != -1:
                    print(f"DEBUG: Found 'days' at position {days_pos}")
                    # Find the FIRST { before "days" - this should be the root object
                    # Search from the beginning of the response
                    first_brace = llm_response.rfind('{', 0, days_pos)
                    if first_brace != -1:
                        print(f"DEBUG: Found opening brace at position {first_brace}")
                        # Find matching closing brace
                        brace_count = 0
                        in_str = False
                        escape = False
                        brace_end = -1
                        
                        for i in range(first_brace, len(llm_response)):
                            c = llm_response[i]
                            if escape:
                                escape = False
                                continue
                            if c == '\\':
                                escape = True
                                continue
                            if c == '"' and not escape:
                                in_str = not in_str
                                continue
                            if not in_str:
                                if c == '{':
                                    brace_count += 1
                                elif c == '}':
                                    brace_count -= 1
                                    if brace_count == 0:
                                        brace_end = i + 1
                                        break
                        
                        if brace_end > first_brace:
                            print(f"DEBUG: Found matching closing brace at position {brace_end}, extracting...")
                            try:
                                obj_text = llm_response[first_brace:brace_end]
                                print(f"DEBUG: Extracted {len(obj_text)} chars")
                                test_obj = json.loads(obj_text)
                                if "days" in test_obj:
                                    print(f"DEBUG: SUCCESS! Found object with 'days' key!")
                                    plan_data = test_obj
                                else:
                                    print(f"DEBUG: Extracted object but no 'days' key. Keys: {list(test_obj.keys())[:10]}")
                            except json.JSONDecodeError as json_err:
                                print(f"DEBUG: JSON parse error: {json_err}")
                                print(f"DEBUG: Extracted text (first 500 chars): {obj_text[:500]}")
                            except Exception as parse_err:
                                print(f"DEBUG: Parse error: {parse_err}")
                    else:
                        print(f"DEBUG: Could not find opening brace before 'days'")
            except Exception as force_extract_error:
                print(f"DEBUG: Force extraction failed: {force_extract_error}")
                import traceback
                traceback.print_exc()
        
        # FINAL CHECK: If we got an ingredient-like object but "days" exists in the response, we MUST re-extract
        # This is the last chance to fix it before validation fails
        if has_days_in_response and isinstance(plan_data, dict) and "days" not in plan_data:
            # Check if it looks like an ingredient object
            looks_like_ingredient = any(key in plan_data for key in ['name', 'amount', 'unit']) and "meals" not in plan_data
            
            if looks_like_ingredient:
                    print(f"DEBUG: WARNING - Extracted ingredient object but 'days' exists in response. Trying alternative extraction...")
                    # Try to extract the largest JSON object that contains "days"
                    import re
                    # json is already imported at module level
                    # Find all JSON objects in the response and pick the one with "days"
                    try:
                        # Find the position of "days"
                        days_pos = llm_response.find('"days"')
                        if days_pos != -1:
                            # Find the largest object containing "days" by searching for all { } pairs
                            # Start from the beginning and find the object that contains "days"
                            best_start = 0
                            best_end = len(llm_response)
                            best_size = 0
                            
                            # Try multiple starting positions
                            for search_start in range(max(0, days_pos - 2000), days_pos + 1, 100):
                                # Find opening brace
                                brace_start = llm_response.rfind('{', search_start, days_pos + 1)
                                if brace_start == -1:
                                    continue
                                
                                # Find matching closing brace
                                brace_count = 0
                                in_string = False
                                escape_next = False
                                brace_end = -1
                                
                                for i in range(brace_start, len(llm_response)):
                                    char = llm_response[i]
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
                                        if char == '{':
                                            brace_count += 1
                                        elif char == '}':
                                            brace_count -= 1
                                            if brace_count == 0:
                                                brace_end = i + 1
                                                break
                                
                                if brace_end > brace_start:
                                    obj_size = brace_end - brace_start
                                    if obj_size > best_size:
                                        # Check if this object contains "days"
                                        obj_text = llm_response[brace_start:brace_end]
                                        if '"days"' in obj_text:
                                            best_start = brace_start
                                            best_end = brace_end
                                            best_size = obj_size
                            
                            if best_size > 0:
                                print(f"DEBUG: Found largest object with 'days' ({best_size} chars), extracting...")
                                try:
                                    obj_text = llm_response[best_start:best_end]
                                    plan_data = json.loads(obj_text)
                                    if "days" in plan_data:
                                        print(f"DEBUG: Successfully extracted meal plan with 'days' key!")
                                    else:
                                        print(f"DEBUG: Extracted object but no 'days' key. Keys: {list(plan_data.keys())[:10]}")
                                        # Try one more time with a simpler approach - just find the first { before "days" and extract to the end
                                        print(f"DEBUG: Trying simpler extraction approach...")
                                        first_brace = llm_response.rfind('{', 0, days_pos)
                                        if first_brace != -1:
                                            # Find the matching closing brace
                                            brace_count = 0
                                            in_str = False
                                            escape = False
                                            end_brace = -1
                                            for i in range(first_brace, len(llm_response)):
                                                c = llm_response[i]
                                                if escape:
                                                    escape = False
                                                    continue
                                                if c == '\\':
                                                    escape = True
                                                    continue
                                                if c == '"' and not escape:
                                                    in_str = not in_str
                                                    continue
                                                if not in_str:
                                                    if c == '{':
                                                        brace_count += 1
                                                    elif c == '}':
                                                        brace_count -= 1
                                                        if brace_count == 0:
                                                            end_brace = i + 1
                                                            break
                                            if end_brace > first_brace:
                                                try:
                                                    simple_obj = llm_response[first_brace:end_brace]
                                                    plan_data = json.loads(simple_obj)
                                                    if "days" in plan_data:
                                                        print(f"DEBUG: Successfully extracted with simple approach!")
                                                except:
                                                    pass
                                except Exception as parse_error:
                                    print(f"DEBUG: Failed to parse extracted object: {parse_error}")
                                    print(f"DEBUG: Error details: {str(parse_error)}")
                    except Exception as alt_extract_error:
                        print(f"DEBUG: Alternative extraction failed: {alt_extract_error}")
                        import traceback
                        traceback.print_exc()
                        # Fall back to re-extraction
                        try:
                            plan_data = extract_json_from_response(llm_response)
                            print(f"DEBUG: Re-extracted. Keys: {list(plan_data.keys()) if isinstance(plan_data, dict) else 'Not a dict'}")
                        except Exception as re_extract_error:
                            print(f"DEBUG: Re-extraction failed: {re_extract_error}")
        
        # Try to parse JSON - if it fails, handle the error
        try:
            # If parsing succeeded, skip truncation checks and continue
            pass  # plan_data is already set above
        except (ValueError, json.JSONDecodeError) as parse_error:
            # JSON parsing failed - show the actual parse error
            print(f"DEBUG: JSON parsing failed: {parse_error}")
            print(f"DEBUG: Response length: {len(llm_response)} chars")
            print(f"DEBUG: Response ending: {llm_response[-200:]}")
            print(f"DEBUG: Full LLM response (first 1000 chars): {llm_response[:1000]}")
            print(f"DEBUG: Full LLM response (last 500 chars): {llm_response[-500:]}")
            
            # Check if JSON appears incomplete (doesn't end with } or ]) - just for logging
            llm_response_stripped = llm_response.strip()
            json_appears_incomplete = not (llm_response_stripped.endswith('}') or llm_response_stripped.endswith(']'))
            
            # If response is very short (< 200 chars) and incomplete, it might be truncated
            # Otherwise, assume it's a JSON parsing issue, not truncation
            if len(llm_response) < 200 and json_appears_incomplete:
                raise HTTPException(
                    status_code=500,
                    detail=f"AI response appears truncated (only {len(llm_response)} chars received). The response may be incomplete. Please try again."
                )
            else:
                # JSON parsing failed - show the actual parse error
                raise HTTPException(
                    status_code=500,
                    detail=f"Failed to parse AI response as JSON: {str(parse_error)}. Response length: {len(llm_response)} chars. The AI may have returned invalid or malformed JSON. Please try again."
                )
        
        # If we get here, JSON parsing succeeded - continue with validation
        if isinstance(plan_data, dict):
            print(f"DEBUG: Plan data sample (first 1000 chars of str): {str(plan_data)[:1000]}")
            # Try to find 'days' recursively
            def find_days_recursive(obj, path=""):
                if isinstance(obj, dict):
                    if "days" in obj:
                        return obj["days"], path
                    for key, value in obj.items():
                        result = find_days_recursive(value, f"{path}.{key}" if path else key)
                        if result:
                            return result
                elif isinstance(obj, list) and len(obj) > 0:
                    if isinstance(obj[0], dict) and "meals" in obj[0]:
                        return obj, path + " (list of days)"
                    for i, item in enumerate(obj):
                        result = find_days_recursive(item, f"{path}[{i}]" if path else f"[{i}]")
                        if result:
                            return result
                return None
            
            days_found = find_days_recursive(plan_data)
            if days_found:
                print(f"DEBUG: Found 'days' structure at path: {days_found[1]}")
                if days_found[1]:  # If it's nested, extract it
                    plan_data = {"days": days_found[0]}
        elif isinstance(plan_data, list):
            print(f"DEBUG: Plan data is a list with {len(plan_data)} items")
            if len(plan_data) > 0:
                print(f"DEBUG: First item type: {type(plan_data[0])}")
                print(f"DEBUG: First item keys: {list(plan_data[0].keys()) if isinstance(plan_data[0], dict) else 'Not a dict'}")
        
        # Check if response contains "days" keyword (for logging only, since we already parsed)
        if '"days"' not in llm_response and "'days'" not in llm_response:
            print(f"DEBUG: WARNING - 'days' keyword not found in response!")
            print(f"DEBUG: Searching for alternative structures...")
            # Check for common variations
            if '"day"' in llm_response or "'day'" in llm_response:
                print(f"DEBUG: Found 'day' (singular) in response")
        
        try:
            print(f"DEBUG: Successfully parsed meal plan data")
            print(f"DEBUG: Plan data keys: {list(plan_data.keys()) if isinstance(plan_data, dict) else 'Not a dict'}")
            print(f"DEBUG: Plan data type: {type(plan_data)}")
            if isinstance(plan_data, dict):
                print(f"DEBUG: Plan data sample (first 1000 chars of str): {str(plan_data)[:1000]}")
                # Try to find 'days' recursively
                def find_days_recursive(obj, path=""):
                    if isinstance(obj, dict):
                        if "days" in obj:
                            return obj["days"], path
                        for key, value in obj.items():
                            result = find_days_recursive(value, f"{path}.{key}" if path else key)
                            if result:
                                return result
                    elif isinstance(obj, list) and len(obj) > 0:
                        if isinstance(obj[0], dict) and "meals" in obj[0]:
                            return obj, path + " (list of days)"
                        for i, item in enumerate(obj):
                            result = find_days_recursive(item, f"{path}[{i}]" if path else f"[{i}]")
                            if result:
                                return result
                    return None
                
                days_found = find_days_recursive(plan_data)
                if days_found:
                    print(f"DEBUG: Found 'days' structure at path: {days_found[1]}")
                    if days_found[1]:  # If it's nested, extract it
                        plan_data = {"days": days_found[0]}
            elif isinstance(plan_data, list):
                print(f"DEBUG: Plan data is a list with {len(plan_data)} items")
                if len(plan_data) > 0:
                    print(f"DEBUG: First item type: {type(plan_data[0])}")
                    print(f"DEBUG: First item keys: {list(plan_data[0].keys()) if isinstance(plan_data[0], dict) else 'Not a dict'}")
        except ValueError as e:
            error_msg = f"Failed to parse AI response as JSON: {str(e)}"
            print(f"DEBUG: JSON extraction failed: {error_msg}")
            print(f"DEBUG: Full LLM response (first 2000 chars): {llm_response[:2000]}")
            print(f"DEBUG: Full LLM response (last 500 chars): {llm_response[-500:]}")
            raise HTTPException(
                status_code=500,
                detail=f"{error_msg}. The AI may have returned invalid data. Please try generating a shorter meal plan (1-3 days) or try again."
            )
        
        # Validate and fix the plan data structure
        if not isinstance(plan_data, dict):
            print(f"DEBUG: Plan data is not a dict, it's: {type(plan_data)}")
            print(f"DEBUG: Plan data value: {plan_data}")
            raise HTTPException(
                status_code=500, 
                detail=f"Invalid meal plan structure: expected dict, got {type(plan_data).__name__}. Please try again."
            )
        
        if "days" not in plan_data:
            print(f"DEBUG: Missing 'days' key. Available keys: {list(plan_data.keys()) if isinstance(plan_data, dict) else 'Not a dict'}")
            print(f"DEBUG: Plan data type: {type(plan_data)}")
            print(f"DEBUG: Full plan_data (first 2000 chars): {str(plan_data)[:2000]}")
            
            # Fix: Handle 'day' (singular) instead of 'days' (plural)
            if isinstance(plan_data, dict) and "day" in plan_data and "meals" in plan_data:
                print(f"DEBUG: Found 'day' (singular) instead of 'days', wrapping in array...")
                # This is a single day object, wrap it in an array
                plan_data = {"days": [plan_data]}
            # Fix: Handle case where it's a list of day objects
            elif isinstance(plan_data, list) and len(plan_data) > 0:
                # Check if it's a list of day objects (has 'day' and 'meals' keys)
                if isinstance(plan_data[0], dict):
                    # Check for day structure first - if it has 'meals' key, it's likely a day object
                    if "meals" in plan_data[0]:
                        print(f"DEBUG: Found list of day objects (has 'meals' key), wrapping in 'days'...")
                        plan_data = {"days": plan_data}
                    elif "day" in plan_data[0]:
                        print(f"DEBUG: Found list of day objects (has 'day' key), wrapping in 'days'...")
                        plan_data = {"days": plan_data}
                    # Check if it looks like ingredients (has 'name', 'amount', 'unit' but NOT 'meals')
                    elif isinstance(plan_data[0], dict) and all(key in plan_data[0] for key in ['name', 'amount', 'unit']) and "meals" not in plan_data[0]:
                        print(f"DEBUG: ERROR - Extracted ingredients array instead of meal plan!")
                        print(f"DEBUG: First item: {plan_data[0]}")
                        print(f"DEBUG: LLM response length: {len(llm_response)} chars")
                        print(f"DEBUG: LLM response (last 500 chars): {llm_response[-500:]}")
                        print(f"DEBUG: Full parsed data (first 1000 chars): {str(plan_data)[:1000]}")
                        # Try to find 'days' in the original response
                        if '"days"' in llm_response or "'days'" in llm_response:
                            print(f"DEBUG: Found 'days' keyword in response, but structure is wrong")
                            # Try to extract days array directly from the response text
                            import re
                            days_match = re.search(r'"days"\s*:\s*\[', llm_response)
                            if days_match:
                                print(f"DEBUG: Found 'days' array in response text, attempting direct extraction...")
                                # Try to extract the days array manually
                                start_pos = days_match.end() - 1
                                bracket_count = 0
                                end_pos = start_pos
                                for i in range(start_pos, len(llm_response)):
                                    if llm_response[i] == '[':
                                        bracket_count += 1
                                    elif llm_response[i] == ']':
                                        bracket_count -= 1
                                        if bracket_count == 0:
                                            end_pos = i + 1
                                            break
                                if end_pos > start_pos:
                                    try:
                                        days_array_str = llm_response[start_pos:end_pos]
                                        days_array = json.loads(days_array_str)
                                        plan_data = {"days": days_array}
                                        print(f"DEBUG: Successfully extracted days array directly from response!")
                                        # Successfully fixed, continue
                                    except Exception as extract_error:
                                        print(f"DEBUG: Failed to extract days array: {extract_error}")
                        # If we couldn't fix it, raise error
                        if "days" not in plan_data:
                            raise HTTPException(
                                status_code=500,
                                detail=f"Failed to parse meal plan structure. The AI returned an ingredients array instead of a meal plan. Response length: {len(llm_response)} chars. Please try again."
                            )
            
            # Try to fix: maybe the structure is different
            if isinstance(plan_data, dict) and len(plan_data) == 1:
                # Maybe it's wrapped in another key
                first_key = list(plan_data.keys())[0]
                if isinstance(plan_data[first_key], dict) and "days" in plan_data[first_key]:
                    print(f"DEBUG: Found 'days' nested under '{first_key}', unwrapping...")
                    plan_data = plan_data[first_key]
                elif isinstance(plan_data[first_key], list):
                    # Check if it's ingredients
                    if len(plan_data[first_key]) > 0 and isinstance(plan_data[first_key][0], dict):
                        if all(key in plan_data[first_key][0] for key in ['name', 'amount', 'unit']):
                            print(f"DEBUG: ERROR - Extracted ingredients instead of meal plan!")
                            print(f"DEBUG: First item: {plan_data[first_key][0] if len(plan_data[first_key]) > 0 else 'empty'}")
                            print(f"DEBUG: LLM response length: {len(llm_response)} chars")
                            raise HTTPException(
                                status_code=500,
                                detail=f"Failed to parse meal plan structure. The AI response appears incomplete or malformed. Response length: {len(llm_response)} chars. Please try generating a shorter meal plan (1-3 days) or try again."
                            )
                    # Maybe days is directly a list
                    print(f"DEBUG: Found list under '{first_key}', wrapping in 'days'...")
                    plan_data = {"days": plan_data[first_key]}
            
            if "days" not in plan_data:
                # LAST RESORT: If "days" exists in response, try extracting from the very first {
                if '"days"' in llm_response or "'days'" in llm_response:
                    print(f"DEBUG: LAST RESORT - 'days' exists but not extracted. Trying extraction from first {{...")
                    # Strip any leading whitespace or text
                    stripped_response = llm_response.strip()
                    first_brace = stripped_response.find('{')
                    if first_brace != -1:
                        print(f"DEBUG: Found first {{ at position {first_brace} in stripped response")
                        try:
                            # Extract root object from first {
                            brace_count = 0
                            in_str = False
                            escape = False
                            end_brace = -1
                            
                            for i in range(first_brace, len(stripped_response)):
                                c = stripped_response[i]
                                if escape:
                                    escape = False
                                    continue
                                if c == '\\':
                                    escape = True
                                    continue
                                if c == '"' and not escape:
                                    in_str = not in_str
                                    continue
                                if not in_str:
                                    if c == '{':
                                        brace_count += 1
                                    elif c == '}':
                                        brace_count -= 1
                                        if brace_count == 0:
                                            end_brace = i + 1
                                            break
                            
                            if end_brace > first_brace:
                                root_text = stripped_response[first_brace:end_brace]
                                print(f"DEBUG: Extracted root object ({len(root_text)} chars)")
                                root_obj = json.loads(root_text)
                                if "days" in root_obj:
                                    print(f"DEBUG: LAST RESORT SUCCESS! Found 'days' in root object!")
                                    plan_data = root_obj
                                else:
                                    print(f"DEBUG: Root object doesn't have 'days'. Keys: {list(root_obj.keys())[:10]}")
                                    # Try one more time with the original response (not stripped)
                                    first_brace_orig = llm_response.find('{')
                                    if first_brace_orig != -1:
                                        brace_count = 0
                                        in_str = False
                                        escape = False
                                        end_brace_orig = -1
                                        for i in range(first_brace_orig, len(llm_response)):
                                            c = llm_response[i]
                                            if escape:
                                                escape = False
                                                continue
                                            if c == '\\':
                                                escape = True
                                                continue
                                            if c == '"' and not escape:
                                                in_str = not in_str
                                                continue
                                            if not in_str:
                                                if c == '{':
                                                    brace_count += 1
                                                elif c == '}':
                                                    brace_count -= 1
                                                    if brace_count == 0:
                                                        end_brace_orig = i + 1
                                                        break
                                        if end_brace_orig > first_brace_orig:
                                            root_text_orig = llm_response[first_brace_orig:end_brace_orig]
                                            try:
                                                root_obj_orig = json.loads(root_text_orig)
                                                if "days" in root_obj_orig:
                                                    print(f"DEBUG: LAST RESORT SUCCESS (original)! Found 'days' in root object!")
                                                    plan_data = root_obj_orig
                                            except:
                                                pass
                        except Exception as last_resort_error:
                            print(f"DEBUG: Last resort extraction failed: {last_resort_error}")
                            import traceback
                            traceback.print_exc()
                
                # Check if plan_data looks like ingredients
                if isinstance(plan_data, dict) and any(key in plan_data for key in ['name', 'amount', 'unit']) and "meals" not in plan_data:
                    print(f"DEBUG: WARNING - Extracted object looks like an ingredient, but response is {len(llm_response)} chars (likely contains full meal plan)")
                    print(f"DEBUG: Plan data keys: {list(plan_data.keys())}")
                    print(f"DEBUG: Plan data (first 500 chars): {str(plan_data)[:500]}")
                    
                    # Before giving up, try to find "days" in the original response
                    if '"days"' in llm_response or "'days'" in llm_response:
                        print(f"DEBUG: Found 'days' keyword in response, attempting to extract it directly...")
                        import re
                        # Try to find the full JSON object with "days" key
                        days_match = re.search(r'\{[^{}]*"days"\s*:\s*\[', llm_response)
                        if not days_match:
                            # Try a broader search
                            days_match = re.search(r'"days"\s*:\s*\[', llm_response)
                        
                        if days_match:
                            print(f"DEBUG: Found 'days' array in response text, attempting direct extraction...")
                            # Find the opening brace before "days"
                            start_search = max(0, days_match.start() - 1000)
                            text_before = llm_response[start_search:days_match.start()]
                            # Find the last { before "days"
                            last_brace = text_before.rfind('{')
                            if last_brace != -1:
                                start_pos = start_search + last_brace
                            else:
                                start_pos = days_match.start() - 1  # Start one char before "days"
                            
                            # Now find the matching closing brace
                            brace_count = 0
                            in_string = False
                            escape_next = False
                            end_pos = start_pos
                            
                            for i in range(start_pos, len(llm_response)):
                                char = llm_response[i]
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
                                    if char == '{':
                                        brace_count += 1
                                    elif char == '}':
                                        brace_count -= 1
                                        if brace_count == 0:
                                            end_pos = i + 1
                                            break
                            
                            if end_pos > start_pos:
                                try:
                                    full_json_str = llm_response[start_pos:end_pos]
                                    full_plan_data = json.loads(full_json_str)
                                    if "days" in full_plan_data:
                                        print(f"DEBUG: Successfully extracted full meal plan with 'days' key!")
                                        plan_data = full_plan_data
                                    else:
                                        print(f"DEBUG: Extracted JSON but still no 'days' key. Keys: {list(full_plan_data.keys())}")
                                        # Try one more time - re-extract using the function which prioritizes "days"
                                        print(f"DEBUG: Attempting to re-extract using extract_json_from_response...")
                                        try:
                                            plan_data = extract_json_from_response(llm_response)
                                            if "days" in plan_data:
                                                print(f"DEBUG: Successfully re-extracted with 'days' key!")
                                            else:
                                                print(f"DEBUG: Re-extraction still failed. Keys: {list(plan_data.keys())[:10]}")
                                        except Exception as re_extract_error:
                                            print(f"DEBUG: Re-extraction failed: {re_extract_error}")
                                except Exception as extract_error:
                                    print(f"DEBUG: Failed to extract full JSON: {extract_error}")
                                    # Try re-extraction as fallback
                                    print(f"DEBUG: Attempting to re-extract using extract_json_from_response as fallback...")
                                    try:
                                        plan_data = extract_json_from_response(llm_response)
                                        if "days" in plan_data:
                                            print(f"DEBUG: Successfully re-extracted with 'days' key!")
                                        else:
                                            print(f"DEBUG: Re-extraction still failed. Keys: {list(plan_data.keys())[:10]}")
                                    except Exception as re_extract_error:
                                        print(f"DEBUG: Re-extraction failed: {re_extract_error}")
                    else:
                        # No "days" match found, but try re-extraction anyway
                        print(f"DEBUG: No 'days' pattern found, but attempting re-extraction anyway...")
                        try:
                            plan_data = extract_json_from_response(llm_response)
                            if "days" in plan_data:
                                print(f"DEBUG: Successfully re-extracted with 'days' key!")
                            else:
                                print(f"DEBUG: Re-extraction failed. Keys: {list(plan_data.keys())[:10]}")
                        except Exception as re_extract_error:
                            print(f"DEBUG: Re-extraction failed: {re_extract_error}")
                    
                    # If we still don't have "days", try one more aggressive extraction
                    if "days" not in plan_data:
                        print(f"DEBUG: ERROR - Extracted ingredient object instead of meal plan!")
                        print(f"DEBUG: Plan data keys: {list(plan_data.keys()) if isinstance(plan_data, dict) else 'Not a dict'}")
                        print(f"DEBUG: LLM response length: {len(llm_response)} chars")
                        
                        # Last resort: Extract from the very first { in the response
                        first_brace = llm_response.find('{')
                        if first_brace != -1:
                            print(f"DEBUG: Attempting last-resort extraction from first {{ at position {first_brace}...")
                            brace_count = 0
                            in_str = False
                            escape = False
                            brace_end = -1
                            for i in range(first_brace, len(llm_response)):
                                c = llm_response[i]
                                if escape:
                                    escape = False
                                    continue
                                if c == '\\':
                                    escape = True
                                    continue
                                if c == '"' and not escape:
                                    in_str = not in_str
                                    continue
                                if not in_str:
                                    if c == '{':
                                        brace_count += 1
                                    elif c == '}':
                                        brace_count -= 1
                                        if brace_count == 0:
                                            brace_end = i + 1
                                            break
                            
                            if brace_end > first_brace:
                                try:
                                    root_text = llm_response[first_brace:brace_end]
                                    root_parsed = json.loads(root_text)
                                    if isinstance(root_parsed, dict) and "days" in root_parsed:
                                        print(f"DEBUG: SUCCESS - Last-resort extraction found root object with 'days'!")
                                        plan_data = root_parsed
                                    else:
                                        print(f"DEBUG: Last-resort extraction failed. Root object keys: {list(root_parsed.keys())[:10] if isinstance(root_parsed, dict) else 'Not a dict'}")
                                except Exception as last_error:
                                    print(f"DEBUG: Last-resort extraction failed: {last_error}")
                        
                        # If we still don't have "days", raise error
                        if "days" not in plan_data:
                            print(f"DEBUG: LLM response (last 500 chars): {llm_response[-500:]}")
                            raise HTTPException(
                                status_code=500,
                                detail=f"Failed to parse meal plan structure. The AI returned an ingredient object instead of a meal plan. Response length: {len(llm_response)} chars. Please try again."
                            )
                
                # Provide detailed diagnostic information
                print(f"DEBUG: ERROR - Missing 'days' key after all fix attempts")
                print(f"DEBUG: LLM response length: {len(llm_response)} chars")
                print(f"DEBUG: Plan data type: {type(plan_data)}")
                print(f"DEBUG: LLM response (first 1000 chars): {llm_response[:1000]}")
                print(f"DEBUG: LLM response (last 500 chars): {llm_response[-500:]}")
                
                if isinstance(plan_data, dict):
                    print(f"DEBUG: Available keys: {list(plan_data.keys())}")
                    print(f"DEBUG: Plan data (first 2000 chars): {str(plan_data)[:2000]}")
                    # Try to see if there's a nested structure
                    for key, value in list(plan_data.items())[:5]:  # Check first 5 keys
                        print(f"DEBUG: Key '{key}' type: {type(value)}")
                        if isinstance(value, dict):
                            print(f"DEBUG: Key '{key}' has sub-keys: {list(value.keys())[:10]}")
                        elif isinstance(value, list) and len(value) > 0:
                            print(f"DEBUG: Key '{key}' is a list with {len(value)} items, first item type: {type(value[0])}")
                            if isinstance(value[0], dict):
                                print(f"DEBUG: Key '{key}' first item keys: {list(value[0].keys())[:10]}")
                elif isinstance(plan_data, list) and len(plan_data) > 0:
                    print(f"DEBUG: List with {len(plan_data)} items, first item type: {type(plan_data[0])}")
                    if isinstance(plan_data[0], dict):
                        print(f"DEBUG: First item keys: {list(plan_data[0].keys())}")
                        print(f"DEBUG: First item (first 1000 chars): {str(plan_data[0])[:1000]}")
                
                # Create a more helpful error message
                if isinstance(plan_data, dict):
                    keys_str = ", ".join(list(plan_data.keys())[:10])
                    if len(plan_data.keys()) > 10:
                        keys_str += f" (and {len(plan_data.keys()) - 10} more)"
                    error_detail = f"Invalid meal plan structure: missing 'days' key. Found keys: {keys_str}. Response length: {len(llm_response)} chars."
                elif isinstance(plan_data, list):
                    error_detail = f"Invalid meal plan structure: received a list instead of an object with 'days' key. List has {len(plan_data)} items. Response length: {len(llm_response)} chars."
                else:
                    error_detail = f"Invalid meal plan structure: unexpected type {type(plan_data).__name__}. Expected dict with 'days' key. Response length: {len(llm_response)} chars."
                
                raise HTTPException(
                    status_code=500,
                    detail=f"{error_detail} Please try generating a shorter meal plan (1-3 days) or try again."
                )
        
        # Post-process: Remove animal products if vegan is selected
        if request.dietary_preferences and "vegan" in request.dietary_preferences:
            print(f"DEBUG: Applying vegan filtering to meal plan...")
            import re
            
            # Reuse the same filtering function from recipe generation
            # Comprehensive animal product patterns - including variations with punctuation
            animal_patterns = [
                # Eggs - most comprehensive (including typos like "eeg" and shortened "eg")
                r'\begg\b', r'\beggs\b', r'\beeg\b', r'\beegs\b',  # Standard and typo variations
                r'\beg\b', r'\begs\b',  # Shortened form "eg" (but not in "vegetable", "leg", etc.)
                r'\begg\s+white', r'\begg\s+whites', r'\begg\s+yolk', r'\begg\s+yolks',
                r'\begg,', r'\beggs,', r'\begg\.', r'\beggs\.', r'\begg\s', r'\beggs\s',
                r'\beeg,', r'\beegs,', r'\beeg\.', r'\beegs\.', r'\beeg\s', r'\beegs\s',  # Typo variations
                r'\beg,', r'\begs,', r'\beg\.', r'\begs\.', r'\beg\s', r'\begs\s',  # Shortened form variations
                r'\begg\s*-\s*\d', r'\beggs\s*-\s*\d',  # "egg - 1" or "eggs - 1"
                r'\begg-\d', r'\beggs-\d',  # "egg-1" or "eggs-1" (no spaces)
                r'\beeg\s*-\s*\d', r'\beegs\s*-\s*\d',  # "eeg - 1" (typo)
                r'\beeg-\d', r'\beegs-\d',  # "eeg-1" (typo, no spaces)
                r'\beg\s*-\s*\d', r'\begs\s*-\s*\d',  # "eg - 1" (shortened)
                r'\beg-\d', r'\begs-\d',  # "eg-1" or "egs-1" (shortened, no spaces)
                r'\begg\s*-\s*\d+\s+\w+', r'\beggs\s*-\s*\d+\s+\w+',  # "egg - 1 large"
                r'\beeg\s*-\s*\d+\s+\w+', r'\beegs\s*-\s*\d+\s+\w+',  # "eeg - 1 large" (typo)
                r'\beg\s*-\s*\d+\s+\w+', r'\begs\s*-\s*\d+\s+\w+',  # "eg - 1 large" (shortened)
                # Compound phrases with egg
                r'\bpoached\s+egg', r'\bpoached\s+eggs', r'\bpoached\s+eeg', r'\bpoached\s+eegs', r'\bpoached\s+eg', r'\bpoached\s+egs',
                r'\bfried\s+egg', r'\bfried\s+eggs', r'\bfried\s+eeg', r'\bfried\s+eegs', r'\bfried\s+eg', r'\bfried\s+egs',
                r'\bscrambled\s+egg', r'\bscrambled\s+eggs', r'\bscrambled\s+eeg', r'\bscrambled\s+eegs', r'\bscrambled\s+eg', r'\bscrambled\s+egs',
                r'\bboiled\s+egg', r'\bboiled\s+eggs', r'\bboiled\s+eeg', r'\bboiled\s+eegs', r'\bboiled\s+eg', r'\bboiled\s+egs',
                r'\bhard\s+boiled\s+egg', r'\bhard\s+boiled\s+eggs',
                r'\bsoft\s+boiled\s+egg', r'\bsoft\s+boiled\s+eggs',
                r'\bsunny\s+side\s+up\s+egg', r'\bsunny\s+side\s+up\s+eggs',
                r'\bover\s+easy\s+egg', r'\bover\s+easy\s+eggs',
                r'\braw\s+egg', r'\braw\s+eggs', r'\braw\s+eg', r'\braw\s+egs',
                r'\bwhole\s+egg', r'\bwhole\s+eggs', r'\bwhole\s+eg', r'\bwhole\s+egs',
                r'\btoast\s+with\s+eg', r'\btoast\s+with\s+egs',
                # Meat
                r'\bchicken\b', r'\bbeef\b', r'\bpork\b', r'\blamb\b', r'\bturkey\b', r'\bduck\b',
                r'\bchicken\s+breast\b', r'\bground\s+beef\b', r'\bmeat\b', r'\bpoultry\b',
                # Seafood
                r'\bfish\b', r'\bsalmon\b', r'\btuna\b', r'\bshrimp\b', r'\bcrab\b', r'\blobster\b', r'\bseafood\b',
                # Dairy
                r'\bmilk\b', r'\bcheese\b', r'\bbutter\b', r'\byogurt\b', r'\bcream\b', r'\bsour\s+cream\b', r'\bdairy\b',
                # Other animal products
                r'\bhoney\b', r'\bgelatin\b', r'\bwhey\b', r'\bcasein\b', r'\blard\b', r'\bbacon\b', r'\bham\b'
            ]
            
            def contains_animal_product(text):
                """Check if text contains any animal product - case insensitive"""
                if not text:
                    return False
                text_lower = str(text).lower().strip()
                
                # FIRST: Quick check for any "egg" followed by hyphen and number (most common case)
                if re.search(r'\b(eeg|egg|eg|eggs|egs)\s*-\s*\d', text_lower):
                    if 'eggplant' not in text_lower and 'eggshell' not in text_lower:
                        print(f"DEBUG: contains_animal_product QUICK MATCH: '{text_lower}'")
                        return True
                
                # Check for exact word matches
                for pattern in animal_patterns:
                    if re.search(pattern, text_lower):
                        return True
                
                # Check for patterns like "egg - 1 large", "eggs - 3 large"
                if re.search(r'\b(eeg|egg|eg|eggs|egs)\s*-\s*\d+', text_lower, re.IGNORECASE):
                    if 'eggplant' not in text_lower and 'eggshell' not in text_lower:
                        return True
                
                # FINAL CATCH-ALL: If text contains "egg" or "eggs" anywhere (as a word)
                if re.search(r'\b(eeg|egg|eg|eggs|egs)\b', text_lower):
                    if 'eggplant' not in text_lower and 'eggshell' not in text_lower:
                        if re.search(r'\b(eeg|egg|eg|eggs|egs)\s*-\s*\d', text_lower):
                            return True
                        if text_lower in ['egg', 'eggs', 'eeg', 'eegs', 'eg', 'egs']:
                            return True
                
                return False
            
            # Filter ingredients, names, and instructions from all meals in all days
            total_removed = 0
            for day in plan_data.get("days", []):
                for meal in day.get("meals", []):
                    # Filter meal name
                    if "name" in meal:
                        meal_name = str(meal.get("name", "")).strip()
                        original_name = meal_name
                        
                        if contains_animal_product(meal_name):
                            print(f"DEBUG: Meal name contains animal products: '{meal_name}'")
                            # Replace common egg phrases in meal names
                            meal_name = re.sub(r'\bpoached\s+egg\b', 'poached tofu', meal_name, flags=re.IGNORECASE)
                            meal_name = re.sub(r'\bpoached\s+eggs\b', 'poached tofu', meal_name, flags=re.IGNORECASE)
                            meal_name = re.sub(r'\bpoached\s+eeg\b', 'poached tofu', meal_name, flags=re.IGNORECASE)
                            meal_name = re.sub(r'\bpoached\s+eegs\b', 'poached tofu', meal_name, flags=re.IGNORECASE)
                            meal_name = re.sub(r'\bpoached\s+eg\b', 'poached tofu', meal_name, flags=re.IGNORECASE)
                            meal_name = re.sub(r'\bpoached\s+egs\b', 'poached tofu', meal_name, flags=re.IGNORECASE)
                            meal_name = re.sub(r'\bfried\s+egg\b', 'fried tofu', meal_name, flags=re.IGNORECASE)
                            meal_name = re.sub(r'\bfried\s+eggs\b', 'fried tofu', meal_name, flags=re.IGNORECASE)
                            meal_name = re.sub(r'\bscrambled\s+egg\b', 'scrambled tofu', meal_name, flags=re.IGNORECASE)
                            meal_name = re.sub(r'\bscrambled\s+eggs\b', 'scrambled tofu', meal_name, flags=re.IGNORECASE)
                            meal_name = re.sub(r'\btoast\s+with\s+eg\b', 'toast with tofu', meal_name, flags=re.IGNORECASE)
                            meal_name = re.sub(r'\btoast\s+with\s+egs\b', 'toast with tofu', meal_name, flags=re.IGNORECASE)
                            meal_name = re.sub(r'\btoast\s+with\s+egg\b', 'toast with tofu', meal_name, flags=re.IGNORECASE)
                            meal_name = re.sub(r'\btoast\s+with\s+eggs\b', 'toast with tofu', meal_name, flags=re.IGNORECASE)
                            # Generic egg replacements
                            meal_name = re.sub(r'\begg\b', 'tofu', meal_name, flags=re.IGNORECASE)
                            meal_name = re.sub(r'\beggs\b', 'tofu', meal_name, flags=re.IGNORECASE)
                            meal_name = re.sub(r'\beeg\b', 'tofu', meal_name, flags=re.IGNORECASE)
                            meal_name = re.sub(r'\beegs\b', 'tofu', meal_name, flags=re.IGNORECASE)
                            meal_name = re.sub(r'\beg\b', 'tofu', meal_name, flags=re.IGNORECASE)
                            meal_name = re.sub(r'\begs\b', 'tofu', meal_name, flags=re.IGNORECASE)
                            
                            # Make sure we didn't create "eggplant" or "eggshell"
                            meal_name = meal_name.replace('tofuplant', 'eggplant').replace('tofushell', 'eggshell')
                            
                            meal["name"] = meal_name
                            print(f"DEBUG: Updated meal name from '{original_name}' to '{meal_name}'")
                    
                    # Filter meal instructions
                    if "instructions" in meal:
                        filtered_instructions = []
                        for inst in meal.get("instructions", []):
                            inst_str = str(inst)
                            original_inst = inst_str
                            
                            if contains_animal_product(inst_str):
                                # Replace common egg phrases in instructions
                                inst_str = re.sub(r'\bpoached\s+egg\b', 'poached tofu', inst_str, flags=re.IGNORECASE)
                                inst_str = re.sub(r'\bpoached\s+eggs\b', 'poached tofu', inst_str, flags=re.IGNORECASE)
                                inst_str = re.sub(r'\bpoached\s+eeg\b', 'poached tofu', inst_str, flags=re.IGNORECASE)
                                inst_str = re.sub(r'\bpoached\s+eegs\b', 'poached tofu', inst_str, flags=re.IGNORECASE)
                                inst_str = re.sub(r'\bpoached\s+eg\b', 'poached tofu', inst_str, flags=re.IGNORECASE)
                                inst_str = re.sub(r'\bpoached\s+egs\b', 'poached tofu', inst_str, flags=re.IGNORECASE)
                                inst_str = re.sub(r'\bfried\s+egg\b', 'fried tofu', inst_str, flags=re.IGNORECASE)
                                inst_str = re.sub(r'\bfried\s+eggs\b', 'fried tofu', inst_str, flags=re.IGNORECASE)
                                inst_str = re.sub(r'\bscrambled\s+egg\b', 'scrambled tofu', inst_str, flags=re.IGNORECASE)
                                inst_str = re.sub(r'\bscrambled\s+eggs\b', 'scrambled tofu', inst_str, flags=re.IGNORECASE)
                                inst_str = re.sub(r'\bboiled\s+egg\b', 'boiled tofu', inst_str, flags=re.IGNORECASE)
                                inst_str = re.sub(r'\bboiled\s+eggs\b', 'boiled tofu', inst_str, flags=re.IGNORECASE)
                                inst_str = re.sub(r'\btoast\s+with\s+eg\b', 'toast with tofu', inst_str, flags=re.IGNORECASE)
                                inst_str = re.sub(r'\btoast\s+with\s+egs\b', 'toast with tofu', inst_str, flags=re.IGNORECASE)
                                inst_str = re.sub(r'\btoast\s+with\s+egg\b', 'toast with tofu', inst_str, flags=re.IGNORECASE)
                                inst_str = re.sub(r'\btoast\s+with\s+eggs\b', 'toast with tofu', inst_str, flags=re.IGNORECASE)
                                # Generic egg replacements
                                inst_str = re.sub(r'\begg\b', 'tofu', inst_str, flags=re.IGNORECASE)
                                inst_str = re.sub(r'\beggs\b', 'tofu', inst_str, flags=re.IGNORECASE)
                                inst_str = re.sub(r'\beeg\b', 'tofu', inst_str, flags=re.IGNORECASE)
                                inst_str = re.sub(r'\beegs\b', 'tofu', inst_str, flags=re.IGNORECASE)
                                inst_str = re.sub(r'\beg\b', 'tofu', inst_str, flags=re.IGNORECASE)
                                inst_str = re.sub(r'\begs\b', 'tofu', inst_str, flags=re.IGNORECASE)
                                # Replace "egg - 1", "eggs - 3" patterns
                                inst_str = re.sub(r'\begg\s*-\s*\d+', 'tofu', inst_str, flags=re.IGNORECASE)
                                inst_str = re.sub(r'\beggs\s*-\s*\d+', 'tofu', inst_str, flags=re.IGNORECASE)
                                inst_str = re.sub(r'\beeg\s*-\s*\d+', 'tofu', inst_str, flags=re.IGNORECASE)
                                inst_str = re.sub(r'\beegs\s*-\s*\d+', 'tofu', inst_str, flags=re.IGNORECASE)
                                inst_str = re.sub(r'\beg\s*-\s*\d+', 'tofu', inst_str, flags=re.IGNORECASE)
                                inst_str = re.sub(r'\begs\s*-\s*\d+', 'tofu', inst_str, flags=re.IGNORECASE)
                                
                                # Make sure we didn't create "eggplant" or "eggshell"
                                inst_str = inst_str.replace('tofuplant', 'eggplant').replace('tofushell', 'eggshell')
                                
                                # Remove other animal products
                                for pattern in animal_patterns:
                                    if pattern not in [r'\begg\b', r'\beggs\b', r'\beeg\b', r'\beegs\b', r'\beg\b', r'\begs\b']:  # Skip egg patterns we already handled
                                        inst_str = re.sub(pattern, "[removed - non-vegan]", inst_str, flags=re.IGNORECASE)
                            
                            if inst_str.strip() and inst_str.strip() != "[removed - non-vegan]":
                                filtered_instructions.append(inst_str)
                            elif original_inst.strip():
                                print(f"DEBUG: Removed instruction containing animal products: {original_inst[:100]}")
                        
                        meal["instructions"] = filtered_instructions
                    
                    # Filter ingredients
                    if "ingredients" in meal:
                        original_ingredients = meal["ingredients"].copy()
                        original_count = len(meal["ingredients"])
                        
                        filtered_ingredients = []
                        for ing in meal["ingredients"]:
                            ing_name = str(ing.get("name", "")).strip()
                            ing_amount = str(ing.get("amount", "")).strip()
                            ing_unit = str(ing.get("unit", "")).strip()
                            
                            # Create multiple string combinations to check
                            full_ing_str = f"{ing_name} {ing_amount} {ing_unit}".strip()
                            alt_ing_str = f"{ing_name}-{ing_amount} {ing_unit}".strip()
                            alt_ing_str2 = f"{ing_name} - {ing_amount} {ing_unit}".strip()
                            alt_ing_str3 = f"{ing_name} {ing_unit} {ing_amount}".strip()
                            alt_ing_str4 = f"{ing_name} - {ing_amount} - {ing_unit}".strip()
                            alt_ing_str5 = f"{ing_name}-{ing_amount}-{ing_unit}".strip()
                            
                            # Check all fields and combinations
                            if (not contains_animal_product(ing_name) and 
                                not contains_animal_product(ing_amount) and 
                                not contains_animal_product(ing_unit) and
                                not contains_animal_product(full_ing_str) and
                                not contains_animal_product(alt_ing_str) and
                                not contains_animal_product(alt_ing_str2) and
                                not contains_animal_product(alt_ing_str3) and
                                not contains_animal_product(alt_ing_str4) and
                                not contains_animal_product(alt_ing_str5)):
                                filtered_ingredients.append(ing)
                            else:
                                print(f"DEBUG: Removed non-vegan ingredient from meal '{meal.get('name')}': {ing.get('name')} (full: '{full_ing_str}')")
                        
                        meal["ingredients"] = filtered_ingredients
                        removed_count = original_count - len(meal["ingredients"])
                        total_removed += removed_count
                        if removed_count > 0:
                            print(f"DEBUG: Removed {removed_count} non-vegan ingredient(s) from meal '{meal.get('name')}'")
            
            if total_removed > 0:
                print(f"DEBUG: Removed {total_removed} total non-vegan ingredient(s) from meal plan")
        
        # Remove duplicate meals (same ingredients = same meal)
        seen_meals = set()
        for day in plan_data.get("days", []):
            unique_meals = []
            for meal in day.get("meals", []):
                # Create a signature based on ingredients
                if meal.get("ingredients"):
                    ing_signature = tuple(sorted([
                        (
                            str(ing.get("name") or "").lower().strip(), 
                            str(ing.get("amount") or "").strip(), 
                            str(ing.get("unit") or "").strip()
                        )
                        for ing in meal.get("ingredients", [])
                    ]))
                    if ing_signature not in seen_meals:
                        seen_meals.add(ing_signature)
                        unique_meals.append(meal)
                    else:
                        print(f"DEBUG: Removed duplicate meal: {meal.get('name')} (same ingredients as previous meal)")
                else:
                    unique_meals.append(meal)
            day["meals"] = unique_meals
        
        # Add dates to days and generate images for meals
        # Use today as day 1 (not yesterday)
        today = datetime.now().date()
        for i, day in enumerate(plan_data.get("days", [])):
            if "meals" not in day:
                print(f"DEBUG: Warning - Day {i+1} has no meals")
                day["meals"] = []
            
            # Validate meals per day
            meals_count = len(day.get("meals", []))
            if meals_count < request.meals_per_day:
                print(f"DEBUG: WARNING - Day {i+1} has only {meals_count} meals, expected {request.meals_per_day}")
                if meals_count == 0:
                    raise HTTPException(
                        status_code=500,
                        detail=f"Day {i+1} has no meals. The response may have been truncated. Please try generating a shorter meal plan (1-3 days)."
                    )
                elif meals_count == 1 and request.meals_per_day > 1:
                    raise HTTPException(
                        status_code=500,
                        detail=f"Day {i+1} only has 1 meal instead of {request.meals_per_day} meals. The response was truncated. Please try generating a shorter meal plan (1-3 days) or reduce meals per day."
                    )
            
            # Set date starting from today (day 1 = today)
            day["date"] = (today + timedelta(days=i)).isoformat()
            day["day_number"] = i + 1
            
            # Generate images and add recipe IDs for each meal
            for meal in day.get("meals", []):
                # Ensure meal has required fields
                if "name" not in meal:
                    meal["name"] = "Unnamed Meal"
                if "description" not in meal:
                    meal["description"] = ""
                if "ingredients" not in meal:
                    meal["ingredients"] = []
                if "instructions" not in meal:
                    meal["instructions"] = []
                
                # Create a recipe ID for this meal
                meal["recipe_id"] = str(uuid.uuid4())
                
                # Generate image for meal only if requested (disabled by default since images often don't match)
                if request.include_images:
                    try:
                        import asyncio
                        # Use a longer timeout for image generation
                        image_url = await asyncio.wait_for(
                            generate_recipe_image(meal.get("name", ""), meal.get("description", "")),
                            timeout=20.0  # Increased timeout for images
                        )
                        if image_url:
                            meal["image_url"] = image_url
                            print(f"DEBUG: Generated image for {meal.get('name')}: {image_url[:50]}...")
                    except asyncio.TimeoutError:
                        print(f"Image generation timed out for meal {meal.get('name')} - skipping image")
                    except Exception as e:
                        print(f"Image generation failed for meal {meal.get('name')}: {e} - skipping image")
                # If include_images is False, don't add image_url at all
            
            # Calculate daily totals
            total_calories = sum(meal.get("estimated_calories", 0) for meal in day.get("meals", []))
            day["total_calories"] = total_calories
        
        # Validate that we got all requested days
        days_received = len(plan_data.get("days", []))
        if days_received < request.days:
            print(f"DEBUG: WARNING - Only received {days_received} days out of {request.days} requested")
            if days_received == 0:
                raise HTTPException(
                    status_code=500,
                    detail=f"Failed to generate meal plan. No days were returned. The response may have been truncated. Please try generating a shorter meal plan (1-3 days)."
                )
            elif days_received == 1 and request.days > 1:
                raise HTTPException(
                    status_code=500,
                    detail=f"Only 1 day was generated instead of {request.days} days. The response was severely truncated. Please try generating a 1-3 day plan instead, or generate multiple shorter plans separately."
                )
            elif days_received < request.days * 0.5:  # Less than half
                raise HTTPException(
                    status_code=500,
                    detail=f"Only {days_received} out of {request.days} days were generated. The response was truncated. Please try generating a shorter meal plan (1-3 days) or generate multiple shorter plans."
                )
            else:
                # Partial success - warn but continue
                print(f"DEBUG: Partial meal plan - {days_received}/{request.days} days. Continuing with available days.")
        
        plan_id = str(uuid.uuid4())
        plan_data["plan_id"] = plan_id
        plan_data["created_at"] = datetime.now().isoformat()
        plan_data["dietary_preferences"] = request.dietary_preferences
        plan_data["target_calories"] = request.target_calories
        plan_data["total_days"] = days_received
        plan_data["requested_days"] = request.days  # Store what was requested
        
        meal_plans_storage[plan_id] = plan_data
        
        print(f"DEBUG: Meal plan generated successfully with {days_received} days (requested {request.days})")
        return plan_data
    
    except HTTPException as he:
        # Re-raise HTTP exceptions with their details
        raise he
    except Exception as e:
        error_msg = f"Unexpected error: {type(e).__name__}: {str(e)}"
        print(f"DEBUG: Unexpected error in generate_meal_plan: {error_msg}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error generating meal plan: {error_msg}")


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


@app.post("/api/recipe/{recipe_id}/favorite")
async def toggle_favorite(recipe_id: str):
    """Toggle favorite status of a recipe"""
    if recipe_id not in recipes_storage:
        raise HTTPException(status_code=404, detail="Recipe not found")
    
    if recipe_id in favorites_storage:
        favorites_storage.remove(recipe_id)
        is_favorite = False
    else:
        favorites_storage.append(recipe_id)
        is_favorite = True
    
    return {"recipe_id": recipe_id, "is_favorite": is_favorite}


@app.get("/api/favorites")
async def get_favorites():
    """Get all favorite recipes"""
    favorite_recipes = [recipes_storage[rid] for rid in favorites_storage if rid in recipes_storage]
    return {"favorites": favorite_recipes}


@app.post("/api/recipe/{recipe_id}/save")
async def save_recipe(recipe_id: str):
    """Save a recipe (already saved if in storage, this is for explicit save)"""
    if recipe_id not in recipes_storage:
        raise HTTPException(status_code=404, detail="Recipe not found")
    return {"recipe_id": recipe_id, "saved": True, "message": "Recipe saved successfully"}


@app.post("/api/scale-recipe")
async def scale_recipe(request: ScaleRecipeRequest):
    """Scale a recipe to a different number of servings"""
    if request.recipe_id not in recipes_storage:
        raise HTTPException(status_code=404, detail="Recipe not found")
    
    recipe = recipes_storage[request.recipe_id].copy()
    original_servings = recipe.get("servings", 4)
    
    # Scale ingredients
    recipe["ingredients"] = scale_recipe_ingredients(recipe, original_servings, request.new_servings)
    recipe["servings"] = request.new_servings
    
    # Scale nutrition
    if "nutrition_estimate" in recipe and recipe["nutrition_estimate"]:
        scale_factor = request.new_servings / original_servings
        nutrition = recipe["nutrition_estimate"]
        recipe["nutrition_estimate"] = {
            "calories_per_serving": round(nutrition.get("calories_per_serving", 0) * scale_factor, 1),
            "protein_grams": round(nutrition.get("protein_grams", 0) * scale_factor, 1),
            "carbs_grams": round(nutrition.get("carbs_grams", 0) * scale_factor, 1),
            "fat_grams": round(nutrition.get("fat_grams", 0) * scale_factor, 1)
        }
    
    return recipe


@app.post("/api/shopping-list")
async def create_shopping_list(request: ShoppingListRequest):
    """Generate a shopping list from recipes or meal plan"""
    shopping_list = generate_shopping_list(request.recipe_ids, request.meal_plan_id)
    return shopping_list


@app.get("/api/recipe/{recipe_id}/image")
async def get_recipe_image(recipe_id: str):
    """Generate and return recipe image URL"""
    if recipe_id not in recipes_storage:
        raise HTTPException(status_code=404, detail="Recipe not found")
    
    recipe = recipes_storage[recipe_id]
    
    # Check if image already exists
    if "image_url" in recipe:
        return {"image_url": recipe["image_url"]}
    
    # Generate new image
    image_url = await generate_recipe_image(
        recipe.get("name", ""),
        recipe.get("description", "")
    )
    
    if image_url:
        recipe["image_url"] = image_url
        return {"image_url": image_url}
    else:
        return {"image_url": None, "message": "Image generation not available or failed"}


@app.get("/api/meal-plan/{plan_id}/export-pdf")
async def export_meal_plan_pdf(plan_id: str):
    """Export meal plan as PDF"""
    if plan_id not in meal_plans_storage:
        raise HTTPException(status_code=404, detail="Meal plan not found")
    
    meal_plan = meal_plans_storage[plan_id]
    pdf_buffer = generate_meal_plan_pdf(meal_plan)
    
    return StreamingResponse(
        BytesIO(pdf_buffer.read()),
        media_type="application/pdf",
        headers={
            "Content-Disposition": f"attachment; filename=meal-plan-{plan_id}.pdf"
        }
    )


# Mount static files
app.mount("/static", StaticFiles(directory=CLIENT_STATIC_DIR), name="static")


if __name__ == "__main__":
    import uvicorn
    print("=" * 50)
    print("Starting Recipe Generator & Meal Planner Server...")
    print(f"Serving from: {BASE_DIR}")
    print("=" * 50)
    uvicorn.run(app, host="0.0.0.0", port=8001, log_level="info")
