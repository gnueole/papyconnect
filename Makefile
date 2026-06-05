# Variables
DOTNET = /home/eole/.dotnet/dotnet
CSPROJ = EoleN8NPlugin/EoleN8NPlugin/EoleN8NPlugin.csproj
WINDOWS_USER = $(shell cmd.exe /C "echo %USERNAME%" | tr -d '\r\n ')
PLUGINS_DIR = /mnt/c/Users/$(WINDOWS_USER)/AppData/Local/Logi/LogiPluginService/Plugins
TARGET_DIR = $(PLUGINS_DIR)/EoleN8N
DOWNLOADS_DIR = /mnt/c/Users/$(WINDOWS_USER)/Downloads

DOTNET_EXISTS = $(shell [ -f $(DOTNET) ] && echo yes || echo no)

.PHONY: all build deploy restart clean status prepare check-dotnet publish help

# Default target: build, deploy and restart service
all: build deploy restart

# Show available make targets
help:
	@echo ""
	@echo "  Eole n8n Plugin — Available commands"
	@echo "  ─────────────────────────────────────────────────────────"
	@echo "  make all        Build + deploy + restart (full cycle)"
	@echo "  make build      Compile the plugin DLL with .NET"
	@echo "  make deploy     Copy built files to Logi Options+ plugin folder"
	@echo "  make restart    Restart LogiPluginService AND LogiOptions+ UI"
	@echo "  make publish    Build + package as .lproj4 in Downloads folder"
	@echo "  make clean      Remove .NET build artifacts"
	@echo "  make status     Show current build configuration"
	@echo "  make prepare    Install .NET 8.0 SDK if missing"
	@echo "  make help       Show this help message"
	@echo "  ─────────────────────────────────────────────────────────"
	@echo "  Typical workflow:"
	@echo "    1. Edit plugin source in EoleN8NPlugin/"
	@echo "    2. Run: make all"
	@echo "    3. Wait a few seconds for Logi Options+ to reload"
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
		Start-Process -FilePath 'C:\Program Files\Logi\LogiPluginService\LogiPluginService.exe'; \
		Start-Sleep -Seconds 2; \
		Start-Process -FilePath 'C:\Program Files\LogiOptionsPlus\logioptionsplus.exe'"
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
