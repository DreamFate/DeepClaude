import { API_BASE_URL } from "./index";

// 获取指定类型的所有模型
export async function fetchModelsByType(model_type: string) {
  const response = await fetch(`${API_BASE_URL}/models/get_all_models/${model_type}`);
  if (!response.ok) throw new Error('获取模型列表失败');
  return response.json();
}

// 获取有效模型列表
export async function fetchModelsValid() {
  const response = await fetch(`${API_BASE_URL}/models/get_all_valid_models`);
  if (!response.ok) throw new Error('获取有效组合模型列表失败');
  return response.json();
}

// 保存模型
export async function saveModel(modelData: any) {
  const response = await fetch(`${API_BASE_URL}/models/save_model`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(modelData),
  });
  const data = await response.json();
  if (!response.ok)
    throw new Error(data.message || '保存模型失败');
  return data;
}

// 删除模型
export async function deleteModel(modelId: string) {
  const response = await fetch(`${API_BASE_URL}/models/delete_model/${modelId}`, {
    method: 'DELETE',
  });

  // 获取响应数据
  const data = await response.json();

  // 如果响应不成功，抛出包含后端返回的错误信息的异常
  if (!response.ok) {
    throw new Error(data.message || '删除模型失败');
  }

  return data;
}
