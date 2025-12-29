/**
 * Aegis 前端主 JavaScript 文件
 */

// 检查登录状态
function checkAuth() {
    const token = localStorage.getItem('access_token');
    const currentPath = window.location.pathname;

    // 登录页面不需要检查
    if (currentPath === '/admin/login') {
        if (token) {
            // 已登录，跳转到首页
            window.location.href = '/admin/';
        }
        return;
    }

    // 其他管理页面需要登录
    if (currentPath.startsWith('/admin') && !token) {
        window.location.href = '/admin/login';
    }
}

// 页面加载时检查登录状态
document.addEventListener('DOMContentLoaded', checkAuth);

// 带认证的 fetch 请求
async function fetchWithAuth(url, options = {}) {
    const token = localStorage.getItem('access_token');

    const headers = {
        'Content-Type': 'application/json',
        ...options.headers,
    };

    if (token) {
        headers['Authorization'] = `Bearer ${token}`;
    }

    const response = await fetch(url, {
        ...options,
        headers,
    });

    // 如果 401，尝试刷新 token
    if (response.status === 401) {
        const refreshed = await refreshToken();
        if (refreshed) {
            // 重试请求
            headers['Authorization'] = `Bearer ${localStorage.getItem('access_token')}`;
            return fetch(url, { ...options, headers });
        } else {
            // 刷新失败，跳转到登录页
            logout();
        }
    }

    return response;
}

// 刷新 token
async function refreshToken() {
    const refreshToken = localStorage.getItem('refresh_token');
    if (!refreshToken) return false;

    try {
        const response = await fetch('/api/v1/auth/refresh', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ refresh_token: refreshToken }),
        });

        if (response.ok) {
            const data = await response.json();
            localStorage.setItem('access_token', data.access_token);
            if (data.refresh_token) {
                localStorage.setItem('refresh_token', data.refresh_token);
            }
            return true;
        }
    } catch (error) {
        console.error('刷新 token 失败:', error);
    }

    return false;
}

// 退出登录
function logout() {
    localStorage.removeItem('access_token');
    localStorage.removeItem('refresh_token');
    localStorage.removeItem('username');
    window.location.href = '/admin/login';
}

// 格式化时间
function formatDateTime(timestamp) {
    if (!timestamp) return '-';
    const date = new Date(timestamp);
    return date.toLocaleString('zh-CN');
}

// 显示提示消息
function showMessage(message, type = 'info') {
    // 简单的 alert 实现，可以替换为更好的 UI
    alert(message);
}
