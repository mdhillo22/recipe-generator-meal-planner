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
    const isFavorite = window.favoriteRecipeIds && window.favoriteRecipeIds.includes(recipe.recipe_id);
    
    container.innerHTML = `
        <div class="recipe-header">
            <div style="display: flex; justify-content: space-between; align-items: start;">
                <h3>${escapeHtml(recipe.name)}</h3>
                <div style="display: flex; gap: 10px;">
                    <button class="btn btn-secondary" onclick="toggleFavorite('${recipe.recipe_id}')" id="favorite-btn-${recipe.recipe_id}">
                        ${isFavorite ? '⭐ Unfavorite' : '☆ Favorite'}
                    </button>
                    <button class="btn btn-secondary" onclick="saveRecipe('${recipe.recipe_id}')">💾 Save</button>
                </div>
            </div>
            <div class="recipe-meta">
                <span>⏱️ Prep: ${recipe.prep_time_minutes} min</span>
                <span>🍳 Cook: ${recipe.cook_time_minutes} min</span>
                <span>👥 Serves: ${recipe.servings}</span>
                <span>🌍 ${recipe.cuisine || 'Various'}</span>
            </div>
            <div style="margin-top: 15px; display: flex; gap: 15px; align-items: center;">
                <label for="scale-servings-${recipe.recipe_id}">Scale to servings:</label>
                <input type="number" id="scale-servings-${recipe.recipe_id}" min="1" max="50" value="${recipe.servings}" style="width: 80px; padding: 5px;">
                <button class="btn btn-secondary" onclick="scaleRecipe('${recipe.recipe_id}', ${recipe.servings})">Scale Recipe</button>
            </div>
            <p style="margin-top: 15px; color: #666;">${escapeHtml(recipe.description || '')}</p>
        </div>
        
        <div style="margin: 20px 0; text-align: center;">
            ${recipe.image_url ? `
                <div>
                    <img src="${recipe.image_url}" 
                         alt="${escapeHtml(recipe.name)}" 
                         style="max-width: 100%; border-radius: 10px; box-shadow: 0 5px 15px rgba(0,0,0,0.2);"
                         onerror="this.style.display='none'; this.parentElement.nextElementSibling.style.display='block';">
                    <div style="font-size: 0.75em; color: #999; margin-top: 5px; font-style: italic;">
                        ${recipe.image_url.includes('themealdb.com') ? 'Image: TheMealDB (themealdb.com)' : 
                          recipe.image_url.includes('foodish-api') ? 'Image: Foodish API (foodish-api.herokuapp.com)' : 
                          recipe.image_url.includes('openai') ? 'Image: OpenAI DALL-E' : 
                          recipe.image_url.includes('placehold') ? 'Image: Placeholder' : 
                          'Image: External Source'}
                    </div>
                </div>
                <div style="display: none;">
                    <p style="color: #666; margin-bottom: 10px;">Image failed to load</p>
                    <button class="btn btn-secondary" onclick="generateRecipeImage('${recipe.recipe_id}')">🖼️ Generate New Image</button>
                </div>
            ` : `
                <button class="btn btn-secondary" onclick="generateRecipeImage('${recipe.recipe_id}')">🖼️ Generate Image</button>
            `}
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
    const includeImages = document.getElementById('include-images').checked;
    
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
                dietary_preferences: dietary.length > 0 ? dietary : null,
                include_images: includeImages
            })
        });
        
        if (!response.ok) {
            let errorMessage = `Failed to generate meal plan (Status: ${response.status})`;
            try {
                const errorData = await response.json();
                console.error('Meal plan error response:', errorData);
                errorMessage = errorData.detail || errorData.message || errorData.error || errorMessage;
                if (!errorMessage || errorMessage === 'Failed to generate meal plan') {
                    errorMessage = `Server returned error ${response.status}. Check server logs for details.`;
                }
            } catch (e) {
                const text = await response.text();
                console.error('Failed to parse error response. Raw text:', text);
                errorMessage = `Server error: ${response.status} ${response.statusText}. Response: ${text.substring(0, 200)}`;
            }
            throw new Error(errorMessage);
        }
        
        const plan = await response.json();
        console.log('Meal plan received:', plan);
        displayMealPlan(plan);
        
    } catch (error) {
        console.error('Error generating meal plan:', error);
        const errorMsg = error.message || 'Unknown error occurred. Please try again.';
        showError('meal-plan-result', `Error: ${errorMsg}`);
        alert(`Failed to generate meal plan:\n\n${errorMsg}\n\nPlease check the browser console (F12) for more details.`);
    } finally {
        document.getElementById('meal-plan-loading').style.display = 'none';
    }
});

// Display meal plan
function displayMealPlan(plan) {
    const container = document.getElementById('meal-plan-result');
    
    let html = '<div class="meal-plan-grid">';
    
    plan.days.forEach(day => {
        // Parse date consistently - handle date-only strings (YYYY-MM-DD)
        let date;
        if (day.date && day.date.length === 10) {
            // Date-only string, parse as local date (not UTC)
            const [year, month, dayNum] = day.date.split('-').map(Number);
            date = new Date(year, month - 1, dayNum);
        } else {
            date = new Date(day.date || new Date());
        }
        const dayName = date.toLocaleDateString('en-US', { weekday: 'long' });
        const dateStr = date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
        
        html += `
            <div class="meal-day-card">
                <div class="meal-day-header">
                    <h4>Day ${day.day_number}</h4>
                    <div class="date">${dayName}, ${dateStr}</div>
                </div>
                
                ${day.meals.map(meal => {
                    // Debug: log meal data
                    console.log('Meal data:', meal);
                    const hasIngredients = meal.ingredients && Array.isArray(meal.ingredients) && meal.ingredients.length > 0;
                    const hasInstructions = meal.instructions && Array.isArray(meal.instructions) && meal.instructions.length > 0;
                    
                    return `
                    <div class="meal-item" style="margin-bottom: 20px; padding: 15px; background: #f8f9fa; border-radius: 8px;">
                        <div class="meal-type" style="font-weight: 600; color: #667eea; text-transform: capitalize; margin-bottom: 5px;">${escapeHtml(meal.meal_type || 'Meal')}</div>
                        <div class="meal-name" style="font-size: 1.2em; font-weight: 600; margin: 10px 0; color: #333;">${escapeHtml(meal.name || 'Unnamed Meal')}</div>
                        ${meal.image_url ? `
                        <div style="margin: 10px 0; text-align: center;">
                            <img src="${meal.image_url}" 
                                 alt="${escapeHtml(meal.name)}" 
                                 style="max-width: 100%; max-height: 200px; border-radius: 8px; box-shadow: 0 3px 10px rgba(0,0,0,0.1); object-fit: cover;"
                                 onerror="console.error('Image failed to load:', this.src); this.parentElement.innerHTML='';"
                                 onload="console.log('Image loaded successfully:', this.src);">
                            <div style="font-size: 0.75em; color: #999; margin-top: 5px; font-style: italic;">
                                ${meal.image_url.includes('themealdb.com') ? 'Image: TheMealDB (themealdb.com)' : 
                                  meal.image_url.includes('foodish-api') ? 'Image: Foodish API' : 
                                  meal.image_url.includes('openai') ? 'Image: OpenAI DALL-E' : 
                                  meal.image_url.includes('placehold') ? 'Image: Placeholder' : 
                                  'Image: External Source'}
                            </div>
                        </div>
                        ` : ''}
                        <div class="meal-description" style="color: #666; margin: 10px 0;">${escapeHtml(meal.description || 'No description available')}</div>
                        <div class="meal-calories" style="color: #28a745; font-weight: 600; margin: 10px 0;">🔥 ${meal.estimated_calories || 'N/A'} calories</div>
                        ${hasIngredients ? `
                            <div style="margin-top: 15px; padding: 10px; background: white; border-radius: 5px;">
                                <h5 style="color: #667eea; margin-bottom: 8px; font-size: 1em;">📋 Ingredients:</h5>
                                <ul style="margin: 0; padding-left: 20px;">
                                    ${meal.ingredients.map(ing => `
                                        <li style="margin: 5px 0;">${escapeHtml(ing.name || 'Ingredient')}${ing.amount ? ` - ${escapeHtml(ing.amount)}` : ''}${ing.unit ? ` ${escapeHtml(ing.unit)}` : ''}</li>
                                    `).join('')}
                                </ul>
                            </div>
                        ` : '<div style="margin-top: 10px; padding: 10px; background: #fff3cd; border-radius: 5px; color: #856404;">⚠️ Ingredients not available for this meal</div>'}
                        ${hasInstructions ? `
                            <div style="margin-top: 15px; padding: 10px; background: white; border-radius: 5px;">
                                <h5 style="color: #667eea; margin-bottom: 8px; font-size: 1em;">👨‍🍳 Instructions:</h5>
                                <ol style="margin: 0; padding-left: 20px;">
                                    ${meal.instructions.map((inst, idx) => `
                                        <li style="margin: 5px 0;">${escapeHtml(inst || `Step ${idx + 1}`)}</li>
                                    `).join('')}
                                </ol>
                            </div>
                        ` : '<div style="margin-top: 10px; padding: 10px; background: #fff3cd; border-radius: 5px; color: #856404;">⚠️ Instructions not available for this meal</div>'}
                        ${meal.prep_time_minutes || meal.cook_time_minutes || meal.servings ? `
                            <div style="margin-top: 10px; color: #666; font-size: 0.9em; padding: 8px; background: #e9ecef; border-radius: 5px;">
                                ${meal.prep_time_minutes ? `⏱️ Prep: ${meal.prep_time_minutes} min` : ''}
                                ${meal.prep_time_minutes && meal.cook_time_minutes ? ' | ' : ''}
                                ${meal.cook_time_minutes ? `🍳 Cook: ${meal.cook_time_minutes} min` : ''}
                                ${meal.servings ? ` | 👥 Serves: ${meal.servings}` : ''}
                            </div>
                        ` : ''}
                    </div>
                `;
                }).join('')}
                
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
            <div style="display: flex; justify-content: space-between; align-items: center;">
                <h2>📅 ${plan.total_days}-Day Meal Plan</h2>
                <button class="btn btn-primary" onclick="exportMealPlanPDF('${plan.plan_id}')">📄 Export PDF</button>
            </div>
            <div style="background: #e3f2fd; padding: 15px; border-radius: 8px; margin-bottom: 20px;">
                <strong>Summary:</strong> Average ${avgCalories} calories/day | Total ${totalCalories} calories
                ${plan.target_calories ? ` | Target: ${plan.target_calories} calories/day` : ''}
            </div>
            <div style="margin-bottom: 15px;">
                <button class="btn btn-secondary" onclick="generateShoppingListFromPlan('${plan.plan_id}')">🛒 Generate Shopping List</button>
            </div>
        </div>
        ${html}
    `;
    
    container.innerHTML = html;
    container.style.display = 'block';
    window.currentMealPlan = plan;
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

// Favorite functions
async function toggleFavorite(recipeId) {
    try {
        const response = await fetch(`${API_BASE}/recipe/${recipeId}/favorite`, {
            method: 'POST'
        });
        const data = await response.json();
        
        if (!window.favoriteRecipeIds) {
            window.favoriteRecipeIds = [];
        }
        
        if (data.is_favorite) {
            if (!window.favoriteRecipeIds.includes(recipeId)) {
                window.favoriteRecipeIds.push(recipeId);
            }
        } else {
            window.favoriteRecipeIds = window.favoriteRecipeIds.filter(id => id !== recipeId);
        }
        
        const btn = document.getElementById(`favorite-btn-${recipeId}`);
        if (btn) {
            btn.textContent = data.is_favorite ? '⭐ Unfavorite' : '☆ Favorite';
        }
        
        // Reload favorites if on favorites tab
        if (document.getElementById('favorites-tab').classList.contains('active')) {
            loadFavorites();
        }
    } catch (error) {
        alert('Error toggling favorite: ' + error.message);
    }
}

async function saveRecipe(recipeId) {
    try {
        const response = await fetch(`${API_BASE}/recipe/${recipeId}/save`, {
            method: 'POST'
        });
        const data = await response.json();
        alert('Recipe saved successfully!');
    } catch (error) {
        alert('Error saving recipe: ' + error.message);
    }
}

async function scaleRecipe(recipeId, currentServings) {
    const newServings = parseInt(document.getElementById(`scale-servings-${recipeId}`).value);
    if (!newServings || newServings < 1) {
        alert('Please enter a valid number of servings');
        return;
    }
    
    try {
        const response = await fetch(`${API_BASE}/scale-recipe`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                recipe_id: recipeId,
                new_servings: newServings
            })
        });
        
        if (!response.ok) {
            throw new Error('Failed to scale recipe');
        }
        
        const scaledRecipe = await response.json();
        displayRecipe(scaledRecipe);
    } catch (error) {
        alert('Error scaling recipe: ' + error.message);
    }
}

async function generateMealImage(recipeId, mealName) {
    // For meal plan meals, we need to generate image via API
    try {
        const response = await fetch(`${API_BASE}/recipe/${recipeId}/image`);
        const data = await response.json();
        if (data.image_url) {
            // Reload the meal plan to show the image
            if (window.currentMealPlan && window.currentMealPlan.plan_id) {
                const planResponse = await fetch(`${API_BASE}/meal-plan/${window.currentMealPlan.plan_id}`);
                const plan = await planResponse.json();
                displayMealPlan(plan);
            }
        }
    } catch (error) {
        alert('Error generating image: ' + error.message);
    }
}

async function generateRecipeImage(recipeId) {
    try {
        // Show loading state
        const btn = event?.target || document.querySelector(`button[onclick*="${recipeId}"]`);
        if (btn) {
            const originalText = btn.textContent;
            btn.textContent = 'Generating...';
            btn.disabled = true;
        }
        
        const response = await fetch(`${API_BASE}/recipe/${recipeId}/image`);
        const data = await response.json();
        
        if (data.image_url) {
            // Reload the recipe to show the image
            const recipeResponse = await fetch(`${API_BASE}/recipe/${recipeId}`);
            const recipe = await recipeResponse.json();
            displayRecipe(recipe);
        } else {
            alert('Image generation failed. The system will try to use a placeholder image.');
            // Try to reload anyway in case a fallback was added
            const recipeResponse = await fetch(`${API_BASE}/recipe/${recipeId}`);
            const recipe = await recipeResponse.json();
            displayRecipe(recipe);
        }
    } catch (error) {
        alert('Error generating image: ' + error.message);
    }
}

async function loadFavorites() {
    try {
        const response = await fetch(`${API_BASE}/favorites`);
        const data = await response.json();
        
        const container = document.getElementById('favorites-list');
        if (data.favorites.length === 0) {
            container.innerHTML = '<p>No favorite recipes yet. Click the favorite button on any recipe to add it here.</p>';
            return;
        }
        
        container.innerHTML = data.favorites.map(recipe => `
            <div class="recipe-result" style="margin-bottom: 20px;">
                <div class="recipe-header">
                    <h3>${escapeHtml(recipe.name)}</h3>
                    <button class="btn btn-secondary" onclick="toggleFavorite('${recipe.recipe_id}')">⭐ Unfavorite</button>
                </div>
                <p>${escapeHtml(recipe.description || '')}</p>
                <button class="btn btn-primary" onclick="viewRecipe('${recipe.recipe_id}')">View Recipe</button>
            </div>
        `).join('');
    } catch (error) {
        document.getElementById('favorites-list').innerHTML = `<div class="error-message">Error loading favorites: ${error.message}</div>`;
    }
}

async function viewRecipe(recipeId) {
    try {
        const response = await fetch(`${API_BASE}/recipe/${recipeId}`);
        const recipe = await response.json();
        
        // Switch to recipes tab and display
        document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
        document.querySelector('[data-tab="recipes"]').classList.add('active');
        document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
        document.getElementById('recipes-tab').classList.add('active');
        
        displayRecipe(recipe);
    } catch (error) {
        alert('Error loading recipe: ' + error.message);
    }
}

// Shopping list functions
async function loadRecipesForShoppingList() {
    try {
        const response = await fetch(`${API_BASE}/recipes`);
        const data = await response.json();
        
        const select = document.getElementById('recipe-select');
        select.innerHTML = data.recipes.map(recipe => 
            `<option value="${recipe.recipe_id}">${escapeHtml(recipe.name)}</option>`
        ).join('');
    } catch (error) {
        document.getElementById('recipe-select').innerHTML = '<option value="">Error loading recipes</option>';
    }
}

document.getElementById('shopping-list-form').addEventListener('submit', async (e) => {
    e.preventDefault();
    
    const selectedRecipes = Array.from(document.getElementById('recipe-select').selectedOptions)
        .map(opt => opt.value)
        .filter(v => v);
    
    if (selectedRecipes.length === 0) {
        alert('Please select at least one recipe');
        return;
    }
    
    try {
        const response = await fetch(`${API_BASE}/shopping-list`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                recipe_ids: selectedRecipes
            })
        });
        
        if (!response.ok) {
            throw new Error('Failed to generate shopping list');
        }
        
        const shoppingList = await response.json();
        displayShoppingList(shoppingList);
    } catch (error) {
        showError('shopping-list-result', error.message);
    }
});

function displayShoppingList(shoppingList) {
    const container = document.getElementById('shopping-list-result');
    container.innerHTML = `
        <div class="card" style="margin-top: 20px;">
            <h3>🛒 Shopping List (${shoppingList.total_items} items)</h3>
            <div class="ingredients-list">
                ${shoppingList.items.map(item => `
                    <div class="ingredient-item">
                        <strong>${escapeHtml(item.name)}</strong>
                        ${item.amount ? ` - ${escapeHtml(item.amount)} ${escapeHtml(item.unit || '')}` : ''}
                        ${item.count > 1 ? ` <span style="color: #667eea;">(used in ${item.count} recipe${item.count > 1 ? 's' : ''})</span>` : ''}
                    </div>
                `).join('')}
            </div>
        </div>
    `;
    container.style.display = 'block';
}

async function generateShoppingListFromPlan(planId) {
    try {
        const response = await fetch(`${API_BASE}/shopping-list`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                meal_plan_id: planId
            })
        });
        
        if (!response.ok) {
            throw new Error('Failed to generate shopping list');
        }
        
        const shoppingList = await response.json();
        alert(`Shopping list generated with ${shoppingList.total_items} items! Switch to the Shopping List tab to view it.`);
    } catch (error) {
        alert('Error generating shopping list: ' + error.message);
    }
}

async function exportMealPlanPDF(planId) {
    try {
        const response = await fetch(`${API_BASE}/meal-plan/${planId}/export-pdf`);
        const blob = await response.blob();
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `meal-plan-${planId}.pdf`;
        document.body.appendChild(a);
        a.click();
        window.URL.revokeObjectURL(url);
        document.body.removeChild(a);
    } catch (error) {
        alert('Error exporting PDF: ' + error.message);
    }
}

// Initialize favorites list and shopping list recipes on tab switch
document.querySelectorAll('.tab-btn').forEach(btn => {
    btn.addEventListener('click', () => {
        const targetTab = btn.dataset.tab;
        if (targetTab === 'favorites') {
            loadFavorites();
        } else if (targetTab === 'shopping-list') {
            loadRecipesForShoppingList();
        }
    });
});

// Initialize favorites
window.favoriteRecipeIds = [];
loadFavorites();
