import { API_BASE_URL } from "./index";

// 系统设置相关API
export async function fetchSystemConfig() {
  const response = await fetch(`${API_BASE_URL}/system_settings/get_all_settings`);
  if (!response.ok) throw new Error('获取系统配置失败');
  return response.json();
}

// 更新系统设置
export async function updateSystemConfig(configData: any) {
  const response = await fetch(`${API_BASE_URL}/system_settings/save_setting`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(configData),
  });
  const data = await response.json();
  if (!response.ok)
    throw new Error(data.message || '更新系统配置失败');
  return data;
}

// 更新系统日志级别
export async function updateSystemLog(setting: any) {
  const response = await fetch(`${API_BASE_URL}/system_settings/set_log_level`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(setting),
  });
  const data = await response.json();
  if (!response.ok)
    throw new Error(data.message || '更新系统日志级别失败');
  return data;
}

// 更新系统API密钥
export async function updateSystemApiKey(setting: any) {
  const response = await fetch(`${API_BASE_URL}/system_settings/save_api_key`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(setting),
  });
  const data = await response.json();
  if (!response.ok)
    throw new Error(data.message || '更新系统API密钥失败');
  return data;
}

// 更新系统连接池设置
export async function updateSystemconnector(setting: any) {
  const response = await fetch(`${API_BASE_URL}/system_settings/set_tcp_connector`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(setting),
  });
  const data = await response.json();
  if (!response.ok)
    throw new Error(data.message || '更新系统连接池参数失败');
  return data;
}

// 导出系统配置（下载文件）
export async function exportSystemConfig() {
  const response = await fetch(`${API_BASE_URL}/system_settings/export_config`, {
    method: 'GET',
  });
  if (!response.ok) {
    const data = await response.json();
    throw new Error(data.message || '导出系统配置失败');
  }
  // 获取blob并返回
  return await response.blob();
}

// 导入系统配置
export async function importSystemConfig(configData: any) {
  const response = await fetch(`${API_BASE_URL}/system_settings/import_config`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({config: configData}),
  });
  const data = await response.json();
  if (!response.ok)
    throw new Error(data.message || '导入系统配置失败');
  return data;
}