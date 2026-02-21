@echo off
echo ========================================
echo Pizza Language Parser - Test Examples
echo ========================================
echo.

echo Test 1: Buy pizza dough with tomato sauce and cheese, mushrooms
echo Command: java PizzaLang "Buy pizza dough. Spread olive oil and tomato sauce. Top with cheese, mushrooms. Bake in a preheated oven. Now eat it!"
echo.
java PizzaLang "Buy pizza dough. Spread olive oil and tomato sauce. Top with cheese, mushrooms. Bake in a preheated oven. Now eat it!"
echo.
echo.

echo Test 2: Make dough with pesto sauce and spinach, mushrooms
echo Command: java PizzaLang "Mix, knead, rise and roll dough. Spread olive oil and pesto sauce. Top with spinach, mushrooms. Bake in a preheated oven. Now eat it!"
echo.
java PizzaLang "Mix, knead, rise and roll dough. Spread olive oil and pesto sauce. Top with spinach, mushrooms. Bake in a preheated oven. Now eat it!"
echo.
echo.

echo Test 3: Buy pizza dough with tomato sauce, NO toppings
echo Command: java PizzaLang "Buy pizza dough. Spread olive oil and tomato sauce. Bake in a preheated oven. Now eat it!"
echo.
java PizzaLang "Buy pizza dough. Spread olive oil and tomato sauce. Bake in a preheated oven. Now eat it!"
echo.
echo.

echo Test 4: Make dough with pesto sauce and single topping (pepperoni)
echo Command: java PizzaLang "Mix, knead, rise and roll dough. Spread olive oil and pesto sauce. Top with pepperoni. Bake in a preheated oven. Now eat it!"
echo.
java PizzaLang "Mix, knead, rise and roll dough. Spread olive oil and pesto sauce. Top with pepperoni. Bake in a preheated oven. Now eat it!"
echo.
echo.

echo Test 5: Multiple toppings (cheese, mushrooms, spinach, pepperoni)
echo Command: java PizzaLang "Buy pizza dough. Spread olive oil and tomato sauce. Top with cheese, mushrooms, spinach, pepperoni. Bake in a preheated oven. Now eat it!"
echo.
java PizzaLang "Buy pizza dough. Spread olive oil and tomato sauce. Top with cheese, mushrooms, spinach, pepperoni. Bake in a preheated oven. Now eat it!"
echo.
echo.

echo Test 6: ERROR CASE - Double period (should fail)
echo Command: java PizzaLang "Mix, knead, rise and roll dough.. Spread olive oil and pesto sauce. Top with spinach, mushrooms. Bake in a preheated oven. Now eat it!"
echo.
java PizzaLang "Mix, knead, rise and roll dough.. Spread olive oil and pesto sauce. Top with spinach, mushrooms. Bake in a preheated oven. Now eat it!"
echo.
echo.

echo ========================================
echo All tests completed!
echo ========================================
