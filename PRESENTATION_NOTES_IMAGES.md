# Presentation Notes: Image Integration Challenges in Recipe Meal Planner

## Introduction
- **Project**: Recipe Generator & Meal Planner Web Application
- **Challenge**: Integrating relevant food images for recipes and meal plans
- **Goal**: Display accurate, appetizing images that match the recipes

---

## Problem 1: Images Not Showing Up

### Issues Encountered:
- **404 Errors**: Many image URLs returned "404 Not Found" errors
- **Broken Image Sources**: 
  - Unsplash Source API was deprecated and unreliable
  - Direct Unsplash image IDs started returning 404s
  - Foodish API was frequently down

### Examples:
```
Failed to load resource: 404 (Not Found)
Image failed to load: https://images.unsplash.com/photo-1606312615550...
Image failed to load: https://source.unsplash.com/800x600/?spaghetti,pasta
```

### Impact:
- Broken UI with missing image placeholders
- Users couldn't visualize their meal plans

---

## Problem 2: Images Not Being Food Related

### Initial Approach:
- Used **Picsum Photos** - a random placeholder image service
- Images were completely unrelated to food (landscapes, people, objects)
- Example: Caprese Salad recipe showing an entire crop field


---

## Problem 3: Images Being Food Related But Not Matching Recipes

- Images were food-related but didn't match the specific recipe
- Example: Spaghetti showing a pizza image

### Why This Happened:
1. **Database Limitations**: TheMealDB API has a finite number of recipes (~300 meals)
2. **Fallback Logic**: When exact match failed:
   - Random images from similar categories
   - Generic food images
   - Placeholder images
     were used
3. **Search Limitations**: 
   - Recipe names from AI didn't match database entries
   - Keyword matching was too broad
   - Category mapping was imprecise

---

## Our Attempted Solutions

### Solution Attempt 1: Multiple Image APIs
**Approach**: Tried several image services
- **Unsplash Source API**: Deprecated, unreliable
- **Foodish API**: Frequently down, limition on food categories
- **TheMealDB API**: Database limitions, exact matches almost never occured

**Result**: Got food images, however, different than the recipes

---

### Solution Attempt 2: Improved Search Strategies
**Approach**: Changed recipe name matching
- Full recipe name search
- First word extraction
- Keyword extraction (removing stop words)
- Category-based matching

**Implementation**:
```python
search_strategies = [
    recipe_name,  # Full name
    recipe_name.split()[0],  # First word
    food_keywords[:3]  # Top 3 keywords
]
```

**Result**: Better matching for common recipes, but still many misses

---

### Solution Attempt 3: Category Mapping
**Approach**: Map recipe types to image categories
- Pasta recipes → Pasta category
- Breakfast items → Breakfast category
- Chicken dishes → Chicken category

**Implementation**:
```python
category_map = {
    'pasta': 'Pasta',
    'chicken': 'Chicken',
    'breakfast': 'Breakfast',
    ...
}
```

**Result**: Still showed generic category images, not specific recipes

---

### Solution Attempt 4: Random Food Images as Fallback
**Approach**: If no match found, use random food image from TheMealDB
- Better than placeholder
- At least food-related

**Result**: Food-related images, however, still didn't match recipes

---

## The Final Solution: Make Images Optional

- Made images optional and disabled by default
- Users can opt-in if they want images

Decided that:
   - Wrong images are worse than no images
   - Transparency about limitations is important
   - Give users control

**Best Practices Applied:**
- **Fail Gracefully**: Works without images
- **User Control**: Let users decide if they want images
- **Honest Communication**: Warn users about limitations
- **Default to Safe**: Disable problematic features by default