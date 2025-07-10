import { API_BASE_URL } from "./index";

// 验证密钥
export async function verifyApiKey(apiKey: string) {
  const response = await fetch(`${API_BASE_URL}/auth/verify`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ apiKey }),
  });
  if (!response.ok) throw new Error('验证密钥失败');
  return response.json();
}

// 检查是否已认证
export async function checkAuth() {
  try {
    const response = await fetch(`${API_BASE_URL}/auth/status`);
    if (!response.ok) return { authenticated: false };
    return response.json();
  } catch (error) {
    return { authenticated: false };
  }
}

// 登出
export async function logout() {
  try {
    const response = await fetch(`${API_BASE_URL}/auth/logout`, {
      method: 'POST',
    });
    if (!response.ok) throw new Error('登出失败');
    return response.json();
  } catch (error) {
    console.error('登出时发生错误:', error);
    return { success: false };
  }
}