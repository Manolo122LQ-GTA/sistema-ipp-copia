<#
.SYNOPSIS
    Instalador automático del Sistema IPP para Windows 10/11
.DESCRIPTION
    Verifica Python 3.13 y MySQL 8.4+ (o MariaDB 10.6+), instala dependencias,
    genera los estaticos, migra la BD y deja el sistema listo para usar.
.NOTES
    Ejecutar como Administrador. Se necesita tener MySQL/MariaDB instalado
    (XAMPP incluye MariaDB) o saber la contraseña de root.
#>

#Requires -RunAsAdministrator

$ErrorActionPreference = "Stop"
$ProjectDir = Split-Path -Parent $MyInvocation.MyCommand.Path
# No se usa Start-Transcript: el transcript guardaría la contraseña de MySQL en texto plano.
$LogFile = "$env:TEMP\ipp_instalacion.log"

Write-Host "============================================" -ForegroundColor Cyan
Write-Host "  INSTALADOR AUTOMATICO SISTEMA IPP" -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan
Write-Host ""

# ------- 1. VERIFICAR / INSTALAR PYTHON -------
Write-Host "[1/7] Verificando Python 3.13..."
$pythonExe = $null
try { $pythonExe = (& py -3.13 -c "import sys; print(sys.executable)" 2>$null).Trim() } catch {}
if (-not $pythonExe) {
    Write-Host "  > Python 3.13 no encontrado. Instalando..."
    $pyUrl = "https://www.python.org/ftp/python/3.13.5/python-3.13.5-amd64.exe"
    $pyInstaller = "$env:TEMP\python-3.13.5-amd64.exe"
    if (-not (Test-Path $pyInstaller)) {
        Invoke-WebRequest -Uri $pyUrl -OutFile $pyInstaller
    }
    Start-Process -Wait -FilePath $pyInstaller -ArgumentList "/quiet InstallAllUsers=1 PrependPath=1"
    $env:Path = [Environment]::GetEnvironmentVariable("Path","Machine") + ";" + [Environment]::GetEnvironmentVariable("Path","User")
    try { $pythonExe = (& py -3.13 -c "import sys; print(sys.executable)" 2>$null).Trim() } catch {}
    if (-not $pythonExe) {
        Write-Host "  ERROR: no se pudo instalar Python 3.13." -ForegroundColor Red
        exit 1
    }
}
Write-Host "  OK: $pythonExe"

# ------- 2. VERIFICAR MYSQL / MARIADB -------
Write-Host "[2/7] Verificando MySQL/MariaDB..."
$mysqlClient = $null
$candidates = @()
try {
    $cmd = Get-Command mysql.exe -ErrorAction SilentlyContinue
    if ($cmd) { $candidates += $cmd.Source }
} catch {}
$candidates += @(
    "C:\Program Files\MySQL\MySQL Server 8.4\bin\mysql.exe",
    "C:\Program Files\MySQL\MySQL Server 8.0\bin\mysql.exe",
    "C:\xampp\mysql\bin\mysql.exe"
)
foreach ($c in $candidates) {
    if ($c -and (Test-Path $c)) { $mysqlClient = $c; break }
}
if (-not $mysqlClient) {
    Write-Host "  ERROR: no se encontro mysql.exe." -ForegroundColor Red
    Write-Host "  Instale MySQL 8.4+ o MariaDB 10.6+ (XAMPP trae MariaDB) y vuelva a ejecutar." -ForegroundColor Yellow
    exit 1
}
Write-Host "  OK: $mysqlClient"

$mysqlPassword = Read-Host -Prompt "  Contrasena de root de MySQL (Enter si no tiene)" -AsSecureString
# Convertida solo en memoria y liberada inmediatamente; nunca se escribe en logs.
$bstrPassword = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($mysqlPassword)
try {
    $mysqlPasswordPlain = [Runtime.InteropServices.Marshal]::PtrToStringAuto($bstrPassword)
} finally {
    [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($bstrPassword)
}
# MYSQL_PWD evita pasar la contrasena en la linea de comandos (visible en el proceso).
$env:MYSQL_PWD = $mysqlPasswordPlain

# ------- 3. INICIAR SERVICIO, VALIDAR VERSION Y CREAR BD -------
Write-Host "[3/7] Asegurando que MySQL este corriendo..."
$svc = Get-Service -ErrorAction SilentlyContinue | Where-Object { $_.Name -match 'mysql|mariadb' -and $_.Status -ne 'Running' }
if ($svc) {
    Start-Service $svc.Name
    Start-Sleep 2
}
$version = (& $mysqlClient -u root -N -B -e "SELECT VERSION();" 2>$null)
if ($LASTEXITCODE -ne 0 -or -not $version) {
    Write-Host "  ERROR: no se pudo conectar con MySQL. Revise la contrasena de root." -ForegroundColor Red
    exit 1
}
$isMaria = $version -match 'mariadb'
$m = [regex]::Match($version, '(\d+)\.(\d+)\.(\d+)')
$major = [int]$m.Groups[1].Value
$minor = [int]$m.Groups[2].Value
$soportado = if ($isMaria) { $major -gt 10 -or ($major -eq 10 -and $minor -ge 6) } else { $major -ge 8 }
if (-not $soportado) {
    Write-Host "  ERROR: Django 6 requiere MySQL 8+ o MariaDB 10.6+ (encontrado: $version)." -ForegroundColor Red
    exit 1
}
Write-Host "  OK: $version"

Write-Host "  Creando base de datos ippbd..."
& $mysqlClient -u root -e "CREATE DATABASE IF NOT EXISTS ippbd CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"
if ($LASTEXITCODE -ne 0) {
    Write-Host "  ERROR al crear la base de datos." -ForegroundColor Red
    exit 1
}
Write-Host "  OK: ippbd lista."

# ------- 4. INSTALAR DEPENDENCIAS Y GENERAR ESTATICOS -------
Write-Host "[4/7] Instalando dependencias Python..."
Set-Location -Path $ProjectDir

$venvPython = Join-Path $ProjectDir "venv\Scripts\python.exe"
if (-not (Test-Path $venvPython)) {
    Write-Host "  > Creando virtualenv..."
    & $pythonExe -m venv venv
}
& $venvPython -m pip install -r requirements.txt 2>&1 | Out-Host
if ($LASTEXITCODE -ne 0) {
    Write-Host "  ERROR al instalar dependencias." -ForegroundColor Red
    exit 1
}
& $venvPython -m pip check 2>&1 | Out-Host
Write-Host "  OK: Dependencias instaladas."

$envFile = Join-Path $ProjectDir '.env'
if (-not (Test-Path $envFile)) {
    $secret = (& $venvPython -c "import secrets; print(secrets.token_urlsafe(50))").Trim()
    @"
SECRET_KEY=$secret
ALLOWED_HOSTS=localhost,127.0.0.1
DB_NAME=ippbd
DB_USER=root
DB_PASSWORD=$mysqlPasswordPlain
DB_HOST=127.0.0.1
DB_PORT=3306
EMAIL_HOST_USER=
EMAIL_HOST_PASSWORD=
CSRF_TRUSTED_ORIGINS=
TRUST_PROXY_HEADERS=0
"@ | Set-Content -Path $envFile -Encoding UTF8
    Write-Host "  OK: .env generado (no se versiona)."
} else {
    Write-Host "  OK: .env ya existe; no se modifica."
}

# Con DEBUG=False, WhiteNoise sirve desde STATIC_ROOT: hay que generarlo siempre.
Write-Host "  Generando archivos estaticos..."
& $venvPython manage.py collectstatic --noinput 2>&1 | Out-Host
if ($LASTEXITCODE -ne 0) {
    Write-Host "  ERROR en collectstatic." -ForegroundColor Red
    exit 1
}
Write-Host "  OK: estaticos generados."

# La contrasena ya no se necesita: se elimina del entorno y de la memoria del script.
Remove-Item Env:\MYSQL_PWD -ErrorAction SilentlyContinue
$mysqlPasswordPlain = $null
[GC]::Collect()

# ------- 5. MIGRACIONES -------
Write-Host "[5/7] Ejecutando migraciones..."
& $venvPython manage.py migrate 2>&1 | Out-Host
if ($LASTEXITCODE -ne 0) {
    Write-Host "  ERROR en migraciones." -ForegroundColor Red
    exit 1
}
Write-Host "  OK: Migraciones aplicadas."

# ------- 6. CARGAR DATOS INICIALES -------
Write-Host "[6/7] Cargando datos iniciales..."
$dataFile = Join-Path $ProjectDir "datos_iniciales.json"
if (Test-Path $dataFile) {
    & $venvPython manage.py loaddata "$dataFile" 2>&1 | Out-Host
    Write-Host "  OK: Datos cargados (ignorar errores de ContentType/Permission)."
} else {
    Write-Host "  AVISO: No se encontro datos_iniciales.json. Los datos se migraran manualmente." -ForegroundColor Yellow
}

# ------- 6.5. CREAR SUPERUSUARIO -------
Write-Host ""
$crearSuper = Read-Host "  ¿Desea crear un superusuario para el panel admin? (s/n)"
if ($crearSuper -eq "s" -or $crearSuper -eq "S") {
    $adminUser = Read-Host "  Usuario admin (dejar vacio para 'admin')"
    if (-not $adminUser) { $adminUser = "admin" }
    $adminEmail = Read-Host "  Email del admin"
    Write-Host "  Ingrese la contrasena del superusuario:"
    & $venvPython manage.py createsuperuser --username $adminUser --email $adminEmail --noinput
    Write-Host "  AVISO: Asigne la contrasena manualmente con:" -ForegroundColor Yellow
    Write-Host "    $venvPython manage.py changepassword $adminUser" -ForegroundColor Yellow
}

# ------- 7. ACCESO DIRECTO + FIREWALL -------
Write-Host "[7/7] Creando acceso directo y configurando firewall..."
$desktop = [Environment]::GetFolderPath("Desktop")
$batContent = @"
@echo off
title SISTEMA IPP - Historia Medica
cd /d "$ProjectDir"
echo.
echo === SISTEMA IPP ===
echo Iniciando servidor...
echo Accede en: http://localhost:8000
echo.
"$venvPython" manage.py runserver 127.0.0.1:8000
pause
"@
$batPath = "$desktop\Iniciar IPP.bat"
Set-Content -Path $batPath -Value $batContent -Encoding ASCII
Write-Host "  OK: Acceso directo en $batPath"

try {
    netsh advfirewall firewall add rule name="IPP Sistema (8000)" dir=in action=allow protocol=TCP localport=8000 2>&1 | Out-Null
    Write-Host "  OK: Puerto 8000 abierto en firewall."
} catch {
    Write-Host "  AVISO: No se pudo abrir puerto 8000 en firewall." -ForegroundColor Yellow
}

Write-Host ""
Write-Host "============================================" -ForegroundColor Green
Write-Host "  INSTALACION COMPLETADA EXITOSAMENTE" -ForegroundColor Green
Write-Host "============================================" -ForegroundColor Green
Write-Host ""
Write-Host "  Accede en: http://localhost:8000"
Write-Host "  Usuarios y pass: los mismos del sistema original"
Write-Host ""
Write-Host "  Para iniciar el sistema cada vez:"
Write-Host "    Dar doble clic en el acceso del escritorio:"
Write-Host "    'Iniciar IPP.bat'"
Write-Host ""
Write-Host "  LOG: $LogFile (sin credenciales; se desactivó Start-Transcript)"
Write-Host ""
pause
