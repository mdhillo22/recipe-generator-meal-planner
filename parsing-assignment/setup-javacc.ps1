# PowerShell script to download and setup JavaCC
Write-Host "Setting up JavaCC..." -ForegroundColor Green

$javaccVersion = "7.0.13"
# Use Maven Central repository (more reliable)
$javaccUrl = "https://repo1.maven.org/maven2/net/java/dev/javacc/javacc/$javaccVersion/javacc-$javaccVersion.jar"
$javaccJar = "javacc.jar"

# Check if javacc.jar already exists
if (Test-Path $javaccJar) {
    Write-Host "JavaCC JAR already exists. Skipping download." -ForegroundColor Yellow
} else {
    Write-Host "Downloading JavaCC $javaccVersion from Maven Central..." -ForegroundColor Cyan
    try {
        Invoke-WebRequest -Uri $javaccUrl -OutFile $javaccJar
        Write-Host "Download complete!" -ForegroundColor Green
    } catch {
        Write-Host "Error downloading JavaCC: $_" -ForegroundColor Red
        Write-Host "Please download manually from: https://github.com/javacc/javacc/releases" -ForegroundColor Yellow
        exit 1
    }
}

Write-Host "JavaCC setup complete!" -ForegroundColor Green
Write-Host "You can now compile with: java -cp javacc.jar javacc PizzaLang.jj" -ForegroundColor Cyan
