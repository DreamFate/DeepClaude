"use client";
import { useState, useEffect } from 'react';
import { fetchProviders, saveProvider, deleteProvider } from '@/lib/api';
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
import { ProviderFormat } from '@/lib/utils';
import { HelpCircle, Eye, EyeOff } from "lucide-react";

interface Provider {
  id: string;
  provider_name: string;
  api_key: string;
  api_base_url: string;
  api_request_address: string;
  provider_format: string;
  is_proxy_open: boolean;
  is_valid: boolean;
}

const ProviderForm = ({
  provider,
  onInputChange,
  onCancel,
  onSave,
  onDelete,
  isValidating,
  isEditing,
  isAdding,
  disabled = false
}: {
  provider: Partial<Provider>,
  onInputChange: (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) => void,
  onCancel: () => void,
  onSave: () => void,
  onDelete?: (id: string) => void,
  isValidating: boolean,
  isEditing: boolean,
  isAdding: boolean,
  disabled?: boolean
}) => {

  const [showApiKey, setShowApiKey] = useState(false);
  return (
    <Card className={`w-full ${(!disabled || isAdding) ? 'border-2 border-blue-500 shadow-lg' : ''}`}>
      <CardHeader>
        <CardTitle>{isEditing ? '编辑供应商' : isAdding ? '添加新供应商' : provider.provider_name}</CardTitle>
      </CardHeader>
      <CardContent>
        <div className="space-y-4">
          <div>
            <Label className="block text-sm font-medium mb-1">供应商名称</Label>
            <Input
              type="text"
              name="provider_name"
              value={provider.provider_name}
              onChange={onInputChange}
              disabled={disabled}
              className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm"
            />
          </div>
          <div>
            <Label className="block text-sm font-medium mb-1">API密钥</Label>
            <div className="relative">
              <Input
                type={showApiKey ? "text" : "password"}
                name="api_key"
                value={provider.api_key}
                onChange={onInputChange}
                disabled={disabled}
                className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm"
              />
              <button
                  type="button"
                  onClick={() => setShowApiKey(!showApiKey)}
                  disabled={disabled}
                  className="absolute right-2 top-1/2 -translate-y-1/2 text-gray-500 hover:text-gray-700"
                >
                {showApiKey ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
              </button>
            </div>
          </div>
          <div>
            <Label className="block text-sm font-medium mb-1">API基础URL</Label>
            <Input
              type="text"
              name="api_base_url"
              value={provider.api_base_url}
              onChange={onInputChange}
              disabled={disabled}
              className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm"
            />
          </div>
          <div>
            <Label className="block text-sm font-medium mb-1">API请求地址</Label>
            <Input
              type="text"
              name="api_request_address"
              value={provider.api_request_address}
              onChange={onInputChange}
              disabled={disabled}
              className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm"
            />
          </div>
          <div>
            <Label className="block text-sm font-medium mb-1">供应商格式</Label>
            <Select
              value={provider.provider_format || ''}
              onValueChange={(value) => {
                const event = {
                  target: {
                    name: 'provider_format',
                    value
                  }
                } as React.ChangeEvent<HTMLSelectElement>;
                onInputChange(event);
              }}
              disabled={disabled}
            >
              <SelectTrigger className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm">
                <SelectValue placeholder="选择供应商格式" />
              </SelectTrigger>
              <SelectContent>
                {Object.entries(ProviderFormat).map(([key, value]) => (
                  <SelectItem key={key} value={key}>
                    {value}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="flex items-center">
            <Label htmlFor="is_proxy_open" className="text-sm font-medium mr-2">启用代理</Label>
            <Switch
              id="is_proxy_open"
              checked={provider.is_proxy_open}
              onCheckedChange={(checked) => {
                if (!disabled) {
                  const event = {
                    target: {
                      name: 'is_proxy_open',
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
          <div className="flex items-center">
            <Label htmlFor="is_valid" className="text-sm font-medium mr-2">启用</Label>
            <Switch
              id="is_valid"
              checked={provider.is_valid}
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
            <Button onClick={() => onDelete && provider.id && onDelete(provider.id)}>删除</Button>
          </>
        )}
      </CardFooter>
    </Card>
  );
};

export default function ProvidersPage() {
  const InitialForm = {
    provider_name: '',
    api_key: '',
    api_base_url: '',
    api_request_address: '',
    provider_format: '',
    is_proxy_open: false,
    is_valid: true
  }
  const [providers, setProviders] = useState<Provider[]>([]);
  const [loading, setLoading] = useState(true);
  const [newProvider, setNewProvider] = useState<Partial<Provider>>(InitialForm);
  const [isAdding, setIsAdding] = useState(false);
  const [isValidating, setIsValidating] = useState(false);
  const [isEditing, setIsEditing] = useState(false);
  const [editingProviderId, setEditingProviderId] = useState<string | null>(null);
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [providerToDelete, setProviderToDelete] = useState<string | null>(null);

  useEffect(() => {
    async function loadProviders() {
      try {
        setLoading(true);
        const data = await fetchProviders();
        setProviders(data as Provider[]);
      } catch (error) {
        console.error('加载供应商列表失败:', error);
        toast.error('加载供应商列表失败');
      } finally {
        setLoading(false);
      }
    }

    loadProviders();
  }, []);

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) => {
    const { name, value, type } = e.target as HTMLInputElement;

    if (type === 'checkbox') {
      const checked = (e.target as HTMLInputElement).checked;
      setNewProvider(prev => ({ ...prev, [name]: checked }));
    } else {
      setNewProvider(prev => ({ ...prev, [name]: value }));
    }
  };

  const handleAddProvider = async () => {
    try {
      setIsValidating(true);
      // 这里可以添加验证逻辑

      if (!newProvider.provider_name) {
        toast.error('请填写供应商名称');
        return;
      }
      if (!newProvider.api_key) {
        toast.error('请填写API密钥');
        return;
      }
      if (!newProvider.api_base_url) {
        toast.error('请填写API基础URL');
        return;
      }
      if (!newProvider.api_request_address) {
        toast.error('请填写API请求地址');
        return;
      }

      // 保存供应商
      const result = await saveProvider(newProvider);

      // 更新列表
      if (isEditing) {
        // 如果是编辑，替换原有数据
        setProviders(prev => prev.map(item => item.id === newProvider.id ? result as Provider : item));
      } else {
        // 如果是新增，添加到列表
        setProviders(prev => [...prev, result as Provider]);
      }

      // 重置表单
      setNewProvider(InitialForm);

      toast.success('保存成功');

      setIsAdding(false);
      setIsEditing(false);
      setEditingProviderId(null);
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
    setEditingProviderId(null);
    setNewProvider(InitialForm);
  };

  const handleEdit = (provider: Provider) => {
    setNewProvider({...provider});
    setIsAdding(true);
    setIsEditing(true);
    setEditingProviderId(provider.id);
  };

  const handleDelete = async (providerId: string) => {
    setProviderToDelete(providerId);
    setDeleteDialogOpen(true);
  };

  const confirmDelete = async () => {
    if (providerToDelete) {
      try {
        await deleteProvider(providerToDelete);
        // 从列表中移除已删除的供应商
        setProviders(prev => prev.filter(item => item.id !== providerToDelete));
        toast.success('删除成功');
      } catch (error: any) {
        const errorMessage = error.message || '删除失败';
        toast.error(errorMessage);
      } finally {
        setDeleteDialogOpen(false);
        setProviderToDelete(null);
      }
    }
  };

  return (
    <div>
      <div className="flex justify-between items-center mb-6">
        <h1 className="text-2xl font-bold">供应商管理</h1>
      </div>

      {loading ? (
        <p className="text-gray-500">加载中...</p>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {providers.map((provider) => (
            <ProviderForm
              key={provider.id}
              provider={editingProviderId === provider.id ? newProvider : provider}
              onInputChange={handleInputChange}
              onCancel={editingProviderId === provider.id ? handleCancel : () => handleEdit(provider)}
              onSave={handleAddProvider}
              onDelete={handleDelete}
              isValidating={isValidating}
              isEditing={editingProviderId === provider.id}
              isAdding={false}
              disabled={editingProviderId !== provider.id}
            />
          ))}
          {/* 添加供应商卡片 */}
          {!isAdding && (
            <Card
              className="w-full border-dashed flex items-center justify-center cursor-pointer hover:bg-gray-50 transition-colors"
              onClick={() => setIsAdding(true)}
            >
              <CardContent className="flex flex-col items-center justify-center h-full py-12">
                <div className="rounded-full bg-gray-100 p-3 mb-4">
                  <PlusIcon className="h-6 w-6 text-gray-500" />
                </div>
                <p className="text-gray-500 font-medium">添加供应商</p>
              </CardContent>
            </Card>
          )}
          {/* 添加供应商表单 */}
          {isAdding && !isEditing && (
            <ProviderForm
              provider={newProvider}
              onInputChange={handleInputChange}
              onCancel={handleCancel}
              onSave={handleAddProvider}
              isValidating={isValidating}
              isEditing={false}
              isAdding={true}
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
              您确定要删除此供应商吗？此操作无法撤销。
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
