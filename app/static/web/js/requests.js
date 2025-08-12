/**
 * request.js
 * 
 * 负责与本地后端核心逻辑进行通信。
 * 使用相对路径，假设前端由同一个后端服务提供。
 */

const API_PREFIX = '/api'; // 所有API的统一前缀

/**
 * 封装的 fetch 辅助函数，处理通用逻辑和错误。
 * @param {string} endpoint - API的端点，例如 '/config'。
 * @param {object} options - fetch API 的选项对象。
 * @returns {Promise<any>} - 解析后的 JSON 响应。
 */
async function apiFetch(endpoint, options = {}) {
    try {
        const response = await fetch(API_PREFIX + endpoint, options);

        if (!response.ok) {
            // 尝试解析错误信息，如果后端有返回的话
            const errorData = await response.json().catch(() => null);
            const errorMessage = errorData?.error || `Request failed with status ${response.status}`;
            throw new Error(errorMessage);
        }
        
        // 如果响应是 204 No Content，则没有body，直接返回成功
        if (response.status === 204) {
            return { success: true };
        }

        return response.json();
    } catch (error) {
        console.error(`API call to ${endpoint} failed:`, error);
        // 将错误向上抛出，以便调用方可以处理
        throw error;
    }
}

// --- API 导出 ---

/** @description 加载程序配置。 */
export const loadConfig = () => apiFetch('/config');

/** @description 保存程序配置。 */
export const saveConfig = (config) => apiFetch('/config', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(config),
});

/** @description 获取模型列表。 */
export const fetchModels = () => apiFetch('/models');

/** @description 上传模型。 */
export const uploadModel = (formData) => apiFetch('/models', {
    method: 'POST',
    body: formData, // FormData 会自动设置正确的 Content-Type header
});

/** @description 删除一个模型。 */
export const deleteModel = (modelName) => apiFetch(`/models/${encodeURIComponent(modelName)}`, {
    method: 'DELETE',
});

/** @description 启动推理。 */
export const startInference = (config) => apiFetch('/inference/start', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(config),
});

/** @description 停止推理。 */
export const stopInference = () => apiFetch('/inference/stop', {
    method: 'POST',
});