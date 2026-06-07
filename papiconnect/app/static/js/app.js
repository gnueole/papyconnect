// ─────────────────────────────────────────────────────────────────────────
// Alpine.js Application Controller (Coded by Éole & Antigravity)
// ─────────────────────────────────────────────────────────────────────────
function app() {
  return {
    devices:  [],
    actions:  [],
    loading:  true,
    scanning: false,
    toast:    '',
    selectedDeviceForDetails: null,
    deviceDetailsModal: {
      open: false
    },
    aboutModal: {
      open: false
    },
    vendorsModal: {
      open: false,
      list: [],
      selected: null,
      longest: null
    },
    manualAddModal: {
      open: false,
      form: {
        name: '',
        ip: '',
        type: 'tv',
        vendor: 'Sony'
      }
    },
    factoryResetModal: {
      open: false
    },
    _toastTimer: null,

    filterKnownVendors: true,

    wizard: {
      step: 1,
      service: '',
      device: null,
      title: ''
    },

    get onlineCount() {
      return this.devices.filter(d => d.status === 'online').length;
    },

    get filteredDevices() {
      if (this.filterKnownVendors) {
        return this.devices.filter(d => d.vendor !== 'Generic');
      }
      return this.devices;
    },

    async init() { await this.load(); },

    async load() {
      this.loading = true;
      try {
        const r = await fetch('/api/devices');
        if (!r.ok) throw new Error();
        this.devices = await r.json();
        await this.loadActions();
      } catch {
        this.notify('Failed to load registry data.');
      } finally {
        this.loading = false;
      }
    },

    async loadActions() {
      try {
        const r = await fetch('/api/actions');
        if (!r.ok) throw new Error();
        this.actions = await r.json();
      } catch {
        this.notify('Failed to load configured actions.');
      }
    },

    openDeviceDetails(d) {
      this.selectedDeviceForDetails = d;
      this.deviceDetailsModal.open = true;
    },

    formatActionName(name) {
      const map = {
        'launch_spotify': 'Spotify Connect',
        'launch_netflix': 'Netflix',
        'launch_youtube': 'YouTube',
        'power_on': 'Power On',
        'power_off': 'Power Off'
      };
      if (map[name]) return map[name];
      const clean = name.replace('launch_', '').replace('_', ' ');
      return clean.charAt(0).toUpperCase() + clean.slice(1);
    },

    async executeDeviceAction(ip, actionName) {
      try {
        this.notify(`Executing ${this.formatActionName(actionName)} on ${ip}...`);
        const r = await fetch(`/api/devices/${ip}/action/${actionName}`, {
          method: 'POST'
        });
        if (!r.ok) throw new Error();
        this.notify(`Action ${this.formatActionName(actionName)} executed successfully!`);
      } catch {
        this.notify(`Failed to execute action.`);
      }
    },

    async scan() {
      if (this.scanning) return;
      this.scanning = true;
      this.notify('Network scan started (mDNS + ping, ~7s)…');
      try {
        await fetch('/api/scan', { method: 'POST' });
        await new Promise(r => setTimeout(r, 8000));
        await this.load();
        this.notify(`Scan completed — ${this.devices.length} device(s) found in registry.`);
      } catch {
        this.notify('Failed to scan network.');
      } finally {
        this.scanning = false;
      }
    },

    async remove(ip) {
      try {
        const r = await fetch(`/api/devices/${ip}`, { method: 'DELETE' });
        if (!r.ok) throw new Error();
        this.devices = this.devices.filter(d => d.ip !== ip);
        this.notify(`Device ${ip} removed.`);
      } catch {
        this.notify('Failed to remove device.');
      }
    },

    notify(msg) {
      this.toast = msg;
      clearTimeout(this._toastTimer);
      this._toastTimer = setTimeout(() => this.toast = '', 6000);
    },

    async openVendors() {
      this.vendorsModal.open = true;
      try {
        const r = await fetch('/api/vendors');
        if (!r.ok) throw new Error();
        this.vendorsModal.list = await r.json();
        if (this.vendorsModal.list.length > 0) {
          if (!this.vendorsModal.selected) {
            this.vendorsModal.selected = this.vendorsModal.list[0];
          }
          // Find the vendor with the longest description and api calls representation
          let longest = this.vendorsModal.list[0];
          let maxLen = 0;
          for (const v of this.vendorsModal.list) {
            const len = (v.description || '').length + JSON.stringify(v.api_calls || {}).length;
            if (len > maxLen) {
              maxLen = len;
              longest = v;
            }
          }
          this.vendorsModal.longest = longest;
        }
      } catch {
        this.notify('Failed to load supported vendors API specs.');
      }
    },

    async openManualAdd() {
      this.manualAddModal.form.name = '';
      this.manualAddModal.form.type = 'tv';
      this.manualAddModal.form.vendor = 'Sony';
      this.manualAddModal.open = true;
      try {
        const r = await fetch('/api/network-prefix');
        if (r.ok) {
          const data = await r.json();
          this.manualAddModal.form.ip = data.prefix;
        } else {
          this.manualAddModal.form.ip = '192.168.1.';
        }
      } catch {
        this.manualAddModal.form.ip = '192.168.1.';
      }
    },

    async submitManualAdd() {
      try {
        const res = await fetch('/api/devices', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            name: this.manualAddModal.form.name,
            ip: this.manualAddModal.form.ip,
            type: this.manualAddModal.form.type,
            vendor: this.manualAddModal.form.vendor,
            variables: {}
          })
        });
        if (!res.ok) {
          const err = await res.json();
          throw new Error(err.detail || 'Failed to add device.');
        }
        this.manualAddModal.open = false;
        this.notify('Device manually added successfully.');
        await this.load();
      } catch (e) {
        this.notify(e.message || 'Failed to add device.');
      }
    },

    openAbout() {
      this.aboutModal.open = true;
      setTimeout(() => {
        startFireworks();
      }, 50);
    },

    closeAbout() {
      this.aboutModal.open = false;
      stopFireworks();
    },

    confirmFactoryReset() {
      this.factoryResetModal.open = true;
    },

    async executeFactoryReset() {
      this.factoryResetModal.open = false;
      this.loading = true;
      try {
        const r = await fetch('/api/factory-reset', { method: 'POST' });
        if (!r.ok) throw new Error();
        localStorage.clear();
        sessionStorage.clear();
        this.notify('Factory reset successful. Reloading...');
        setTimeout(() => {
          window.location.reload();
        }, 1500);
      } catch {
        this.notify('Failed to perform factory reset.');
        this.loading = false;
      }
    },

    ago(iso) {
      if (!iso) return '';
      try {
        const diff = Math.floor((Date.now() - new Date(iso).getTime()) / 1000);
        if (diff < 60)  return 'just now';
        if (diff < 3600) return `${Math.floor(diff/60)}m ago`;
        return new Date(iso).toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' });
      } catch { return ''; }
    },

    // Wizard Logic
    selectService(service) {
      this.wizard.service = service;
      this.wizard.step = 2;
    },

    selectDevice(device) {
      this.wizard.device = device;
      let room = 'Living Room';
      if (device.name.toLowerCase().includes('salon')) room = 'Living Room';
      else if (device.name.toLowerCase().includes('louistib')) room = 'Louistib';
      else if (device.name.toLowerCase().includes('chambre')) room = 'Bedroom';
      let baseTitle = `${this.serviceLabel(this.wizard.service)} (${room})`;
      this.wizard.title = this.getUniqueTitle(baseTitle);
      this.wizard.step = 3;
    },

    getUniqueTitle(baseTitle) {
      let finalTitle = baseTitle;
      let counter = 2;
      while (this.actions.some(act => act.title.toLowerCase() === finalTitle.toLowerCase())) {
        finalTitle = `${baseTitle} ${counter}`;
        counter++;
      }
      return finalTitle;
    },

    serviceLabel(service) {
      if (SERVICES_METADATA[service]) return SERVICES_METADATA[service].label;
      return service.split('_').map(w => w.charAt(0).toUpperCase() + w.slice(1)).join(' ');
    },

    getPopularServices() {
      const counts = {};
      
      this.devices.forEach(d => {
        // Count state actions if supported in catalog
        if (d.catalog && d.catalog.actions) {
          if (d.catalog.actions.power_on) {
            counts['power_on'] = (counts['power_on'] || 0) + 1;
          }
          if (d.catalog.actions.power_off) {
            counts['power_off'] = (counts['power_off'] || 0) + 1;
          }
        }
        
        // Count applications
        if (d.available_apps && Array.isArray(d.available_apps)) {
          d.available_apps.forEach(app => {
            if (app) {
              const normalized = app.toLowerCase().replace(/[\s-]/g, '_');
              counts[normalized] = (counts[normalized] || 0) + 1;
            }
          });
        }
      });

      // Convert to list of service objects
      const services = Object.keys(counts).map(key => {
        return {
          key: key,
          label: this.serviceLabel(key),
          count: counts[key]
        };
      });

      // Sort by count descending (popularity), then alphabetically
      return services.sort((a, b) => {
        if (b.count !== a.count) {
          return b.count - a.count;
        }
        return a.label.localeCompare(b.label);
      });
    },

    filteredWizardDevices() {
      const service = this.wizard.service;
      if (!service) return [];

      if (service === 'power_on') {
        return this.devices.filter(d => d.catalog && d.catalog.actions && d.catalog.actions.power_on);
      } else if (service === 'power_off') {
        return this.devices.filter(d => d.catalog && d.catalog.actions && d.catalog.actions.power_off);
      } else {
        // Filter devices that contain this application
        return this.devices.filter(d => {
          if (!d.available_apps || !Array.isArray(d.available_apps)) return false;
          return d.available_apps.some(app => {
            if (!app) return false;
            const norm = app.toLowerCase().replace(/[\s-]/g, '_');
            return norm === service;
          });
        });
      }
    },

    resetWizard() {
      this.wizard = {
        step: 1,
        service: '',
        device: null,
        title: ''
      };
    },

    async submitWizard() {
      if (!this.wizard.device || !this.wizard.title) return;
      const targetApp = this.wizard.service === 'spotify'
        ? 'launch_spotify'
        : (this.wizard.service.startsWith('power_')
           ? this.wizard.service
           : 'launch_' + this.wizard.service);

      const service = this.wizard.service;
      const deviceName = this.wizard.device.name;
      const slug = deviceName.toLowerCase()
        .replace(/[^a-z0-9]/g, '_')
        .replace(/_+/g, '_')
        .replace(/^_+|_+$/g, '');
      const actionId = `${service}_${slug}`;

      const payload = {
        id: actionId,
        device_ip: this.wizard.device.ip,
        target_app: targetApp,
        title: this.wizard.title,
        icon: this.wizard.service
      };

      try {
        this.notify("Adding action to dashboard...");
        const r = await fetch('/api/actions', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload)
        });
        if (!r.ok) throw new Error();
        await this.loadActions();
        this.resetWizard();
        this.notify("Action added successfully!");
      } catch {
        this.notify("Failed to add action.");
      }
    },

    async removeAction(id) {
      try {
        const r = await fetch(`/api/actions/${id}`, { method: 'DELETE' });
        if (!r.ok) throw new Error();
        this.actions = this.actions.filter(a => a.id !== id);
        this.notify("Action removed.");
      } catch {
        this.notify("Failed to remove action.");
      }
    },

    async triggerAction(action, event) {
      const card = event.currentTarget;
      if (!card) return;

      const glowColor = SERVICES_METADATA[action.icon]?.glowColor || 'rgba(233, 166, 35, 0.45)';

      // Apply glow color as CSS variables for the keyframes
      card.style.setProperty('--glow-color', glowColor);

      // Spawn ripple
      const container = card.querySelector('.ripple-container');
      if (container) {
        const rect = card.getBoundingClientRect();
        const ripple = document.createElement('div');
        ripple.className = 'ripple-element';
        
        // Set dynamic background color
        ripple.style.background = glowColor;

        const size = Math.max(rect.width, rect.height);
        ripple.style.width = ripple.style.height = `${size}px`;
        
        let x, y;
        if (event.clientX === 0 && event.clientY === 0) {
          x = rect.width / 2 - size / 2;
          y = rect.height / 2 - size / 2;
        } else {
          x = event.clientX - rect.left - size / 2;
          y = event.clientY - rect.top - size / 2;
        }
        ripple.style.left = `${x}px`;
        ripple.style.top = `${y}px`;

        container.appendChild(ripple);
        
        // Remove ripple element after animation finishes
        setTimeout(() => {
          ripple.remove();
        }, 600);
      }

      // Trigger glow animation
      card.classList.remove('glow-pulse');
      // Force layout reflow to restart animation if clicked repeatedly
      void card.offsetWidth;
      card.classList.add('glow-pulse');
      setTimeout(() => {
        card.classList.remove('glow-pulse');
      }, 600);

      // Executing logic
      try {
        this.notify(`Triggering ${action.title}...`);
        
        // 1. Toggle action state in database
        const toggleRes = await fetch(`/api/actions/execute/${action.id}`, { method: 'POST' });
        if (!toggleRes.ok) throw new Error("Failed to execute action toggle.");
        const contract = await toggleRes.json();

        // 2. Dispatch command to physical device
        const runRes = await fetch(`/api/devices/${contract.ip}/action/${contract.action}`, { method: 'POST' });
        if (!runRes.ok) throw new Error("Failed to dispatch device command.");

        this.notify(`Action ${action.title} completed successfully.`);
      } catch (err) {
        this.notify(`Failed to run action: ${err.message || err}`);
      } finally {
        // Always sync the list to show updated active states
        await this.loadActions();
      }
    },

    activeCardClass(type) {
      const cfg = SERVICES_METADATA[type] || SERVICES_METADATA.unknown;
      return cfg.activeClass + ' scale-[1.01]';
    },

    icon(type) {
      const cfg = SERVICES_METADATA[type] || SERVICES_METADATA.unknown;
      return cfg.icon;
    },

    iconBg(type) {
      const cfg = SERVICES_METADATA[type] || SERVICES_METADATA.unknown;
      return cfg.bgClass;
    }
  };
}
