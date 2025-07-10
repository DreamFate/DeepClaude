"use client";

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { useAuth } from '@/lib/auth-context';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import { toast } from 'sonner';

export default function AuthPage() {
  const [apiKey, setApiKey] = useState('');
  const [isVerifying, setIsVerifying] = useState(false);
  const router = useRouter();
  const { verifyKey } = useAuth();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!apiKey.trim()) {
      toast.error('请输入API密钥');
      return;
    }

    setIsVerifying(true);

    try {
      const success = await verifyKey(apiKey);
      if (success) {
        router.push('/');
      } else {
        toast.error('无效的API密钥，请重试');
      }
    } catch (err) {
      toast.error('验证过程中出错，请重试');
    } finally {
      setIsVerifying(false);
    }
  };

  return (
    <div className="flex min-h-screen flex-col items-center justify-center p-4">
      <div className="w-full max-w-md space-y-8">
        <div className="text-center">
          <h1 className="text-3xl font-bold">DeepClaude 模型配置管理</h1>
        </div>

        <form className="mt-8 space-y-6" onSubmit={handleSubmit}>
          <div className="space-y-1 mt-2">
            <div className="flex flex-col space-y-2">
              <Input
                id="apiKey"
                name="apiKey"
                type="password"
                required
                placeholder="输入您的API密钥"
                value={apiKey}
                onChange={(e) => setApiKey(e.target.value)}
              />
            </div>
          </div>
          <div className="flex flex-col space-y-2">
            <Button
              type="submit"
              disabled={isVerifying}
              className="group relative flex w-full justify-center"
            >
              {isVerifying ? '验证中...' : '验证'}
            </Button>
            <p className="text-xs text-muted-foreground">
            默认 api key 为 123456，远程部署请在登录后在“系统设置”内尽快修改
            </p>
          </div>
        </form>
      </div>
    </div>
  );
}
