"use client";
import { useState, useEffect } from 'react';
import {
  fetchSystemConfig, updateSystemConfig,
  updateSystemLog, updateSystemconnector,
  exportSystemConfig,importSystemConfig,
  updateSystemApiKey
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
import { Label } from '@/components/ui/label';
import { toast } from 'sonner';
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
import { HelpCircle, Eye, EyeOff } from "lucide-react";
import { useAuth } from "@/lib/auth-context";

interface SystemSettings {
  api_key: string;
  proxy_address: string;
  log_level: string;
  tcp_connector_limit: number;
  tcp_connector_limit_per_host: number;
  tcp_keepalive_timeout: number;
}

export default function SettingsPage() {
  const [settings, setSettings] = useState<Partial<SystemSettings>>({
    api_key: '',
    proxy_address: '',
    log_level: '',
    tcp_connector_limit: undefined,
    tcp_connector_limit_per_host: undefined,
    tcp_keepalive_timeout: undefined
  });
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [showApiKey, setShowApiKey] = useState(false);
  const { logout } = useAuth();

  useEffect(() => {
    async function loadSettings() {
      try {
        setLoading(true);
        const data = await fetchSystemConfig();
        setSettings(data as SystemSettings);
      } catch (error) {
        toast.error('加载系统设置失败');
      } finally {
        setLoading(false);
      }
    }

    loadSettings();
  }, []);

  const handleChange = (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) => {
    const { name, value } = e.target;
    setSettings(prev => ({
      ...prev,
      [name]: value
    }));
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      setSaving(true);
      const setting = [{
        setting_key: 'proxy_address',
        setting_value: settings.proxy_address,
        setting_type: 'str'
      }];
      await updateSystemConfig(setting);
      toast.success('系统设置已更新');
    } catch (error: any) {
      toast.error(error.message || '更新系统设置失败');
    } finally {
      setSaving(false);
    }
  };

  const handleLogSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      setSaving(true);
      const logsetting = [{
        setting_key: 'log_level',
        setting_value: settings.log_level,
        setting_type: 'str'
      }];
      await updateSystemLog(logsetting);
      toast.success('系统日志级别已更新');
    } catch (error: any) {
      toast.error(error.message || '更新系统日志级别失败');
    } finally {
      setSaving(false);
    }
  };

  const handleApiKeySubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      setSaving(true);
      const setting = [{
        setting_key: 'api_key',
        setting_value: settings.api_key,
        setting_type: 'str'
      }];
      await updateSystemApiKey(setting);
      toast.success('系统API密钥已更新,请重新登录');
      logout();
    } catch (error: any) {
      toast.error(error.message || '更新系统API密钥失败');
    } finally {
      setSaving(false);
    }
  };

  const handleConnectorSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      setSaving(true);
      if (!settings.tcp_connector_limit || !settings.tcp_connector_limit_per_host || !settings.tcp_keepalive_timeout) {
        toast.error('参数不能为空');
        return;
      }
      if (settings.tcp_connector_limit < 0 || settings.tcp_connector_limit_per_host < 0 || settings.tcp_keepalive_timeout < 0) {
        toast.error('参数不能小于0');
        return;
      }
      if (settings.tcp_connector_limit < settings.tcp_connector_limit_per_host) {
        toast.error('总连接数不能小于供应商连接数');
        return;
      }
      const connectorsetting = [{
        setting_key: 'tcp_connector_limit',
        setting_value: settings.tcp_connector_limit,
        setting_type: 'int'
      }, {
        setting_key: 'tcp_connector_limit_per_host',
        setting_value: settings.tcp_connector_limit_per_host,
        setting_type: 'int'
      }, {
        setting_key: 'tcp_keepalive_timeout',
        setting_value: settings.tcp_keepalive_timeout,
        setting_type: 'float'
      }];
      await updateSystemconnector(connectorsetting);
      toast.success('系统连接池参数已更新');
    } catch (error: any) {
      toast.error(error.message || '更新系统连接池参数失败');
    } finally {
      setSaving(false);
    }
  };

  const handleExportConfig = async () => {
    try {
      const blob = await exportSystemConfig();
      // 检查浏览器是否支持showSaveFilePicker
      if ('showSaveFilePicker' in window) {
        // @ts-ignore
        const handle = await window.showSaveFilePicker({
          suggestedName: 'deepclaude_config.json',
          types: [{
            description: 'JSON文件',
            accept: { 'application/json': ['.json'] }
          }]
        });
        const writable = await handle.createWritable();
        await writable.write(blob);
        await writable.close();
        toast.success('配置导出成功');
      } else {
        // 兼容老浏览器，自动下载
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = 'deepclaude_config.json';
        document.body.appendChild(a);
        a.click();
        a.remove();
        window.URL.revokeObjectURL(url);
        toast.success('配置导出成功');
      }
    } catch (error: any) {
      toast.error(error.message || '配置导出失败');
    }
  };

  const handleImportConfig = async () => {
    try {
      // 获取 input 元素
      const input = document.getElementById('importConfig') as HTMLInputElement;
      if (!input.files || input.files.length === 0) {
        toast.error('请选择文件');
        return;
      }
      const file = input.files[0];
      const fileContent = await file.text();
      const configData = JSON.parse(fileContent);
      await importSystemConfig(configData);
      toast.success('配置导入成功,请重新登录');
      logout();
    } catch (error: any) {
      toast.error(error.message || '配置导入失败');
    }
  };

  if (loading) {
    return <p className="text-gray-500">加载中...</p>;
  }

  return (
    <div>
      <div className="flex w-full items-center gap-6">
        <h1 className="text-2xl font-bold mb-6">系统设置</h1>
        <Button className="mb-5" onClick={handleExportConfig}>导出配置</Button>
      </div>
      <div className="flex w-full max-w-sm items-center gap-2 mb-6">
        <Input id="importConfig" type="file" />
        <Button onClick={handleImportConfig} type="submit">导入配置</Button>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        <Card>
          <CardHeader>
            <CardTitle>日志级别设置</CardTitle>
          </CardHeader>
          <CardContent>
          <div className="flex w-full max-w-sm items-center gap-2">
            <Select value={settings.log_level} onValueChange={(value) => {
              const event = {
                target: {
                  name: 'log_level',
                  value
                }
              } as React.ChangeEvent<HTMLSelectElement>;
              handleChange(event);
            }}>
              <SelectTrigger className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm">
                <SelectValue placeholder="选择日志级别" />
              </SelectTrigger>
              <SelectContent>
                  <SelectItem value="DEBUG">DEBUG</SelectItem>
                  <SelectItem value="INFO">INFO</SelectItem>
                  <SelectItem value="WARNING">WARNING</SelectItem>
                  <SelectItem value="ERROR">ERROR</SelectItem>
                  <SelectItem value="CRITICAL">CRITICAL</SelectItem>
              </SelectContent>
            </Select>
            <Button onClick={handleLogSubmit}>应用</Button>
            </div>
          </CardContent>
          <CardHeader>
            <CardTitle>api密钥设置</CardTitle>
          </CardHeader>
          <CardContent>
          <div className="flex w-full max-w-sm items-center gap-2">
            <div className="relative w-full">
              <Input
                type={showApiKey ? "text" : "password"}
                name="api_key"
                value={settings.api_key}
                onChange={handleChange}
              />
              <button
                type="button"
                onClick={() => setShowApiKey(!showApiKey)}
                className="absolute right-2 top-1/2 -translate-y-1/2 text-gray-500 hover:text-gray-700"
              >
                {showApiKey ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
              </button>
            </div>
            <Button onClick={handleApiKeySubmit}>应用</Button>
            </div>
          </CardContent>
          <CardFooter className="flex justify-end space-x-2">

        </CardFooter>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle>供应商连接池设置</CardTitle>
          </CardHeader>
          <CardContent>
          <div className="space-y-4">
            <div>
              <div className="flex items-center gap-2 mb-1">
                <Label className="text-sm font-medium">连接池总数量</Label>
                <Tooltip>
                  <TooltipTrigger asChild>
                    <HelpCircle className="h-3 w-3 text-gray-500" />
                  </TooltipTrigger>
                  <TooltipContent side='right'>
                    <p>允许同时连接的最大数量</p>
                  </TooltipContent>
                </Tooltip>
              </div>
              <Input
                type="number"
                name="tcp_connector_limit"
                value={settings.tcp_connector_limit}
                onChange={handleChange}
                className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm"
              />
            </div>
            <div>
              <div className="flex items-center gap-2 mb-1">
                <Label className="text-sm font-medium">供应商连接数</Label>
                <Tooltip>
                  <TooltipTrigger asChild>
                    <HelpCircle className="h-3 w-3 text-gray-500" />
                  </TooltipTrigger>
                  <TooltipContent side='right'>
                    <p>每个供应商同时连接的最大数量</p>
                  </TooltipContent>
                </Tooltip>
              </div>
              <Input
                type="number"
                name="tcp_connector_limit_per_host"
                value={settings.tcp_connector_limit_per_host}
                onChange={handleChange}
                className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm"
              />
            </div>
            <div>
              <div className="flex items-center gap-2 mb-1">
                <Label className="text-sm font-medium">连接保持活跃时间(秒)</Label>
                <Tooltip>
                  <TooltipTrigger asChild>
                    <HelpCircle className="h-3 w-3 text-gray-500" />
                  </TooltipTrigger>
                  <TooltipContent side='right'>
                    <p>每个连接保持活跃的时间</p>
                  </TooltipContent>
                </Tooltip>
              </div>
                <Input
                  type="number"
                  step="any"
                  name="tcp_keepalive_timeout"
                  value={settings.tcp_keepalive_timeout}
                  onChange={handleChange}
                  className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm"
                />
              </div>
          </div>
          </CardContent>
          <CardFooter className="flex justify-end space-x-2">
              <Button onClick={handleConnectorSubmit}>应用</Button>
        </CardFooter>
        </Card>
      </div>
      <h2 className="text-xl font-bold mb-6 mt-6">其他设置</h2>
      <div>
        <Label className="text-sm font-medium">代理URL</Label>
        <Input
          type="text"
          name="proxy_address"
          value={settings.proxy_address}
          onChange={handleChange}
          className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm"
        />
      </div>
      <div className="flex justify-end space-x-2 mt-4">
        <Button onClick={handleSubmit}>保存其他设置</Button>
      </div>
    </div>
  );
}
