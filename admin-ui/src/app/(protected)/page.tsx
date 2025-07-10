"use client";
import { useState, useEffect } from 'react';
import {
  fetchCompositeModels,
  saveCompositeModel,
  fetchModelsValid,
  deleteCompositeModel
} from '@/lib/api';
import { Button } from '@/components/ui/button';
import {
  Card,
  CardHeader,
  CardTitle,
  CardDescription,
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

interface CompositeModel {
  id: string;
  model_name: string;
  reasoner_model_id: string;
  general_model_id: string;
  is_valid: boolean;
}

interface Model {
  id: string;
  model_name: string;
}

const InitialForm = {
  model_name: '',
  reasoner_model_id: undefined,
  general_model_id: undefined,
  is_valid: true
}

const CompositeModelForm = ({
  compositeModel,
  reasonerModels,
  generalModels,
  onInputChange,
  onCancel,
  onSave,
  onDelete,
  isValidating,
  isEditing,
  isAdding,
  disabled = false
}: {
  compositeModel: Partial<CompositeModel>,
  reasonerModels: Model[],
  generalModels: Model[],
  onInputChange: (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) => void,
  onCancel: () => void,
  onSave: () => void,
  onDelete?: (id: string) => void,
  isValidating: boolean,
  isEditing: boolean,
  isAdding: boolean,
  disabled?: boolean
}) => {
  return (
    <Card className={`w-full ${(!disabled || isAdding) ? 'border-2 border-blue-500 shadow-lg' : ''}`}>
      <CardHeader>
        <CardTitle>{isEditing ? '编辑组合模型' : isAdding ? '添加新组合模型' : compositeModel.model_name}</CardTitle>
      </CardHeader>
      <CardContent>
        <div className="space-y-4">
          <div>
            <Label className="block text-sm font-medium mb-1">组合模型名称</Label>
            <Input
              type="text"
              name="model_name"
              value={compositeModel.model_name}
              onChange={onInputChange}
              disabled={disabled}
              className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm"
            />
          </div>
          <div>
            <Label className="block text-sm font-medium mb-1">推理模型</Label>
            <Select
              value={compositeModel.reasoner_model_id}
              onValueChange={(value) => {
                if (!disabled) {
                  const event = {
                    target: {
                      name: 'reasoner_model_id',
                      value
                    }
                  } as React.ChangeEvent<HTMLSelectElement>;
                  onInputChange(event);
                }
              }}
              disabled={disabled}
            >
              <SelectTrigger className="w-full">
                <SelectValue placeholder="选择推理模型" />
              </SelectTrigger>
              <SelectContent>
                {reasonerModels.map((model) => (
                  <SelectItem key={model.id} value={model.id}>
                    {model.model_name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div>
            <Label className="block text-sm font-medium mb-1">目标模型</Label>
            <Select
              value={compositeModel.general_model_id}
              onValueChange={(value) => {
                if (!disabled) {
                  const event = {
                    target: {
                      name: 'general_model_id',
                      value
                    }
                  } as React.ChangeEvent<HTMLSelectElement>;
                  onInputChange(event);
                }
              }}
              disabled={disabled}
            >
              <SelectTrigger className="w-full">
                <SelectValue placeholder="选择目标模型" />
              </SelectTrigger>
              <SelectContent>
                {generalModels.map((model) => (
                  <SelectItem key={model.id} value={model.id}>
                    {model.model_name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="flex items-center">
            <Label htmlFor="is_valid" className="text-sm font-medium mr-2">启用</Label>
            <Switch
              id="is_valid"
              checked={compositeModel.is_valid}
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
            <Button onClick={() => onDelete && compositeModel.id && onDelete(compositeModel.id)}>删除</Button>
          </>
        )}
      </CardFooter>
    </Card>
  );
};

export default function CompositeModelsPage() {
  const [compositeModels, setCompositeModels] = useState<CompositeModel[]>([]);
  const [reasonerModels, setReasonerModels] = useState<Model[]>([]);
  const [generalModels, setGeneralModels] = useState<Model[]>([]);
  const [loading, setLoading] = useState(true);
  const [newCompositeModel, setNewCompositeModel] = useState<Partial<CompositeModel>>(InitialForm);
  const [isAdding, setIsAdding] = useState(false);
  const [isValidating, setIsValidating] = useState(false);
  const [isEditing, setIsEditing] = useState(false);
  const [editingModelId, setEditingModelId] = useState<string | null>(null);
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [modelToDelete, setModelToDelete] = useState<string | null>(null);

  useEffect(() => {
    async function loadData() {
      try {
        setLoading(true);
        const data = await fetchCompositeModels();
        setCompositeModels(data as CompositeModel[]);
      } catch (error) {
        toast.error('加载组合模型数据失败');
      } finally {
        setLoading(false);
      }
    }
    async function loadModels() {
      try {
        setLoading(true);
        const modelsData = await fetchModelsValid();
        const reasonerModels = modelsData['reasoner'] || [];
        const generalModels = modelsData['general'] || [];
        setReasonerModels(reasonerModels as Model[]);
        setGeneralModels(generalModels as Model[]);
      } catch (error) {
        toast.error('加载模型数据失败');
      } finally {
        setLoading(false);
      }
    }
    loadData();
    loadModels();
  }, []);

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) => {
    const { name, value, type } = e.target as HTMLInputElement;
    if (type === 'checkbox') {
      const checked = (e.target as HTMLInputElement).checked;
      setNewCompositeModel(prev => ({ ...prev, [name]: checked }));
    } else {
      setNewCompositeModel(prev => ({ ...prev, [name]: value }));
    }
  };

  const handleAddCompositeModel = async () => {
    try {
      setIsValidating(true);
      if (!newCompositeModel.model_name) {
        toast.error('请输入组合模型名称');
        return;
      }
      if (!newCompositeModel.reasoner_model_id) {
        toast.error('请选择推理模型');
        return;
      }
      if (!newCompositeModel.general_model_id) {
        toast.error('请选择目标模型');
        return;
      }
      const result = await saveCompositeModel(newCompositeModel);
      if (isEditing) {
        setCompositeModels(prev => prev.map(item => item.id === newCompositeModel.id ? result as CompositeModel : item));
      } else {
        setCompositeModels(prev => [...prev, result as CompositeModel]);
      }
      setNewCompositeModel(InitialForm);
      toast.success('保存成功');
      setIsAdding(false);
      setIsEditing(false);
      setEditingModelId(null);
    } catch (error: any) {
      toast.error(error.message || '保存失败');
    } finally {
      setIsValidating(false);
    }
  };

  const handleCancel = () => {
    setIsAdding(false);
    setIsEditing(false);
    setEditingModelId(null);
    setNewCompositeModel(InitialForm);
  };

  const handleEdit = (model: CompositeModel) => {
    setNewCompositeModel({...model});
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
        await deleteCompositeModel(modelToDelete);
        setCompositeModels(prev => prev.filter(item => item.id !== modelToDelete));
        toast.success('删除成功');
      } catch (error: any) {
        toast.error(error.message || '删除失败');
      } finally {
        setDeleteDialogOpen(false);
        setModelToDelete(null);
      }
    }
  };

  return (
    <div>
      <div className="flex justify-between items-center mb-6">
        <h1 className="text-2xl font-bold">组合模型管理</h1>
      </div>
      {loading ? (
        <p className="text-gray-500">加载中...</p>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {compositeModels.map((model) => (
            <CompositeModelForm
              key={model.id}
              compositeModel={editingModelId === model.id ? newCompositeModel : model}
              reasonerModels={reasonerModels}
              generalModels={generalModels}
              onInputChange={handleInputChange}
              onCancel={editingModelId === model.id ? handleCancel : () => handleEdit(model)}
              onSave={handleAddCompositeModel}
              onDelete={handleDelete}
              isValidating={isValidating}
              isEditing={editingModelId === model.id}
              isAdding={false}
              disabled={editingModelId !== model.id}
            />
          ))}
          {!isAdding && (
            <Card
              className="w-full border-dashed flex items-center justify-center cursor-pointer hover:bg-gray-50 transition-colors"
              onClick={() => setIsAdding(true)}
            >
              <CardContent className="flex flex-col items-center justify-center h-full py-12">
                <div className="rounded-full bg-gray-100 p-3 mb-4">
                  <PlusIcon className="h-6 w-6 text-gray-500" />
                </div>
                <p className="text-gray-500 font-medium">添加组合模型</p>
              </CardContent>
            </Card>
          )}
          {isAdding && !isEditing && (
            <CompositeModelForm
              compositeModel={newCompositeModel}
              reasonerModels={reasonerModels}
              generalModels={generalModels}
              onInputChange={handleInputChange}
              onCancel={handleCancel}
              onSave={handleAddCompositeModel}
              isValidating={isValidating}
              isEditing={false}
              isAdding={true}
              disabled={false}
            />
          )}
        </div>
      )}
      <AlertDialog open={deleteDialogOpen} onOpenChange={setDeleteDialogOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>确认删除</AlertDialogTitle>
            <AlertDialogDescription>
              您确定要删除此组合模型吗？此操作无法撤销。
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>取消</AlertDialogCancel>
            <AlertDialogAction onClick={confirmDelete}>删除</AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}