# Installing JavaCC

Since JavaCC is not installed on your system, you have a few options:

## Option 1: Download JavaCC JAR (Recommended)

1. **Download JavaCC**:
   - Go to: https://github.com/javacc/javacc/releases
   - Download the latest version (e.g., `javacc-7.0.13.jar`)
   - Save it as `javacc.jar` in this directory (`parsing-assignment`)

2. **Compile using the batch script**:
   ```cmd
   compile-with-javacc.bat
   ```

   Or manually:
   ```cmd
   java -cp javacc.jar javacc PizzaLang.jj
   javac *.java
   ```

## Option 2: Install JavaCC globally

1. **Download JavaCC**:
   - Go to: https://github.com/javacc/javacc/releases
   - Download the zip file (e.g., `javacc-7.0.13.zip`)

2. **Extract and add to PATH**:
   - Extract to a location like `C:\Program Files\javacc`
   - Add `C:\Program Files\javacc\bin` to your Windows PATH
   - Restart PowerShell/Command Prompt

3. **Verify installation**:
   ```cmd
   javacc
   ```

4. **Compile**:
   ```cmd
   javacc PizzaLang.jj
   javac *.java
   ```

## Option 3: Use Maven (if you have Maven installed)

If you have Maven installed, you can use it to run JavaCC:

```cmd
mvn org.apache.maven.plugins:maven-dependency-plugin:3.2.0:get -Dartifact=net.java.dev.javacc:javacc:7.0.13
mvn org.apache.maven.plugins:maven-dependency-plugin:3.2.0:copy -Dartifact=net.java.dev.javacc:javacc:7.0.13 -DoutputDirectory=. -Dmdep.stripVersion=true -Dmdep.fileName=javacc.jar
java -cp javacc.jar javacc PizzaLang.jj
javac *.java
```

## Quick Start (After JavaCC is available)

Once you have `javacc.jar` in this directory, just run:

```cmd
compile-with-javacc.bat
```

Or manually:
```cmd
java -cp javacc.jar javacc PizzaLang.jj
javac *.java
java PizzaLang "Buy pizza dough. Spread olive oil and tomato sauce. Top with cheese, mushrooms. Bake in a preheated oven. Now eat it!"
```
