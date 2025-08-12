(function() {
    // --- SVG Icons ---
    const icons = {
        error: `<svg t="1746415575880" class="icon" viewBox="0 0 1024 1024" version="1.1" xmlns="http://www.w3.org/2000/svg" p-id="7519"><path d="M512 992C246.912 992 32 777.088 32 512 32 246.912 246.912 32 512 32c265.088 0 480 214.912 480 480 0 265.088-214.912 480-480 480z m0-64c229.76 0 416-186.24 416-416S741.76 96 512 96 96 282.24 96 512s186.24 416 416 416z" p-id="7520"></path><path d="M572.512 512l161.696 161.664-60.544 60.544L512 572.48l-161.664 161.696-60.544-60.544L451.52 512 288 348.512 348.512 288 512 451.488 675.488 288 736 348.512 572.512 512z" p-id="7521"></path></svg>`,
        warning: `<svg t="1746415599750" class="icon" viewBox="0 0 1024 1024" version="1.1" xmlns="http://www.w3.org/2000/svg" p-id="7720"><path d="M512 32C246.912 32 32 246.912 32 512c0 265.088 214.912 480 480 480 265.088 0 480-214.912 480-480 0-265.088-214.912-480-480-480z m0 896C282.24 928 96 741.76 96 512S282.24 96 512 96s416 186.24 416 416-186.24 416-416 416z" p-id="7721"></path><path d="M512 384a32 32 0 0 0-32 32v352a32 32 0 0 0 64 0V416a32 32 0 0 0-32-32z" p-id="7722"></path><path d="M512 272m-48 0a48 48 0 1 0 96 0 48 48 0 1 0-96 0Z" p-id="7723"></path></svg>`,
        success: `<svg t="1746415630102" class="icon" viewBox="0 0 1024 1024" version="1.1" xmlns="http://www.w3.org/2000/svg" p-id="8239"><path d="M512 992C246.912 992 32 777.088 32 512 32 246.912 246.912 32 512 32c265.088 0 480 214.912 480 480 0 265.088-214.912 480-480 480z m0-64c229.76 0 416-186.24 416-416S741.76 96 512 96 96 282.24 96 512s186.24 416 416 416z" p-id="8240"></path><path d="M741.216 344a32 32 0 0 1 46.816 43.616l-315.296 338.208a32 32 0 0 1-43.968 2.688l-193.344-162.368a32 32 0 1 1 41.152-48.992l170.08 142.816 294.56-316z" p-id="8241"></path></svg>`,
        close: `<svg t="1746415679917" class="icon" viewBox="0 0 1024 1024" version="1.1" xmlns="http://www.w3.org/2000/svg" p-id="8620"><path d="M548.992 503.744L885.44 167.328a31.968 31.968 0 1 0-45.248-45.248L503.744 458.496 167.328 122.08a31.968 31.968 0 1 0-45.248 45.248l336.416 336.416L122.08 840.16a31.968 31.968 0 1 0 45.248 45.248l336.416-336.416L840.16 885.44a31.968 31.968 0 1 0 45.248-45.248L548.992 503.744z" p-id="8621"></path></svg>`
    };

// --- Notification Toast Logic ---
let notificationContainer = null;

function getNotificationContainer() {
    if (!notificationContainer) {
        notificationContainer = document.createElement('div');
        notificationContainer.className = 'notification-container';
        document.body.appendChild(notificationContainer);
    }
    return notificationContainer;
}

/**
 * 显示一个提示框
 * @param {number} status - 状态码 (0: red, 1: yellow, 2: green)
 * @param {string} content - 提示内容 (HTML is allowed but use with caution)
 * @param {number} duration - 显示时长（毫秒），默认3000
 */
window.showNotification = function(status, content, duration = 3000) {
    const container = getNotificationContainer();
    const toast = document.createElement('div');
    toast.className = `notification-toast status-${status}`;

    let iconSvg = '';
    switch (status) {
        case 0: iconSvg = icons.error; break;
        case 1: iconSvg = icons.warning; break;
        case 2: iconSvg = icons.success; break;
        default: iconSvg = icons.warning;
    }

    try {
        // 使用正则表达式查找所有的 \uXXXX 序列并替换
        content = content.replace(/\\u([\dA-Fa-f]{4})/g, (match, hex) => {
            return String.fromCharCode(parseInt(hex, 16));
        });
    } catch (e) {
        console.error("Error unescaping notification content:", e);
        // 如果反转义失败，至少显示原始的转义后内容，而不是让整个函数崩溃
    }
    // --- 新增代码结束 ---

    toast.innerHTML = `
        <div class="notification-icon">${iconSvg}</div>
        <div class="notification-content">${content}</div>
        <button class="notification-close">${icons.close}</button>
    `;

    container.appendChild(toast);

    requestAnimationFrame(() => {
        toast.classList.add('show');
    });


    const closeButton = toast.querySelector('.notification-close');
    let timeoutId = null;

    const dismiss = () => {
        clearTimeout(timeoutId);
        toast.classList.remove('show');
        toast.addEventListener('transitionend', () => {
            if (toast.parentNode) {
                toast.parentNode.removeChild(toast);
            }
        }, { once: true });
    };

    closeButton.addEventListener('click', dismiss);

    timeoutId = setTimeout(dismiss, duration);
}


    /**
     * 显示一个二级确认弹窗
     * @param {string} content - 弹窗的主要内容 (HTML is allowed but use with caution)
     * @returns {Promise<boolean>} - 用户点击确认返回 true, 其他情况（取消、关闭、点击遮罩、重复打开）返回 false
     */
    window.showConfirmation = function(content) {
        return new Promise((resolve) => {
            const existingOverlay = document.querySelector('.confirmation-overlay');
            if (existingOverlay) {
                 console.warn("[showConfirmation] Modal already open. Resolving false.");
                 resolve(false);
                 return;
            }

            const overlay = document.createElement('div');
            overlay.className = 'confirmation-overlay';

            overlay.innerHTML = `
                <div class="confirmation-modal">
                    <div class="confirmation-header">
                        <div class="confirmation-header-icon">${icons.warning}</div>
                        <h3 class="confirmation-title">提示</h3>
                        <button class="confirmation-modal-close">${icons.close}</button>
                    </div>
                    <div class="confirmation-content">${content}</div>
                    <div class="confirmation-footer">
                        <button class="confirmation-button cancel">取消</button>
                        <button class="confirmation-button confirm">确认</button>
                    </div>
                </div>
            `;

            document.body.appendChild(overlay);
            console.log('[showConfirmation] Overlay appended.');

            const modal = overlay.querySelector('.confirmation-modal');
            const closeButton = overlay.querySelector('.confirmation-modal-close');
            const cancelButton = overlay.querySelector('.confirmation-button.cancel');
            const confirmButton = overlay.querySelector('.confirmation-button.confirm');

            let isClosing = false;

            const closeModal = (result) => {
                if (isClosing) {
                    console.log(`[closeModal] Already closing. Ignoring call with result: ${result}`);
                    return;
                }
                isClosing = true;
                console.log(`[closeModal] Closing initiated with result: ${result}`);

                overlay.classList.remove('visible');
                console.log('[closeModal] Removed "visible" class.');

                console.log(`[closeModal] Resolving promise with: ${result}`);
                resolve(result);

                const transitionDuration = 300;
                setTimeout(() => {
                    if (overlay.parentNode) {
                        overlay.parentNode.removeChild(overlay);
                        console.log('[closeModal] Overlay removed from DOM after timeout.');
                    } else {
                        console.log('[closeModal] Overlay already removed from DOM before timeout.');
                    }
                }, transitionDuration);
            };

            console.log('[showConfirmation] Adding event listeners.');
            closeButton.addEventListener('click', () => closeModal(false));
            cancelButton.addEventListener('click', () => closeModal(false));
            confirmButton.addEventListener('click', () => closeModal(true));
            overlay.addEventListener('click', (event) => {
                if (event.target === overlay) {
                    closeModal(false);
                }
            });
            requestAnimationFrame(() => {
                 if (!isClosing) {
                    overlay.classList.add('visible');
                    console.log('[showConfirmation] Added "visible" class in rAF.');
                 } else {
                    console.log('[showConfirmation] Modal was closed before rAF callback for adding "visible" class.');
                 }
             });
        });
    }
})();