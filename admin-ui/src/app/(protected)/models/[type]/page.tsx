
"use client";
import { useState, useEffect } from 'react';
import { useParams } from 'next/navigation';
import {
  fetchModelsByType,
  saveModel,
  deleteModel,
  fetchProvidersValid
} from '@/lib/api';
import { Button } from '@/components/ui/button';
import {
  Card,
  CardHeader,
  CardTitle,
  CardContent,
  CardFooter
} from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Switch } from '@/components/ui/switch';
import { Label } from '@/components/ui/label';
import { PlusIcon } from 'lucide-react';
import { toast } from 'sonner';
import {
  AlertDialog,
  AlertDialogContent,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogCancel,
  AlertDialogAction
} from '@/components/ui/alert-dialog';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue
} from '@/components/ui/select';
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { HelpCircle } from "lucide-react";
import { ModelFormat } from '@/lib/utils';
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from "@/components/ui/accordion"
import { Textarea } from "@/components/ui/textarea"
import { constants } from 'node:fs/promises';

interface Model {
  id: string;
  model_name: string;
  model_id: string;
  provider_id: string;
  model_type: string;
  model_format: string;
  model_custom_json: string;
  is_origin_reasoning: boolean;
  is_valid: boolean;
  is_origin_output: boolean;
}

interface ProviderValid {
  id: string;
  provider_name: string;
}

const ModelForm = ({
  model,
  providers,
  onInputChange,
  onCancel,
  onSave,
  onDelete,
  isValidating,
  isEditing,
  isAdding,
  modelType,
  disabled = false
}: {
  model: Partial<Model>,
  providers: ProviderValid[],
  onInputChange: (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement>) => void,
  onCancel: () => void,
  onSave: () => void,
  onDelete?: (id: string) => void,
  isValidating: boolean,
  isEditing: boolean,
  isAdding: boolean,
  modelType: string,
  disabled?: boolean
}) => {
  return (
    <Card className={`w-full ${(!disabled || isAdding) ? 'border-2 border-blue-500 shadow-lg' : ''}`}>
      <CardHeader>
        <CardTitle>{isEditing ? '编辑模型' : isAdding ? '添加新模型' : model.model_name}</CardTitle>
      </CardHeader>
      <CardContent>
        <div className="space-y-4">
          <div>
            <div className="flex items-center gap-2 mb-1">
              <Label className="text-sm font-medium">模型名称</Label>
              <Tooltip>
                <TooltipTrigger asChild>
                  <HelpCircle className="h-3 w-3 text-gray-500" />
                </TooltipTrigger>
                <TooltipContent side='right'>
                  <p>模型名称不能重复</p>
                </TooltipContent>
              </Tooltip>
            </div>
            <Input
              type="text"
              name="model_name"
              value={model.model_name}
              onChange={onInputChange}
              disabled={disabled}
              className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm"
            />
          </div>
          <div>
            <div className="flex items-center gap-2 mb-1">
              <Label className="text-sm font-medium">模型ID</Label>
              <Tooltip>
                <TooltipTrigger asChild>
                  <HelpCircle className="h-3 w-3 text-gray-500" />
                </TooltipTrigger>
                <TooltipContent side='right'>
                  <p>所选供应商提供的模型ID</p>
                </TooltipContent>
              </Tooltip>
            </div>
            <Input
              type="text"
              name="model_id"
              value={model.model_id}
              onChange={onInputChange}
              disabled={disabled}
              className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm"
            />
          </div>
          <div>
            <Label className="block text-sm font-medium mb-1">供应商</Label>
            <Select
              value={model.provider_id?.toString() || ''}
              onValueChange={(value) => {
                const event = {
                  target: {
                    name: 'provider_id',
                    value
                  }
                } as React.ChangeEvent<HTMLSelectElement>;
                onInputChange(event);
              }}
              disabled={disabled}
            >
              <SelectTrigger className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm">
                <SelectValue placeholder="选择供应商" />
              </SelectTrigger>
              <SelectContent>
                {providers.map((provider) => (
                  <SelectItem key={provider.id} value={provider.id.toString()}>
                    {provider.provider_name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div>
            <div className="flex items-center gap-2 mb-1">
              <Label className="block text-sm font-medium mb-1">模型输入格式</Label>
              <Tooltip>
                <TooltipTrigger asChild>
                  <HelpCircle className="h-3 w-3 text-gray-500" />
                </TooltipTrigger>
                <TooltipContent side='right'>
                  <p>供应商属于哪个就用哪个,若供应商支持openai兼容模式就选openai</p>
                </TooltipContent>
              </Tooltip>
            </div>
            <Select
              value={model.model_format || ''}
              onValueChange={(value) => {
                const event = {
                  target: {
                    name: 'model_format',
                    value
                  }
                } as React.ChangeEvent<HTMLSelectElement>;
                onInputChange(event);
              }}
              disabled={disabled}
            >
              <SelectTrigger className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm">
                <SelectValue placeholder="选择模型格式" />
              </SelectTrigger>
              <SelectContent>
                {Object.entries(ModelFormat).map(([key, value]) => (
                  <SelectItem key={key} value={key}>
                    {value}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          {modelType === 'reasoner' && (
            <div>
              <div className="flex items-center gap-2 mb-1">
                <Label htmlFor="is_origin_reasoning" className="text-sm font-medium mr-2">原生推理</Label>
                <Switch
                  id="is_origin_reasoning"
                  checked={model.is_origin_reasoning}
                  onCheckedChange={(checked) => {
                    if (!disabled) {
                      const event = {
                        target: {
                          name: 'is_origin_reasoning',
                          type: 'checkbox',
                          checked
                        }
                      } as React.ChangeEvent<HTMLInputElement>;
                      onInputChange(event);
                    }
                  }}
                  disabled={disabled}
                />
                <Tooltip>
                  <TooltipTrigger asChild>
                    <HelpCircle className="h-3 w-3 text-gray-500" />
                  </TooltipTrigger>
                  <TooltipContent side='right'>
                    <p>返回格式中把推理内容和正式回答分开为原生推理<br />
                      &lt;Think&gt;包起来的为非原生推理</p>
                  </TooltipContent>
                </Tooltip>
              </div>
            </div>
          )}
          <div>
            <div className="flex items-center gap-2 mb-1">
              <Label htmlFor="is_origin_output" className="text-sm font-medium mr-2">原生输出</Label>
              <Switch
                id="is_origin_output"
                checked={model.is_origin_output}
                onCheckedChange={(checked) => {
                  if (!disabled) {
                    const event = {
                      target: {
                        name: 'is_origin_output',
                        type: 'checkbox',
                        checked
                      }
                    } as React.ChangeEvent<HTMLInputElement>;
                    onInputChange(event);
                  }
                }}
                disabled={disabled}
              />
              <Tooltip>
                  <TooltipTrigger asChild>
                    <HelpCircle className="h-3 w-3 text-gray-500" />
                  </TooltipTrigger>
                  <TooltipContent side='right'>
                    <p>模型被单个调用时,使用供应商返回的格式为原生输出<br />
                    反之使用openai兼容格式输出</p>
                  </TooltipContent>
              </Tooltip>
            </div>
          </div>
          <div>
            <div className="flex items-center gap-2 mb-1">
              <Label htmlFor="is_valid" className="text-sm font-medium mr-2">启用</Label>
              <Switch
                id="is_valid"
                checked={model.is_valid}
                onCheckedChange={(checked) => {
                  if (!disabled) {
                    const event = {
                      target: {
                        name: 'is_valid',
                        type: 'checkbox',
                        checked
                      }
                    } as React.ChangeEvent<HTMLInputElement>;
                    onInputChange(event);
                  }
                }}
                disabled={disabled}
              />
            </div>
          </div>
          <div>
            {disabled ? (
              <div className="py-4">
                <div className="flex justify-between items-center">
                  <h4 className="text-sm font-medium">高级设置</h4>
                </div>
              </div>
            ) : (
              <Accordion type="single" collapsible>
                <AccordionItem value="item-1">
                  <AccordionTrigger>高级设置</AccordionTrigger>
                  <AccordionContent>
                    <Textarea
                      id="model_custom_json"
                      name="model_custom_json"
                      value={model.model_custom_json || ''}
                      onChange={onInputChange}
                      disabled={disabled}
                      rows={6}
                      placeholder='请输入自定义JSON,例如:{"key":"value"}'
                      className="font-mono"
                    />
                  </AccordionContent>
                </AccordionItem>
              </Accordion>
            )}
          </div>
        </div>
      </CardContent>
      <CardFooter className="flex justify-end space-x-2">
        {!disabled && (
          <>
            <Button variant="outline" onClick={onCancel}>取消</Button>
            <Button
              onClick={onSave}
              disabled={isValidating}
            >
              {isValidating ? '验证中...' : (isEditing ? '更新' : '保存')}
            </Button>
          </>
        )}
        {disabled && (
          <>
            <Button variant="outline" onClick={onCancel}>编辑</Button>
            <Button onClick={() => onDelete && model.id && onDelete(model.id)}>删除</Button>
          </>
        )}
      </CardFooter>
    </Card>
  );
};

export default function ModelsPage() {
  const params = useParams();
  const modelTypeParam = (params?.type as string) || 'reasoner';
  const InitialForm = {
    model_name: '',
    model_id: '',
    provider_id: undefined,
    model_type: modelTypeParam,
    model_format: '',
    model_custom_json: '',
    is_origin_reasoning: true,
    is_valid: true,
    is_origin_output: false
  }
  const [models, setModels] = useState<Model[]>([]);
  const [loading, setLoading] = useState(true);
  const [newModel, setNewModel] = useState<Partial<Model>>(InitialForm);
  const [providers, setProviders] = useState<ProviderValid[]>([]);
  const [isAdding, setIsAdding] = useState(false);
  const [isValidating, setIsValidating] = useState(false);
  const [isEditing, setIsEditing] = useState(false);
  const [editingModelId, setEditingModelId] = useState<string | null>(null);
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [modelToDelete, setModelToDelete] = useState<string | null>(null);

  useEffect(() => {
    async function loadModels() {
      try {
        setLoading(true);
        const data = await fetchModelsByType(modelTypeParam);
        setModels(data as Model[]);
      } catch (error) {
        console.error('加载模型列表失败:', error);
        toast.error('加载模型列表失败');
      } finally {
        setLoading(false);
      }
    }

    async function loadProviders() {
      try {
        setLoading(true);
        const data = await fetchProvidersValid();
        setProviders(data as ProviderValid[]);
      } catch (error) {
        console.error('加载供应商列表失败:', error);
        toast.error('加载供应商列表失败');
      } finally {
        setLoading(false);
      }
    }

    loadModels();
    loadProviders();
  }, []);

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement>) => {
    const target = e.target;
    const name = target.name;
    const value = target.value;

    if (target instanceof HTMLInputElement && target.type === 'checkbox') {
      const checked = target.checked;
      setNewModel(prev => ({ ...prev, [name]: checked }));
    } else {
      setNewModel(prev => ({ ...prev, [name]: value }));
    }
  };

  const handleAddModel = async () => {
    try {
      setIsValidating(true);
      console.log(newModel);
      // 这里可以添加验证逻辑
      if (!newModel.model_name) {
        toast.error('模型名称不能为空');
        return;
      }
      if (!newModel.model_id) {
        toast.error('模型ID不能为空');
        return;
      }
      if (!newModel.provider_id || newModel.provider_id === '') {
        toast.error('供应商不能为空');
        return;
      }
      try {
        if (newModel.model_custom_json && newModel.model_custom_json.trim() !== '') {
          const parsed = JSON.parse(newModel.model_custom_json);
          // 确保解析后的结果是对象类型
          if (typeof parsed !== 'object' || parsed === null || Array.isArray(parsed)) {
            toast.error('模型自定义配置必须是JSON对象格式，例如：{"key":"value"}');
            return;
          }
        }
      } catch (error) {
        toast.error('模型自定义配置不是合法的 JSON');
        return;
      }
      // 保存模型
      const result = await saveModel(newModel);

      // 更新列表
      if (isEditing) {
        // 如果是编辑，替换原有数据
        setModels(prev => prev.map(item => item.id === newModel.id ? result as Model : item));
      } else {
        // 如果是新增，添加到列表
        setModels(prev => [...prev, result as Model]);
      }

      // 重置表单
      setNewModel(InitialForm);

      toast.success('保存成功');

      setIsAdding(false);
      setIsEditing(false);
      setEditingModelId(null);
    } catch (error: any) {
      // 显示错误信息
      const errorMessage = error.message || '保存失败';
      toast.error(errorMessage);
    } finally {
      setIsValidating(false);
    }
  };

  const handleCancel = () => {
    setIsAdding(false);
    setIsEditing(false);
    setEditingModelId(null);
    setNewModel(InitialForm);
  };

  const handleEdit = (model: Model) => {
    setNewModel({...model});
    setIsAdding(true);
    setIsEditing(true);
    setEditingModelId(model.id);
  };

  const handleDelete = async (modelId: string) => {
    setModelToDelete(modelId);
    setDeleteDialogOpen(true);
  };

  const confirmDelete = async () => {
    if (modelToDelete) {
      try {
        await deleteModel(modelToDelete);
        // 从列表中移除已删除的模型
        setModels(prev => prev.filter(item => item.id !== modelToDelete));
        toast.success('删除成功');
      } catch (error: any) {
        const errorMessage = error.message || '删除失败';
        toast.error(errorMessage);
      } finally {
        setDeleteDialogOpen(false);
        setModelToDelete(null);
      }
    }
  };

  return (
    <div>
      <div className="flex justify-between items-center mb-6">
        <h1 className="text-2xl font-bold">{modelTypeParam=="reasoner"?"推理模型":"目标模型"}管理</h1>
      </div>

      {loading ? (
        <p className="text-gray-500">加载中...</p>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {models.map((model) => (
            <ModelForm
              key={model.id}
              model={editingModelId === model.id ? newModel : model}
              providers={providers}
              onInputChange={handleInputChange}
              onCancel={editingModelId === model.id ? handleCancel : () => handleEdit(model)}
              onSave={handleAddModel}
              onDelete={handleDelete}
              isValidating={isValidating}
              isEditing={editingModelId === model.id}
              isAdding={false}
              modelType={modelTypeParam}
              disabled={editingModelId !== model.id}
            />
          ))}
          {/* 添加模型卡片 */}
          {!isAdding && (
            <Card
              className="w-full border-dashed flex items-center justify-center cursor-pointer hover:bg-gray-50 transition-colors"
              onClick={() => setIsAdding(true)}
            >
              <CardContent className="flex flex-col items-center justify-center h-full py-12">
                <div className="rounded-full bg-gray-100 p-3 mb-4">
                  <PlusIcon className="h-6 w-6 text-gray-500" />
                </div>
                <p className="text-gray-500 font-medium">添加模型</p>
              </CardContent>
            </Card>
          )}
          {/* 添加模型表单 */}
          {isAdding && !isEditing && (
            <ModelForm
              model={newModel}
              providers={providers}
              onInputChange={handleInputChange}
              onCancel={handleCancel}
              onSave={handleAddModel}
              isValidating={isValidating}
              isEditing={false}
              isAdding={true}
              modelType={modelTypeParam}
              disabled={false}
            />
          )}
        </div>
      )}

      {/* 删除确认对话框 */}
      <AlertDialog open={deleteDialogOpen} onOpenChange={setDeleteDialogOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>确认删除</AlertDialogTitle>
            <AlertDialogDescription>
              您确定要删除这个模型吗？此操作无法撤销。
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>取消</AlertDialogCancel>
            <AlertDialogAction onClick={confirmDelete}>确认删除</AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
