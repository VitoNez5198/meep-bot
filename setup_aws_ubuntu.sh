#!/usr/bin/env bash
# ==============================================================================
# Script de Instalación y Despliegue Automático para Meep Bot en AWS EC2 (Ubuntu)
# ==============================================================================
set -e

echo "🧙‍♂️ Iniciando configuración de Meep Bot en AWS EC2..."

# 1. Actualizar repositorios del sistema
echo "📦 Actualizando paquetes del sistema..."
sudo apt update -y && sudo apt upgrade -y

# 2. Configurar 2GB de Swap (Esencial para instancias t2.micro/t3.micro de 1GB RAM)
if [ ! -f /swapfile ]; then
    echo "💾 Creando archivo de intercambio Swap de 2GB..."
    sudo fallocate -l 2G /swapfile || sudo dd if=/dev/zero of=/swapfile bs=1M count=2048
    sudo chmod 600 /swapfile
    sudo mkswap /swapfile
    sudo swapon /swapfile
    echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
    echo "✓ Swap configurado exitosamente."
else
    echo "✓ Archivo Swap ya configurado."
fi

# 3. Instalar Python 3, venv, pip, git y FFmpeg
echo "🔧 Instalando Python 3, FFmpeg y herramientas requeridas..."
sudo apt install -y python3 python3-pip python3-venv ffmpeg git curl

# 4. Crear entorno virtual
PROJECT_DIR="$(pwd)"
echo "🐍 Creando entorno virtual en $PROJECT_DIR/venv..."
if [ ! -d "venv" ]; then
    python3 -m venv venv
fi

# 5. Instalar dependencias de Python
echo "📥 Instalando dependencias de Python desde requirements.txt..."
venv/bin/pip install --upgrade pip
venv/bin/pip install -r requirements.txt

# 6. Configurar archivo .env
if [ ! -f ".env" ]; then
    if [ -f ".env.example" ]; then
        cp .env.example .env
        echo ""
        echo "⚠️  Se ha creado el archivo .env desde .env.example."
        echo "   Por favor, edita el archivo .env con tu token:"
        echo "   nano .env"
        echo ""
    fi
fi

# 7. Crear servicio de Systemd para ejecución 24/7 en segundo plano
SERVICE_FILE="/etc/systemd/system/meep.service"
CURRENT_USER="$(whoami)"

echo "⚙️ Configurando servicio de arranque automático en $SERVICE_FILE..."
sudo tee $SERVICE_FILE > /dev/null <<EOF
[Unit]
Description=Meep Bot - Asistente de Discord (Musica & LoL)
After=network.target

[Service]
Type=simple
User=$CURRENT_USER
WorkingDirectory=$PROJECT_DIR
ExecStart=$PROJECT_DIR/venv/bin/python $PROJECT_DIR/main.py
Restart=always
RestartSec=5
StandardOutput=journal
StandardError=journal
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
EOF

# 8. Recargar y habilitar servicio
sudo systemctl daemon-reload
sudo systemctl enable meep.service

echo ""
echo "=========================================================================="
echo "✨ ¡INSTALACIÓN COMPLETADA CON ÉXITO!"
echo "=========================================================================="
echo ""
echo "Pasos para poner en marcha el bot:"
echo " 1. Edita tus credenciales en el archivo .env:"
echo "      nano .env"
echo "    (Pega tu DISCORD_TOKEN y guarda con Ctrl+O, Enter, Ctrl+X)"
echo ""
echo " 2. Inicia el bot con:"
echo "      sudo systemctl start meep"
echo ""
echo " 3. Comandos útiles para monitorear el bot:"
echo "    * Ver estado:         sudo systemctl status meep"
echo "    * Ver logs en vivo:   journalctl -u meep -f"
echo "    * Reiniciar bot:      sudo systemctl restart meep"
echo "    * Detener bot:        sudo systemctl stop meep"
echo "=========================================================================="
