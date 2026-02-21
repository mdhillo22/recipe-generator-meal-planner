@echo off
echo Compiling JavaCC grammar...

REM Check if javacc.jar exists
if not exist javacc.jar (
    echo JavaCC JAR not found. Attempting to download...
    powershell -ExecutionPolicy Bypass -File setup-javacc.ps1
    if not exist javacc.jar (
        echo.
        echo Download failed. Please download JavaCC manually:
        echo 1. Go to: https://github.com/javacc/javacc/releases
        echo 2. Download javacc-7.0.13.jar (or latest version)
        echo 3. Save it as javacc.jar in this directory
        echo.
        echo See INSTALL_JAVACC.md for detailed instructions.
        exit /b 1
    )
)

REM Compile with JavaCC
java -cp javacc.jar javacc PizzaLang.jj
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

echo.
echo Compilation successful!
echo.
echo You can now run the parser with:
echo   java PizzaLang "Buy pizza dough. Spread olive oil and tomato sauce. Top with cheese, mushrooms. Bake in a preheated oven. Now eat it!"
