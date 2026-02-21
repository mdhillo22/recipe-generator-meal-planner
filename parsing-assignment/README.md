# Parsing Assignment - Pizza Language Parser

This assignment implements a top-down parser for a Pizza Language using JavaCC.

## Files

- `grammar-analysis.md` - Grammar transformation, parsing table, and parsing steps
- `PizzaLang.jj` - JavaCC grammar file
- `DoughSource.java` - Enumeration for dough sources
- `Sauce.java` - Enumeration for sauces
- `Toppings.java` - Enumeration for toppings
- `Pizza.java` - Pizza class to track ingredients

## Compilation

### Option 1: Using the provided batch script (Recommended for Windows)
```bash
compile-with-javacc.bat
```
This script will automatically download JavaCC if needed and compile everything.

### Option 2: Manual compilation

1. **Download JavaCC** (if not already downloaded):
   - Download from: https://github.com/javacc/javacc/releases
   - Get version 7.0.13 or later
   - Save the JAR file as `javacc.jar` in this directory

2. **Compile the JavaCC grammar file**:
   ```bash
   java -cp javacc.jar javacc PizzaLang.jj
   ```

3. **Compile all Java files**:
   ```bash
   javac *.java
   ```

### Option 3: If JavaCC is installed in your PATH
```bash
javacc PizzaLang.jj
javac *.java
```

## Usage

Run the parser with a pizza language sentence wrapped in double quotes:

```bash
java PizzaLang "Buy pizza dough. Spread olive oil and tomato sauce. Top with cheese, mushrooms. Bake in a preheated oven. Now eat it!"
```

Expected output:
```
Enjoy your pizza of bought dough with tomato sauce and topped with cheese and mushrooms
```

Another example:
```bash
java PizzaLang "Mix, knead, rise and roll dough. Spread olive oil and pesto sauce. Top with spinach, mushrooms. Bake in a preheated oven. Now eat it!"
```

Expected output:
```
Enjoy your pizza of made dough with pesto sauce and topped with spinach and mushrooms
```

## Grammar

The parser recognizes the following grammar:

- **Paragraph** -> Dough Spread Toppings Bake Eat
- **Dough** -> "Buy pizza dough." | "Mix, knead, rise and roll dough."
- **Spread** -> "Spread olive oil and" Sauce
- **Sauce** -> "tomato sauce." | "pesto sauce."
- **Toppings** -> "Top with" TopList | (lambda)
- **TopList** -> (cheese | mushrooms | spinach | pepperoni) TopCont
- **TopCont** -> "," (cheese | mushrooms | spinach | pepperoni) TopCont | "."
- **Bake** -> "Bake in a preheated oven."
- **Eat** -> "Now eat it!"

## Error Handling

If the input doesn't match the grammar, the parser will output an error message:
```
ParseException: ... No pizza for you!
```
