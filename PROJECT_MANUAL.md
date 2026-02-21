# Project Manual — Recipe Generator & Meal Planner

## Table of Contents
1. Project Overview  
2. Key Features  
3. System Architecture  
4. Technology Stack  
5. Project Structure  
6. Installation and Setup  
7. Configuration  
8. API Documentation  
9. AI Integration  
10. Prompt Archive  
11. Testing  
12. Troubleshooting  

---

## 1. Project Overview
Recipe Generator & Meal Planner is a client/server web application that generates recipes from user-provided ingredients and dietary preferences. It can also generate multi-day meal plans. The backend is built with FastAPI and calls the Together.ai LLM API to produce structured JSON outputs. The frontend is a browser-based interface for collecting inputs and displaying results.

---

## 2. Key Features
- Generate recipes from ingredients  
- Dietary preferences: vegetarian, vegan, gluten-free, low-carb, keto, dairy-free  
- Optional cuisine type and meal type  
- Multi-day meal plan generation (1–14 days)  
- Basic nutrition estimation  
- Modern web-based interface  

---

## 3. System Architecture
Browser Client → FastAPI Server → Together.ai API → FastAPI Server → Browser Client  

1. User enters inputs in the browser  
2. Frontend sends POST request to backend  
3. Backend builds prompt and calls Together.ai  
4. Backend parses JSON response  
5. Frontend displays results  

---

## 4. Technology Stack
- Backend: Python, FastAPI, Uvicorn  
- Frontend: HTML, CSS, JavaScript  
- AI Service: Together.ai  
- Environment Management: python-dotenv  

---

## 5. Project Structure
```
recipe-meal-planner/
├── server/
├── client/
├── prompts/
├── README.md
└── PROJECT_MANUAL.md
```

---

## 6. Installation and Setup
From the server folder:

```bash
pip install -r requirements.txt
python main.py
```

Open in browser:

```bash
http://localhost:8001
```

## 7. Configuration

Set Together.ai API key using a .env file:

```bash
TOGETHER_AI_API_KEY=your_key_here
```

Do not commit this file.

## 8. API Documentation

- POST `/api/generate-recipe`
- POST `/api/generate-meal-plan`
- GET `/api/recipe/{id}`
- GET `/api/meal-plan/{id}`

## 9. AI Integration

Together.ai is used to generate recipes and meal plans using prompt templates that request structured JSON output.

## 10. Prompt Archive

Archived prompts are located in:

mini-projects/recipe-meal-planner/prompts/


Files:

design_prompts.md

coding_prompts.md

documentation_prompts.md

prompt_usage_notes.md


## 11. Testing

- Generated recipe using chicken, rice, broccoli  
- Generated 3-day meal plan with 3 meals/day  
- Verified outputs appear in UI  


## 12. Troubleshooting

Verify API key is set

Verify dependencies installed

Ensure port 8001 is free

