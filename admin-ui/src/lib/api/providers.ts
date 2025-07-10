import { API_BASE_URL } from "./index";

// 供应商相关API
export async function fetchProviders() {
  const response = await fetch(`${API_BASE_URL}/providers/get_all_providers`);
  if (!response.ok) throw new Error('获取供应商列表失败');
  return response.json();
}

// 获取有效供应商列表
export async function fetchProvidersValid() {
  const response = await fetch(`${API_BASE_URL}/providers/get_all_valid_provider`);
  if (!response.ok) throw new Error('获取有效供应商列表失败');
  return response.json();
}

// 保存供应商
export async function saveProvider(providerData: any) {
  const response = await fetch(`${API_BASE_URL}/providers/save_provider`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(providerData),
  });

  // 获取响应数据
  const data = await response.json();

  // 如果响应不成功，抛出包含后端返回的错误信息的异常
  if (!response.ok) {
    throw new Error(data.message || '保存供应商失败');
  }

  return data;
}

// 删除供应商
export async function deleteProvider(providerId: string) {
  const response = await fetch(`${API_BASE_URL}/providers/delete_provider/${providerId}`, {
    method: 'DELETE',
  });

  // 获取响应数据
  const data = await response.json();

  // 如果响应不成功，抛出包含后端返回的错误信息的异常
  if (!response.ok) {
    throw new Error(data.message || '删除供应商失败');
  }

  return data;
}