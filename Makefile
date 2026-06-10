-include .env
DEPLOY_MODE ?= remote

# If the first argument is "status", parse the remaining targets as command arguments
ifeq ($(firstword $(MAKECMDGOALS)),status)
  RUN_ARGS := $(wordlist 2,$(words $(MAKECMDGOALS)),$(MAKECMDGOALS))
  $(eval $(RUN_ARGS):;@:)
endif

GRONAS_IP ?= gronas
PAPYCONNECT_PORT ?= 8000
N8N_PORT ?= 5678

# Variables
DOTNET = /home/eole/.dotnet/dotnet
CSPROJ = PapyConnectPlugin/PapyConnectPlugin/PapyConnectPlugin.csproj
WINDOWS_USER = $(shell cmd.exe /C "echo %USERNAME%" | tr -d '\r\n ')
PLUGINS_DIR = /mnt/c/Users/$(WINDOWS_USER)/AppData/Local/Logi/LogiPluginService/Plugins
TARGET_DIR = $(PLUGINS_DIR)/PapyConnect
DOWNLOADS_DIR = /mnt/c/Users/$(WINDOWS_USER)/Downloads

# Server automation for papiconnect (Using root as requested)
SERVER_ROOT = root@$(GRONAS_IP)
REMOTE_DIR = /volume1/docker/papiconnect

DOTNET_EXISTS = $(shell [ -f $(DOTNET) ] && echo yes || echo no)

.PHONY: all build deploy restart clean status plugin-status prepare check-dotnet publish help \
        papiconnect-sync papiconnect-up papiconnect-down \
        papiconnect-logs papiconnect-status papiconnect-recreate papiconnect-redeploy \
        papiconnect-n8n-push papiconnect-n8n-backup check \
        local-build local-up local-down local-recreate local-logs local-status status-local

# Default target: build, deploy and restart service
all: build deploy restart

# Show available make targets
help:
	@echo ""
	@echo "  PapyConnect — Available commands"
	@echo "  ─────────────────────────────────────────────────────────"
	@echo "  Plugin .NET / Logitech console :"
	@echo "    make all                   Build + deploy + restart (full cycle)"
	@echo "    make build                 Compile the plugin DLL with .NET"
	@echo "    make deploy                Copy built files to Logi Options+ folder"
	@echo "    make restart               Restart LogiPluginService AND LogiOptions+ UI"
	@echo "    make publish               Build + package as .lproj4 in Downloads"
	@echo "    make clean                 Remove .NET build artifacts"
	@echo "    make plugin-status         Show current .NET build configuration"
	@echo "    make prepare               Install .NET 8.0 SDK if missing"
	@echo "  ─────────────────────────────────────────────────────────"
ifeq ($(DEPLOY_MODE),local)
	@echo "  PapyConnect & n8n Local Stack (localhost / WSL) :"
	@echo "    make status                Show scanned devices tree & available apps on localhost"
	@echo "    make papiconnect-up        Build local Docker image and start containers"
	@echo "    make papiconnect-down      Stop local containers"
	@echo "    make papiconnect-redeploy  Full local redeploy (down + up)"
	@echo "    make papiconnect-recreate  Force recreate local containers"
	@echo "    make papiconnect-logs      Stream local compose logs"
	@echo "    make papiconnect-status    Show local container status"
else
	@echo "  PapyConnect & n8n Stack (gronas) :"
	@echo "    make status                Show scanned devices tree & available apps (CLI debug)"
	@echo "    make papiconnect-sync      Copy local app, compose and workflows to NAS via root SCP"
	@echo "    make papiconnect-up        Sync files and start containers (up -d)"
	@echo "    make papiconnect-down      Stop containers (down)"
	@echo "    make papiconnect-redeploy  Full redeploy (down + up)"
	@echo "    make papiconnect-recreate  Hot recreate containers with compose"
	@echo "    make papiconnect-logs      Stream remote docker compose logs"
	@echo "    make papiconnect-status    Show remote docker compose ps"
	@echo "    make papiconnect-n8n-push  Push local workflows to n8n container on gronas"
	@echo "    make papiconnect-n8n-backup Backup workflows from n8n container on gronas"
endif
	@echo "  ─────────────────────────────────────────────────────────"
	@echo "  Urls :"
ifeq ($(DEPLOY_MODE),local)
	@echo "    PapyConnect Radar :        http://localhost:8000"
	@echo "    n8n Cerveau       :        http://localhost:5678"
else
	@echo "    PapyConnect Radar :        http://$(GRONAS_IP):8000"
	@echo "    n8n Cerveau       :        http://$(GRONAS_IP):$(N8N_PORT)"
endif
	@echo ""

# Check if dotnet exists before running commands
check-dotnet:
ifneq ($(DOTNET_EXISTS),yes)
	@echo "Error: dotnet was not found at $(DOTNET)."
	@echo "To install .NET 8.0 SDK automatically, run: make prepare"
	@echo "Or download it manually from: https://dotnet.microsoft.com/download"
	@exit 1
endif




# Print current configuration status
plugin-status:
	@echo "=== PapyConnect n8n Plugin Build Configuration ==="
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
	cp -r PapyConnectPlugin/PapyConnectPlugin/Debug/bin "$(TARGET_DIR)/"
	cp -r PapyConnectPlugin/PapyConnectPlugin/Debug/metadata "$(TARGET_DIR)/"
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
	@echo "Packaging PapyConnect Plugin..."
	powershell.exe -Command "Compress-Archive -Path 'PapyConnectPlugin\PapyConnectPlugin\Debug\*' -DestinationPath 'papyconnect-1.0.0.zip' -Force"
	mv papyconnect-1.0.0.zip "$(DOWNLOADS_DIR)/papyconnect-1.0.0.lproj4"
	@echo "Published to $(DOWNLOADS_DIR)/papyconnect-1.0.0.lproj4"

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


DOCKER = /usr/local/bin/docker

# -------------------------------------------------
# PapyConnect — Stack Deployment Actions (Dynamic)
# -------------------------------------------------

ifeq ($(DEPLOY_MODE),local)

# Local implementations (localhost / WSL)
papiconnect-up: local-build
	@echo "[papiconnect-local] Starting local containers..."
	docker compose -f papiconnect/docker-compose.yml up -d

papiconnect-down:
	@echo "[papiconnect-local] Stopping local containers..."
	docker compose -f papiconnect/docker-compose.yml down

papiconnect-recreate: local-build
	@echo "[papiconnect-local] Recreating local containers..."
	docker compose -f papiconnect/docker-compose.yml up -d --force-recreate

papiconnect-logs:
	@echo "[papiconnect-local] Streaming logs from local containers..."
	docker compose -f papiconnect/docker-compose.yml logs -f

papiconnect-status:
	@echo "[papiconnect-local] Local container status:"
	docker compose -f papiconnect/docker-compose.yml ps

papiconnect-redeploy: papiconnect-down papiconnect-up
	@echo "[papiconnect-local] Local redeployment complete — http://localhost:8000"

status:
	@python3 toolkit/print_status.py localhost $(PAPYCONNECT_PORT) $(RUN_ARGS) $(MAKEOVERRIDES)

else

# Remote/NAS implementations (gronas)
papiconnect-up: papiconnect-sync
	@echo "[papiconnect] Starting container on $(SERVER_ROOT)..."
	@ssh $(SERVER_ROOT) "cd $(REMOTE_DIR) && $(DOCKER) compose up -d"

papiconnect-down:
	@echo "[papiconnect] Stopping container on $(SERVER_ROOT)..."
	@ssh $(SERVER_ROOT) "cd $(REMOTE_DIR) && $(DOCKER) compose down"

papiconnect-recreate: papiconnect-sync
	@echo "[papiconnect] Recreating container cleanly..."
	@ssh $(SERVER_ROOT) "cd $(REMOTE_DIR) && $(DOCKER) compose up -d --force-recreate"

papiconnect-logs:
	@echo "[papiconnect] Streaming logs from $(SERVER_ROOT)..."
	@ssh $(SERVER_ROOT) "cd $(REMOTE_DIR) && $(DOCKER) compose logs -f"

papiconnect-status:
	@echo "[papiconnect] Container status on $(SERVER_ROOT):"
	@ssh $(SERVER_ROOT) "cd $(REMOTE_DIR) && $(DOCKER) compose ps"

papiconnect-redeploy: papiconnect-down papiconnect-up
	@echo "[papiconnect] Redeployment complete — http://$(GRONAS_IP):8000"

status:
	@python3 toolkit/print_status.py $(GRONAS_IP) $(PAPYCONNECT_PORT) $(RUN_ARGS) $(MAKEOVERRIDES)

endif


# Helper & Sync Utilities
local-build:
	@echo "[papiconnect-local] Building Docker image locally..."
	docker build -t papiconnect:latest -f papiconnect/Dockerfile papiconnect

papiconnect-build-image:
	@echo "[papiconnect] Building Docker image locally..."
	docker build -t papiconnect:latest -f papiconnect/Dockerfile papiconnect
	@echo "[papiconnect] Saving image to archive..."
	docker save papiconnect:latest | gzip > papiconnect.tar.gz

papiconnect-sync: papiconnect-build-image
	@echo "[papiconnect] Creating target directory as root..."
	@ssh $(SERVER_ROOT) "mkdir -p $(REMOTE_DIR)"
	@echo "[papiconnect] Copying Docker image and configuration files..."
	scp -O papiconnect.tar.gz $(SERVER_ROOT):$(REMOTE_DIR)/
	scp -O ./papiconnect/docker-compose.yml $(SERVER_ROOT):$(REMOTE_DIR)/
	scp -O -r ./n8n $(SERVER_ROOT):$(REMOTE_DIR)/
	@echo "[papiconnect] Loading Docker image on the NAS..."
	@ssh $(SERVER_ROOT) "$(DOCKER) load < $(REMOTE_DIR)/papiconnect.tar.gz && rm -f $(REMOTE_DIR)/papiconnect.tar.gz"
	@rm -f papiconnect.tar.gz
	@echo "[papiconnect] Sync and image load complete."

papiconnect-n8n-push:
	@echo "[n8n] Pushing local workflows to n8n container..."
	python3 toolkit/sync_n8n.py --push-all

papiconnect-n8n-backup:
	@echo "[n8n] Backing up workflows from n8n container..."
	python3 toolkit/sync_n8n.py --backup-all

check:
	@echo "=== Checking PapyConnect API (Direct) ==="
	curl -s http://$(GRONAS_IP):$(PAPYCONNECT_PORT)/api/actions
	@echo "\n\n=== Checking n8n API (via Webhook) ==="
	curl -s http://$(GRONAS_IP):$(N8N_PORT)/webhook/get-exposed-actions
	@echo ""