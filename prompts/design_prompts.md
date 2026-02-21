# Design Prompts - Recipe Generator & Meal Planner

## Initial System Design

**Prompt**: "Design a client/server web application for a recipe generator and meal planner that:
- Generates recipes from user-provided ingredients using LLM (together.ai)
- Supports dietary preferences (vegetarian, vegan, gluten-free, etc.)
- Creates weekly meal plans with multiple meals per day
- Calculates nutrition information for recipes
- Has a modern, visually appealing interface with recipe cards and calendar-style meal planning

Use FastAPI/uvicorn for the server and a responsive web interface. Design the architecture, data flow, and key components."

## UI/UX Design

**Prompt**: "Design a modern, user-friendly interface for a recipe and meal planning application. The interface should:
- Have tabbed navigation between recipe generation and meal planning
- Display recipes with ingredients, instructions, and nutrition in an easy-to-read format
- Show meal plans in a calendar/grid layout
- Be visually appealing with food-themed colors
- Be responsive and work on mobile devices

Create a clean, professional design that makes recipe and meal planning enjoyable."

## Data Structure Design

**Prompt**: "Design data structures for:
1. Recipe generation response (name, ingredients, instructions, nutrition)
2. Meal plan response (days, meals, nutrition totals)
3. User input (ingredients, dietary preferences, meal type)

These should be JSON-compatible Python data structures that work well with LLM responses and web APIs."
