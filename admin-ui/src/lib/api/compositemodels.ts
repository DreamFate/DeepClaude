import { API_BASE_URL } from "./index";

// 组合模型相关API
export async function fetchCompositeModels() {
  const response = await fetch(`${API_BASE_URL}/composite_models/get_all_composite_models`);
  if (!response.ok) throw new Error('获取组合模型列表失败');
  return response.json();
}

// 保存组合模型
export async function saveCompositeModel(modelData: any) {
  const response = await fetch(`${API_BASE_URL}/composite_models/save_composite_model`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(modelData),
  });
  const data = await response.json();
  if (!response.ok)
    throw new Error(data.message || '保存组合模型失败');
  return data;
}

// 删除组合模型
export async function deleteCompositeModel(compositeModelId: string) {
  const response = await fetch(`${API_BASE_URL}/composite_models/delete_composite_model/${compositeModelId}`, {
    method: 'DELETE',
  });

  // 获取响应数据
  const data = await response.json();

  // 如果响应不成功，抛出包含后端返回的错误信息的异常
  if (!response.ok) {
    throw new Error(data.message || '删除组合模型失败');
  }

  return data;
}