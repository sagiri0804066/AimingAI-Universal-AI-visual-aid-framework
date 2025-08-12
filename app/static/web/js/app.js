import * as api from './requests.js';

class UIManager {
    constructor() {
        this.models = {}; 
        this.cacheDOMElements();
        this.isInferenceRunning = false;
        this.isListeningHotkey = false;
        this.currentHotkey = { keys: [], display: "" };
        this.debouncedSaveConfig = this.debounce(this.saveCurrentConfig, 500);
    }

    cacheDOMElements() {
        this.body = document.body;
        this.appContainer = document.querySelector('.app-container');
        this.modelSelect = document.getElementById('model-select');
        this.importModelInput = document.getElementById('import-model-input');
        this.manageModelsBtn = document.getElementById('manage-models-btn');
        this.hotkeyListener = document.getElementById('hotkey-listener');
        
        this.elements = {
            rangeWidth: { slider: document.getElementById('range-width-slider'), input: document.getElementById('range-width-input') },
            rangeHeight: { slider: document.getElementById('range-height-slider'), input: document.getElementById('range-height-input') },
            aimSpeed: { slider: document.getElementById('aim-speed-slider'), input: document.getElementById('aim-speed-input') },
            offsetX: { slider: document.getElementById('offset-x-slider'), input: document.getElementById('offset-x-input') },
            offsetY: { slider: document.getElementById('offset-y-slider'), input: document.getElementById('offset-y-input') },
        };
        
        this.toggles = {
            showScope: document.getElementById('showScopeToggle'),
            enableDraw: document.getElementById('enableDrawToggle'),
        };

        this.startBtn = document.getElementById('start-btn');
        this.stopBtn = document.getElementById('stop-btn');
        this.modal = document.getElementById('manage-models-modal');
        this.modalCloseBtn = document.getElementById('modal-close-btn');
        this.modelList = document.getElementById('model-list');
    }
    
    async init() {
        try {
            console.log("UI Manager Initializing...");
            await this.loadAndRenderModels();
            await this.loadAndApplyConfig();
            this.setDynamicRanges();
            this.initEventListeners();
            window.showNotification(2, "初始化成功！", 2000);
            console.log("UI Manager Initialized Successfully.");
        } catch (error) {
            window.showNotification(0, `初始化失败: ${error.message}<br>请确保后端服务已正确启动。`, 8000);
        }
    }

    async loadAndApplyConfig() {
        const config = await api.loadConfig();
        if (config.model && this.models[config.model]) {
            this.modelSelect.value = config.model;
        }
        if (config.hotkey) {
            this.hotkeyListener.value = config.hotkey;
            this.currentHotkey.display = config.hotkey;
        }
        for (const key in this.elements) {
            if (config[key] !== undefined) {
                this.elements[key].slider.value = config[key];
                this.elements[key].input.value = config[key];
            }
        }
        for (const key in this.toggles) {
            if (config[key] !== undefined && this.toggles[key]) {
                this.toggles[key].checked = config[key];
            }
        }
    }

    async loadAndRenderModels() {
        this.models = await api.fetchModels();
        this.renderModelOptions();
    }
    
    initEventListeners() {
        for (const key in this.elements) {
            this.setupTwoWayBinding(this.elements[key].slider, this.elements[key].input);
        }
        for (const key in this.toggles) {
            if (this.toggles[key]) {
                 this.toggles[key].addEventListener('change', () => this.debouncedSaveConfig());
            }
        }
        this.modelSelect.addEventListener('change', () => this.debouncedSaveConfig());
        this.hotkeyListener.addEventListener('click', this.startHotkeyListen.bind(this));
        document.addEventListener('click', (e) => {
            if (this.isListeningHotkey && e.target !== this.hotkeyListener) this.stopHotkeyListen();
        });
        this.startBtn.addEventListener('click', this.startInference.bind(this));
        this.stopBtn.addEventListener('click', this.stopInference.bind(this));
        this.importModelInput.addEventListener('change', this.handleModelImport.bind(this));
        this.manageModelsBtn.addEventListener('click', this.openModelManager.bind(this));
        this.modalCloseBtn.addEventListener('click', this.closeModelManager.bind(this));
        this.modal.addEventListener('click', (e) => {
            if (e.target === this.modal) this.closeModelManager();
        });
        this.modelList.addEventListener('click', this.handleModelDelete.bind(this));
    }

    setupTwoWayBinding(slider, input) {
        const onValueChange = () => this.debouncedSaveConfig();
        
        slider.addEventListener('input', () => {
            input.value = slider.value;
            onValueChange();
        });
        
        input.addEventListener('input', () => {
            let value = parseInt(input.value, 10);
            const min = parseInt(input.min, 10);
            const max = parseInt(input.max, 10);
            if (!isNaN(value)) {
                slider.value = Math.max(min, Math.min(max, value));
            }
        });
        
        input.addEventListener('change', () => {
            let value = parseInt(input.value, 10);
            if (isNaN(value) || input.value === '') {
                input.value = slider.value;
            } else {
                onValueChange();
            }
        });
    }

    async handleModelImport(e) {
        const file = e.target.files[0];
        if (!file) return;

        const formData = new FormData();
        formData.append('model', file);

        try {
            window.showNotification(1, `正在上传模型 "${file.name}"...`, 2000);
            await api.uploadModel(formData);
            window.showNotification(2, "模型上传成功！");
            await this.loadAndRenderModels();
        } catch (error) {
            window.showNotification(0, `模型上传失败: ${error.message}`, 5000);
        } finally {
            e.target.value = '';
        }
    }

    async handleModelDelete(e) {
        const deleteBtn = e.target.closest('.delete-model-btn');
        if (!deleteBtn) return;

        const modelKey = deleteBtn.dataset.modelKey;
        const modelName = this.models[modelKey]?.name || modelKey;
        
        const confirmed = await window.showConfirmation(`您确定要永久删除模型 <strong>"${modelName}"</strong> 吗？此操作无法撤销。`);
        
        if (confirmed) {
            try {
                await api.deleteModel(modelKey);
                window.showNotification(2, "模型已删除。");
                await this.loadAndRenderModels();
                this.renderModelList();
            } catch (error) {
                window.showNotification(0, `删除失败: ${error.message}`);
            }
        }
    }

    async startInference() {
        if (this.isInferenceRunning) return;
        try {
            await api.startInference(this.getCurrentSettings());
            this.isInferenceRunning = true;
            this.updateUIForStateChange();
            console.log("--- 推理开始 ---");
        } catch(error) {
            window.showNotification(0, `启动推理失败: ${error.message}`);
        }
    }
    
    async stopInference() {
        if (!this.isInferenceRunning) return;
        try {
            await api.stopInference();
            this.isInferenceRunning = false;
            this.updateUIForStateChange();
            console.log("--- 推理结束 ---");
        } catch(error) {
            window.showNotification(0, `停止推理失败: ${error.message}`);
        }
    }

    async saveCurrentConfig() {
        try {
            const config = this.getCurrentSettings();
            await api.saveConfig(config);
            console.log("Config saved successfully.");
        } catch (error) {
            console.error("Failed to save config:", error);
            window.showNotification(0, "自动保存配置失败！");
        }
    }

    setDynamicRanges() {
        const screenWidth = window.screen.width;
        const screenHeight = window.screen.height;
        this.elements.rangeWidth.slider.max = screenWidth;
        this.elements.rangeWidth.input.max = screenWidth;
        this.elements.rangeHeight.slider.max = screenHeight;
        this.elements.rangeHeight.input.max = screenHeight;
    }

    startHotkeyListen(e) {
        e.stopPropagation();
        if (this.isListeningHotkey) return;
        this.isListeningHotkey = true;
        this.hotkeyListener.value = "请按下组合键...";
        this.hotkeyListener.classList.add('is-listening');
        this.currentHotkey.keys = [];
        this.currentHotkey.display = "";
        document.addEventListener('keydown', this.handleKeydown.bind(this), { capture: true });
    }

    stopHotkeyListen() {
        if (!this.isListeningHotkey) return;
        this.isListeningHotkey = false;
        this.hotkeyListener.value = this.currentHotkey.display || "";
        if (this.hotkeyListener.value === "") {
            this.hotkeyListener.placeholder = "点击以设置热键";
        }
        this.hotkeyListener.classList.remove('is-listening');
        document.removeEventListener('keydown', this.handleKeydown.bind(this), { capture: true });
        this.debouncedSaveConfig();
    }

    handleKeydown(e) {
        e.preventDefault();
        e.stopPropagation();
        const keys = new Set();
        if (e.ctrlKey) keys.add('Ctrl');
        if (e.altKey) keys.add('Alt');
        if (e.shiftKey) keys.add('Shift');
        if (e.metaKey) keys.add('Meta');
        const mainKey = e.key.toUpperCase();
        if (!['CONTROL', 'ALT', 'SHIFT', 'META'].includes(mainKey) && mainKey.trim() !== '') {
            keys.add(mainKey.replace('ARROW', ''));
        }
        if (keys.size > 0) {
            this.currentHotkey.keys = Array.from(keys);
            this.currentHotkey.display = this.currentHotkey.keys.join(' + ');
            this.hotkeyListener.value = this.currentHotkey.display;
        }
        if (!['Control', 'Alt', 'Shift', 'Meta'].includes(e.key)) {
            this.stopHotkeyListen();
        }
    }
    
    renderModelOptions() {
        const selectedValue = this.modelSelect.value;
        this.modelSelect.innerHTML = '';
        Object.keys(this.models).forEach(key => {
            const option = document.createElement('option');
            option.value = key;
            option.textContent = this.models[key].name;
            this.modelSelect.appendChild(option);
        });
        if (this.models[selectedValue]) {
            this.modelSelect.value = selectedValue;
        }
    }

    renderModelList() {
        this.modelList.innerHTML = '';
        if (Object.keys(this.models).length === 0) {
            this.modelList.innerHTML = '<li>没有可用的模型。</li>';
            return;
        }
        Object.keys(this.models).forEach(key => {
            const model = this.models[key];
            const li = document.createElement('li');
            li.className = 'model-list-item';
            li.innerHTML = `
                <div class="model-info">
                    <div class="name">${model.name}</div>
                    <div class="size">${model.size}</div>
                </div>
                <button class="delete-model-btn" data-model-key="${key}" title="删除模型">&times;</button>
            `;
            this.modelList.appendChild(li);
        });
    }

    openModelManager() {
        this.renderModelList();
        this.modal.style.display = 'flex';
        this.body.classList.add('modal-open');
    }

    closeModelManager() {
        this.modal.style.display = 'none';
        this.body.classList.remove('modal-open');
    }

getCurrentSettings() {
    const settings = {
        model: this.modelSelect.value,

        hotkey: this.hotkeyListener.value,
    };

    for (const key in this.elements) {
        if (this.elements[key] && this.elements[key].input) {
            settings[key] = this.elements[key].input.value;
        }
    }

    for (const key in this.toggles) {
        const toggleElement = this.toggles[key];
        if (toggleElement) {
            settings[key] = toggleElement.checked;
        } else {
            settings[key] = false;
        }
    }
    console.log("正在发送到后端的设置:", settings);
    
    return settings;
}

    updateUIForStateChange() {
        if (this.isInferenceRunning) {
            this.startBtn.style.display = 'none';
            this.stopBtn.style.display = 'block';
            this.appContainer.classList.add('is-inferencing');
        } else {
            this.startBtn.style.display = 'block';
            this.stopBtn.style.display = 'none';
            this.appContainer.classList.remove('is-inferencing');
        }
    }

    debounce(func, delay) {
        let timeout;
        return (...args) => {
            clearTimeout(timeout);
            timeout = setTimeout(() => func.apply(this, args), delay);
        };
    }
}

document.addEventListener('DOMContentLoaded', () => {
    const uiManager = new UIManager();
    uiManager.init();
});