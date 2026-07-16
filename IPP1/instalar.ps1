<#
.SYNOPSIS
    Instalador automático del Sistema IPP para Windows 10
.DESCRIPTION
    Instala PostgreSQL 16, Python 3.14, dependencias, migra la BD y
    deja el sistema listo para usar. Un solo clic.
.NOTES
    Ejecutar como Administrador. En PC sin internet, descargar los
    instaladores antes y colocarlos en la misma carpeta.
#>

#Requires -RunAsAdministrator

$ErrorActionPreference = "Stop"
$ProjectDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$LogFile = "$env:TEMP\ipp_instalacion.log"
Start-Transcript -Path $LogFile -Append | Out-Null

Write-Host "============================================" -ForegroundColor Cyan
Write-Host "  INSTALADOR AUTOMATICO SISTEMA IPP" -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan
Write-Host ""

# ------- 1. VERIFICAR / INSTALAR PYTHON -------
Write-Host "[1/7] Verificando Python..."
$python = $null
try { $python = (Get-Command python).Source } catch {}
if (-not $python) {
    Write-Host "  > Python no encontrado. Instalando..."
    $pyUrl = "https://www.python.org/ftp/python/3.14.0/python-3.14.0-amd64.exe"
    $pyInstaller = "$env:TEMP\python-3.14.0-amd64.exe"
    if (-not (Test-Path $pyInstaller)) {
        Invoke-WebRequest -Uri $pyUrl -OutFile $pyInstaller
    }
    Start-Process -Wait -FilePath $pyInstaller -ArgumentList "/quiet InstallAllUsers=1 PrependPath=1"
    # Refrescar PATH para la sesion actual
    $env:Path = [Environment]::GetEnvironmentVariable("Path","Machine") + ";" + [Environment]::GetEnvironmentVariable("Path","User")
    Write-Host "  OK: Python instalado."
} else {
    Write-Host "  OK: $python"
}

# ------- 2. VERIFICAR / INSTALAR POSTGRESQL -------
Write-Host "[2/7] Verificando PostgreSQL..."
$pgBin = "C:\Program Files\PostgreSQL\16\bin"
$pgInstalled = Test-Path "$pgBin\psql.exe"
$pgPassword = Read-Host -Prompt "  Contraseña para PostgreSQL (superuser)" -AsSecureString
$pgPasswordPlain = [Runtime.InteropServices.Marshal]::PtrToStringAuto([Runtime.InteropServices.Marshal]::SecureStringToBSTR($pgPassword))
if (-not $pgInstalled) {
    Write-Host "  > PostgreSQL no encontrado. Instalando..."
    $pgUrl = "https://get.enterprisedb.com/postgresql/postgresql-16.8-1-windows-x64.exe"
    $pgInstaller = "$env:TEMP\postgresql-16.8-1-windows-x64.exe"
    if (-not (Test-Path $pgInstaller)) {
        Invoke-WebRequest -Uri $pgUrl -OutFile $pgInstaller
    }
    Write-Host "  > Instalando PostgreSQL (varios minutos)..."
    Start-Process -Wait -FilePath $pgInstaller -ArgumentList @(
        "--unattendedmodeui", "minimal",
        "--mode", "unattended",
        "--superpassword", $pgPasswordPlain,
        "--servicename", "postgresql16",
        "--serverport", "5432"
    )
    Write-Host "  OK: PostgreSQL instalado."
    $env:Path += ";$pgBin"
} else {
    Write-Host "  OK: PostgreSQL 16 encontrado."
    $env:Path += ";$pgBin"
}

# ------- 3. INICIAR SERVICIO Y CREAR BD -------
Write-Host "[3/7] Asegurando que PostgreSQL este corriendo..."
$svc = Get-Service -Name "postgresql16*" -ErrorAction SilentlyContinue
if ($svc -and $svc.Status -ne "Running") {
    Start-Service $svc.Name
    Start-Sleep 2
}
Write-Host "  OK: Servicio PostgreSQL activo."

Write-Host "  Creando base de datos IPPBD..."
$env:PGPASSWORD = $pgPasswordPlain
$exists = & "$pgBin\psql.exe" -U postgres -lqt 2>&1 | Select-String "IPPBD"
if (-not $exists) {
    & "$pgBin\createdb.exe" -U postgres IPPBD 2>&1 | Out-Null
    Write-Host "  OK: Base de datos IPPBD creada."
} else {
    Write-Host "  OK: IPPBD ya existe."
}

# ------- 4. INSTALAR DEPENDENCIAS -------
Write-Host "[4/7] Instalando dependencias Python..."
Set-Location -Path $ProjectDir
pip install -r requirements.txt 2>&1 | Out-Host
Write-Host "  OK: Dependencias instaladas."

# ------- 5. MIGRACIONES -------
Write-Host "[5/7] Ejecutando migraciones..."
python manage.py migrate 2>&1 | Out-Host
if ($LASTEXITCODE -ne 0) {
    Write-Host "  ERROR en migraciones." -ForegroundColor Red
    Stop-Transcript
    exit 1
}
Write-Host "  OK: Migraciones aplicadas."

# ------- 6. CARGAR DATOS INICIALES -------
Write-Host "[6/7] Cargando datos iniciales..."
$dataFile = Join-Path $ProjectDir "datos_iniciales.json"
if (Test-Path $dataFile) {
    python manage.py loaddata "$dataFile" 2>&1 | Out-Host
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
    python manage.py createsuperuser --username $adminUser --email $adminEmail --noinput
    Write-Host "  AVISO: Asigne la contrasena manualmente con:" -ForegroundColor Yellow
    Write-Host "    python manage.py changepassword $adminUser" -ForegroundColor Yellow
}

# ------- 7. ACCESO DIRECTO + FIREWALL -------
Write-Host "[7/7] Creando acceso directo y configurando firewall..."
# .bat de inicio
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
python manage.py runserver 127.0.0.1:8000
pause
"@
$batPath = "$desktop\Iniciar IPP.bat"
Set-Content -Path $batPath -Value $batContent -Encoding ASCII
Write-Host "  OK: Acceso directo en $batPath"

# Firewall
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
Write-Host "  LOG: $LogFile"
Write-Host ""
Stop-Transcript
pause
