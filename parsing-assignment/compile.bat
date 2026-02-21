@echo off
echo Compiling JavaCC grammar...
javacc PizzaLang.jj
if %errorlevel% neq 0 (
    echo JavaCC compilation failed!
    exit /b 1
)

echo Compiling Java files...
javac *.java
if %errorlevel% neq 0 (
    echo Java compilation failed!
    exit /b 1
)

echo Compilation successful!
echo.
echo You can now run the parser with:
echo   java PizzaLang "Buy pizza dough. Spread olive oil and tomato sauce. Top with cheese, mushrooms. Bake in a preheated oven. Now eat it!"
