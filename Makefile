# Variables
DOTNET = /home/eole/.dotnet/dotnet
SLN = LifxPlugin/LifxPlugin.sln
WINDOWS_USER = $(shell powershell.exe -Command "Write-Host -NoNewline \$$env:USERNAME" | tr -d '\r')
PLUGINS_DIR = /mnt/c/Users/$(WINDOWS_USER)/AppData/Local/Logi/LogiPluginService/Plugins
TARGET_DIR = $(PLUGINS_DIR)/Lifx
DOWNLOADS_DIR = /mnt/c/Users/$(WINDOWS_USER)/Downloads
VERSION = $(shell grep 'version:' LifxPlugin/LifxPlugin/package/metadata/LoupedeckPackage.yaml | awk '{print $$2}' | tr -d '\r')

TOKEN_FILE_1 = /mnt/c/Users/$(WINDOWS_USER)/Documents/LIFX_Token.txt
TOKEN_FILE_2 = /mnt/c/Users/$(WINDOWS_USER)/.lifx_token

DOTNET_EXISTS = $(shell [ -f $(DOTNET) ] && echo yes || echo no)
TOKEN_EXISTS = $(shell [ -f "$(TOKEN_FILE_1)" ] || [ -f "$(TOKEN_FILE_2)" ] && echo yes || echo no)

.PHONY: all build deploy restart clean status prepare check-dotnet publish setup-token

# Default target: build, deploy and restart service
all: build deploy restart

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
	@echo "=== LIFX Plugin Build Configuration ==="
	@echo "Dotnet Path:     $(DOTNET)"
	@echo "Dotnet Exists:   $(DOTNET_EXISTS)"
	@echo "Solution:        $(SLN)"
	@echo "LIFX Token Configured: $(TOKEN_EXISTS)"
	@echo "Windows User:    $(WINDOWS_USER)"
	@echo "Deploy Target:   $(TARGET_DIR)"
	@echo "Downloads Dir:   $(DOWNLOADS_DIR)"
	@echo "Version:         $(VERSION)"
	@echo "======================================="

# Build the plugin using .NET SDK
build: check-dotnet
	$(DOTNET) build $(SLN) \
		-p:PluginApiDir="/home/eole/projects/n8n-perso/LifxPlugin/build_links/" \
		-p:PluginDir="/home/eole/projects/n8n-perso/LifxPlugin/build_links/"

# Deploy built files to Windows AppData directory
deploy:
	@echo "Deploying to $(TARGET_DIR)..."
	rm -rf "$(TARGET_DIR)"
	mkdir -p "$(TARGET_DIR)"
	cp -r LifxPlugin/LifxPlugin/Debug/bin "$(TARGET_DIR)/"
	cp -r LifxPlugin/LifxPlugin/Debug/metadata "$(TARGET_DIR)/"
	@echo "Deploy completed successfully."

# Restart the LogiPluginService on Windows
restart:
	@echo "Restarting LogiPluginService on Windows..."
	powershell.exe -Command "Stop-Process -Name LogiPluginService -Force; Start-Process -FilePath 'C:\Program Files\Logi\LogiPluginService\LogiPluginService.exe'"
	@echo "LogiPluginService restarted."

# Clean build artifacts
clean: check-dotnet
	$(DOTNET) clean $(SLN)

# Prompt and configure the LIFX API Token if not already set
setup-token:
	@if [ "$(TOKEN_EXISTS)" = "no" ]; then \
		echo "LIFX API Token not found."; \
		echo "You can generate a token at: https://cloud.lifx.com/settings"; \
		printf "Please enter your LIFX Personal Access Token: "; \
		read token; \
		if [ -z "$$token" ]; then \
			echo "Error: Token cannot be empty."; \
			exit 1; \
		fi; \
		mkdir -p "$$(dirname "$(TOKEN_FILE_2)")"; \
		echo "$$token" > "$(TOKEN_FILE_2)"; \
		echo "Token successfully saved to $(TOKEN_FILE_2)"; \
	else \
		echo "LIFX Token is already configured."; \
	fi

# Package the plugin to the Windows Downloads folder
publish: build
	@echo "Packaging Lifx Plugin version $(VERSION)..."
	powershell.exe -Command "Compress-Archive -Path 'LifxPlugin\LifxPlugin\Debug\*' -DestinationPath 'lifx-$(VERSION).zip' -Force"
	mv lifx-$(VERSION).zip "$(DOWNLOADS_DIR)/lifx-$(VERSION).lproj4"
	@echo "Published to $(DOWNLOADS_DIR)/lifx-$(VERSION).lproj4"

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
