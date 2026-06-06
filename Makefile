# Variables
DOTNET = /home/eole/.dotnet/dotnet
CSPROJ = EoleN8NPlugin/EoleN8NPlugin/EoleN8NPlugin.csproj
WINDOWS_USER = $(shell cmd.exe /C "echo %USERNAME%" | tr -d '\r\n ')
PLUGINS_DIR = /mnt/c/Users/$(WINDOWS_USER)/AppData/Local/Logi/LogiPluginService/Plugins
TARGET_DIR = $(PLUGINS_DIR)/EoleN8N
DOWNLOADS_DIR = /mnt/c/Users/$(WINDOWS_USER)/Downloads

# Server automation for papiconnect (Using root as requested)
SERVER_ROOT = root@gronas
REMOTE_DIR = /volume1/docker/papiconnect

DOTNET_EXISTS = $(shell [ -f $(DOTNET) ] && echo yes || echo no)

.PHONY: all build deploy restart clean status prepare check-dotnet publish help \
        papiconnect-sync papiconnect-up papiconnect-down \
        papiconnect-logs papiconnect-status papiconnect-recreate papiconnect-redeploy \
        papiconnect-n8n-push papiconnect-n8n-backup

# Default target: build, deploy and restart service
all: build deploy restart

# Show available make targets
# Show available make targets
help:
	@echo ""
	@echo "  Eole Lab — Available commands"
	@echo "  ─────────────────────────────────────────────────────────"
	@echo "  Plugin .NET / Logitech console :"
	@echo "    make all                   Build + deploy + restart (full cycle)"
	@echo "    make build                 Compile the plugin DLL with .NET"
	@echo "    make deploy                Copy built files to Logi Options+ folder"
	@echo "    make restart               Restart LogiPluginService AND LogiOptions+ UI"
	@echo "    make publish               Build + package as .lproj4 in Downloads"
	@echo "    make clean                 Remove .NET build artifacts"
	@echo "    make status                Show current build configuration"
	@echo "    make prepare               Install .NET 8.0 SDK if missing"
	@echo "  ─────────────────────────────────────────────────────────"
	@echo "  PapyConnect & n8n Stack (gronas) :"
	@echo "    make papiconnect-sync      Copy local app, compose and workflows to NAS via root SCP"
	@echo "    make papiconnect-up        Sync files and start containers (up -d)"
	@echo "    make papiconnect-down      Stop containers (down)"
	@echo "    make papiconnect-redeploy  Full redeploy (down + up)"
	@echo "    make papiconnect-recreate  Hot recreate containers with compose"
	@echo "    make papiconnect-logs      Stream remote docker compose logs"
	@echo "    make papiconnect-status    Show remote docker compose ps"
	@echo "    make papiconnect-n8n-push  Push local workflows to n8n container on gronas"
	@echo "    make papiconnect-n8n-backup Backup workflows from n8n container on gronas"
	@echo "  ─────────────────────────────────────────────────────────"
	@echo "  Urls :"
	@echo "    PapyConnect Radar :        http://gronas:8000"
	@echo "    n8n Cerveau       :        http://gronas:5678"
	@echo ""

# Check if dotnet exists before running commands
check-dotnet:
ifeq ($(DOTNET_EXISTS),no)
	@echo "Error: dotnet was not found at $(DOTNET)."
	@echo "To install .NET 8.0 SDK automatically, run: make prepare"
	@echo "Or download it manually from: https://dotnet.microsoft.com/download"
	@exit 1
endif


# Print current configuration status
status:
	@echo "=== Eole n8n Plugin Build Configuration ==="
	@echo "Dotnet Path:     $(DOTNET)"
	@echo "Dotnet Exists:   $(DOTNET_EXISTS)"
	@echo "Project:         $(CSPROJ)"
	@echo "Windows User:    $(WINDOWS_USER)"
	@echo "Deploy Target:   $(TARGET_DIR)"
	@echo "Downloads Dir:   $(DOWNLOADS_DIR)"
	@echo "=========================================="

# Build the plugin using .NET SDK
build: check-dotnet
	$(DOTNET) build $(CSPROJ) \
		-p:PluginApiDir="/mnt/c/Program Files/Logi/LogiPluginService/" \
		-p:PluginDir="/mnt/c/Users/$(WINDOWS_USER)/AppData/Local/Logi/LogiPluginService/Plugins/"

# Deploy built files to Windows AppData directory
deploy:
	@echo "Deploying to $(TARGET_DIR)..."
	rm -rf "$(TARGET_DIR)"
	mkdir -p "$(TARGET_DIR)"
	cp -r EoleN8NPlugin/EoleN8NPlugin/Debug/bin "$(TARGET_DIR)/"
	cp -r EoleN8NPlugin/EoleN8NPlugin/Debug/metadata "$(TARGET_DIR)/"
	@echo "Deploy completed successfully."

# Restart LogiPluginService (backend) AND LogiOptions+ (UI)
restart:
	@echo "Restarting Logi Options+ and LogiPluginService..."
	powershell.exe -Command "\
		Stop-Process -Name 'logioptionsplus' -Force -ErrorAction SilentlyContinue; \
		Stop-Process -Name 'logioptionsplus_agent' -Force -ErrorAction SilentlyContinue; \
		Stop-Process -Name 'LogiPluginService' -Force -ErrorAction SilentlyContinue; \
		Stop-Process -Name 'LogiPluginServiceExt' -Force -ErrorAction SilentlyContinue; \
		Start-Sleep -Seconds 2; \
		Start-Process -FilePath 'C:\Program Files\Logi\LogiPluginService\LogiPluginService.exe' -WorkingDirectory 'C:\Program Files\Logi\LogiPluginService'; \
		Start-Sleep -Seconds 2; \
		Start-Process -FilePath 'C:\Program Files\LogiOptionsPlus\logioptionsplus.exe' -WorkingDirectory 'C:\Program Files\LogiOptionsPlus'"
	@echo "Logi restarted. Wait ~5 seconds for the UI to appear."


# Clean build artifacts
clean: check-dotnet
	$(DOTNET) clean $(CSPROJ)

# Package the plugin as a .lproj4 archive to the Windows Downloads folder
publish: build
	@echo "Packaging Eole n8n Plugin..."
	powershell.exe -Command "Compress-Archive -Path 'EoleN8NPlugin\EoleN8NPlugin\Debug\*' -DestinationPath 'eolen8n-1.0.0.zip' -Force"
	mv eolen8n-1.0.0.zip "$(DOWNLOADS_DIR)/eolen8n-1.0.0.lproj4"
	@echo "Published to $(DOWNLOADS_DIR)/eolen8n-1.0.0.lproj4"

# Prepare the build environment by installing .NET 8.0 SDK automatically
prepare:
ifeq ($(DOTNET_EXISTS),yes)
	@echo ".NET SDK is already installed at $(DOTNET)."
else
	@echo "Downloading .NET installation script..."
	wget https://dot.net/v1/dotnet-install.sh -O dotnet-install.sh
	chmod +x dotnet-install.sh
	@echo "Installing .NET 8.0 SDK to /home/eole/.dotnet..."
	./dotnet-install.sh --channel 8.0 --install-dir /home/eole/.dotnet
	rm dotnet-install.sh
	@echo ".NET SDK installed successfully."
endif


# -------------------------------------------------
# PapyConnect — Remote deployment (gronas NAS via ROOT SSH)
# -------------------------------------------------
DOCKER = /usr/local/bin/docker

# Recréation forcée à chaud (sans coupure lourde)
papiconnect-recreate: papiconnect-sync
	@echo "[papiconnect] Recreating container cleanly..."
	@ssh $(SERVER_ROOT) "cd $(REMOTE_DIR) && $(DOCKER) compose up -d --force-recreate"

papiconnect-sync:
	@echo "[papiconnect] Creating target directory as root..."
	@ssh $(SERVER_ROOT) "mkdir -p $(REMOTE_DIR)"
	@echo "[papiconnect] Copying files via SCP (legacy -O mode for Synology)..."
	scp -O -r ./papiconnect/app $(SERVER_ROOT):$(REMOTE_DIR)/
	scp -O ./papiconnect/docker-compose.yml $(SERVER_ROOT):$(REMOTE_DIR)/
	scp -O -r ./n8n $(SERVER_ROOT):$(REMOTE_DIR)/
	@echo "[papiconnect] Sync complete."

# Démarrage
papiconnect-up: papiconnect-sync
	@echo "[papiconnect] Starting container on $(SERVER_ROOT)..."
	@ssh $(SERVER_ROOT) "cd $(REMOTE_DIR) && $(DOCKER) compose up -d"

# Arrêt
papiconnect-down:
	@echo "[papiconnect] Stopping container on $(SERVER_ROOT)..."
	@ssh $(SERVER_ROOT) "cd $(REMOTE_DIR) && $(DOCKER) compose down"

# Logs en direct
papiconnect-logs:
	@echo "[papiconnect] Streaming logs from $(SERVER_ROOT)..."
	@ssh $(SERVER_ROOT) "cd $(REMOTE_DIR) && $(DOCKER) compose logs -f"

# Statut des conteneurs
papiconnect-status:
	@echo "[papiconnect] Container status on $(SERVER_ROOT):"
	@ssh $(SERVER_ROOT) "cd $(REMOTE_DIR) && $(DOCKER) compose ps"

# Redéploiement complet (Clean restart)
papiconnect-redeploy: papiconnect-down papiconnect-up
	@echo "[papiconnect] Redeployment complete — http://gronas:8000"

# Outils de synchronisation de workflows n8n
papiconnect-n8n-push:
	@echo "[n8n] Pushing local workflows to gronas:5678..."
	python3 toolkit/sync_n8n.py --push-all

papiconnect-n8n-backup:
	@echo "[n8n] Backing up workflows from gronas:5678..."
	python3 toolkit/sync_n8n.py --backup-all