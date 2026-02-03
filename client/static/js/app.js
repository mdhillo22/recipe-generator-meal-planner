// API base URL
const API_BASE = '/api';

// Tab switching
document.querySelectorAll('.tab-btn').forEach(btn => {
    btn.addEventListener('click', () => {
        const targetTab = btn.dataset.tab;
        
        // Update buttons
        document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        
        // Update content
        document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
        document.getElementById(`${targetTab}-tab`).classList.add('active');
    });
});

// Recipe form handler
document.getElementById('recipe-form').addEventListener('submit', async (e) => {
    e.preventDefault();
    
    const ingredients = document.getElementById('ingredients').value.split(',').map(i => i.trim()).filter(i => i);
    const cuisineType = document.getElementById('cuisine-type').value;
    const mealType = document.getElementById('meal-type').value;
    const servings = parseInt(document.getElementById('servings').value) || 4;
    const dietary = Array.from(document.querySelectorAll('input[name="dietary"]:checked')).map(cb => cb.value);
    
    // Show loading
    document.getElementById('recipe-loading').style.display = 'block';
    document.getElementById('recipe-result').style.display = 'none';
    
    try {
        const response = await fetch(`${API_BASE}/generate-recipe`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                ingredients,
                dietary_preferences: dietary.length > 0 ? dietary : null,
                cuisine_type: cuisineType || null,
                meal_type: mealType || null,
                servings
            })
        });
        
        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Failed to generate recipe');
        }
        
        const recipe = await response.json();
        displayRecipe(recipe);
        
    } catch (error) {
        showError('recipe-result', error.message);
    } finally {
        document.getElementById('recipe-loading').style.display = 'none';
    }
});

// Display recipe
function displayRecipe(recipe) {
    const container = document.getElementById('recipe-result');
    container.innerHTML = `
        <div class="recipe-header">
            <h3>${escapeHtml(recipe.name)}</h3>
            <div class="recipe-meta">
                <span>⏱️ Prep: ${recipe.prep_time_minutes} min</span>
                <span>🍳 Cook: ${recipe.cook_time_minutes} min</span>
                <span>👥 Serves: ${recipe.servings}</span>
                <span>🌍 ${recipe.cuisine || 'Various'}</span>
            </div>
            <p style="margin-top: 15px; color: #666;">${escapeHtml(recipe.description || '')}</p>
        </div>
        
        <div class="nutrition-box">
            <div class="nutrition-item">
                <div class="label">Calories</div>
                <div class="value">${recipe.nutrition_estimate?.calories_per_serving || 'N/A'}</div>
            </div>
            <div class="nutrition-item">
                <div class="label">Protein</div>
                <div class="value">${recipe.nutrition_estimate?.protein_grams || 'N/A'}g</div>
            </div>
            <div class="nutrition-item">
                <div class="label">Carbs</div>
                <div class="value">${recipe.nutrition_estimate?.carbs_grams || 'N/A'}g</div>
            </div>
            <div class="nutrition-item">
                <div class="label">Fat</div>
                <div class="value">${recipe.nutrition_estimate?.fat_grams || 'N/A'}g</div>
            </div>
        </div>
        
        <div class="ingredients-list">
            <h4>📋 Ingredients</h4>
            ${recipe.ingredients.map(ing => `
                <div class="ingredient-item">
                    <strong>${escapeHtml(ing.name)}</strong> - ${escapeHtml(ing.amount)} ${escapeHtml(ing.unit || '')}
                </div>
            `).join('')}
        </div>
        
        <div class="instructions-list">
            <h4>👨‍🍳 Instructions</h4>
            ${recipe.instructions.map(instruction => `
                <div class="instruction-item">
                    ${escapeHtml(instruction)}
                </div>
            `).join('')}
        </div>
        
        ${recipe.tags && recipe.tags.length > 0 ? `
            <div style="margin-top: 20px;">
                <strong>Tags:</strong> ${recipe.tags.map(tag => `<span style="background: #e0e0e0; padding: 5px 10px; border-radius: 5px; margin: 0 5px;">${escapeHtml(tag)}</span>`).join('')}
            </div>
        ` : ''}
    `;
    container.style.display = 'block';
}

// Meal plan form handler
document.getElementById('meal-plan-form').addEventListener('submit', async (e) => {
    e.preventDefault();
    
    const days = parseInt(document.getElementById('plan-days').value) || 7;
    const mealsPerDay = parseInt(document.getElementById('meals-per-day').value) || 3;
    const targetCalories = document.getElementById('target-calories').value ? parseInt(document.getElementById('target-calories').value) : null;
    const dietary = Array.from(document.querySelectorAll('input[name="plan-dietary"]:checked')).map(cb => cb.value);
    
    // Show loading
    document.getElementById('meal-plan-loading').style.display = 'block';
    document.getElementById('meal-plan-result').style.display = 'none';
    
    try {
        const response = await fetch(`${API_BASE}/generate-meal-plan`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                days,
                meals_per_day: mealsPerDay,
                target_calories: targetCalories,
                dietary_preferences: dietary.length > 0 ? dietary : null
            })
        });
        
        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Failed to generate meal plan');
        }
        
        const plan = await response.json();
        displayMealPlan(plan);
        
    } catch (error) {
        showError('meal-plan-result', error.message);
    } finally {
        document.getElementById('meal-plan-loading').style.display = 'none';
    }
});

// Display meal plan
function displayMealPlan(plan) {
    const container = document.getElementById('meal-plan-result');
    
    let html = '<div class="meal-plan-grid">';
    
    plan.days.forEach(day => {
        const date = new Date(day.date);
        const dayName = date.toLocaleDateString('en-US', { weekday: 'long' });
        const dateStr = date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
        
        html += `
            <div class="meal-day-card">
                <div class="meal-day-header">
                    <h4>Day ${day.day_number}</h4>
                    <div class="date">${dayName}, ${dateStr}</div>
                </div>
                
                ${day.meals.map(meal => `
                    <div class="meal-item">
                        <div class="meal-type">${meal.meal_type}</div>
                        <div class="meal-name">${escapeHtml(meal.name)}</div>
                        <div class="meal-description">${escapeHtml(meal.description || '')}</div>
                        <div class="meal-calories">🔥 ${meal.estimated_calories || 'N/A'} calories</div>
                    </div>
                `).join('')}
                
                <div class="day-summary">
                    Total: ${day.total_calories || 0} calories
                    ${plan.target_calories ? ` | Target: ${plan.target_calories}` : ''}
                </div>
            </div>
        `;
    });
    
    html += '</div>';
    
    // Add summary
    const totalCalories = plan.days.reduce((sum, day) => sum + (day.total_calories || 0), 0);
    const avgCalories = Math.round(totalCalories / plan.days.length);
    
    html = `
        <div class="card">
            <h2>📅 ${plan.total_days}-Day Meal Plan</h2>
            <div style="background: #e3f2fd; padding: 15px; border-radius: 8px; margin-bottom: 20px;">
                <strong>Summary:</strong> Average ${avgCalories} calories/day | Total ${totalCalories} calories
                ${plan.target_calories ? ` | Target: ${plan.target_calories} calories/day` : ''}
            </div>
        </div>
        ${html}
    `;
    
    container.innerHTML = html;
    container.style.display = 'block';
}

// Utility functions
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function showError(containerId, message) {
    const container = document.getElementById(containerId);
    container.innerHTML = `<div class="error-message">${escapeHtml(message)}</div>`;
    container.style.display = 'block';
}
