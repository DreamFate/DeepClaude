"use client";

import React, { createContext, useContext, useState, useEffect } from 'react';
import { checkAuth, verifyApiKey, logout as logoutApi } from './api';
import { useRouter, usePathname } from 'next/navigation';
import { Toaster } from '@/components/ui/sonner';

// 认证上下文类型
type AuthContextType = {
  isAuthenticated: boolean;
  isLoading: boolean;
  verifyKey: (key: string) => Promise<boolean>;
  logout: () => Promise<void>;
};

// 创建认证上下文
const AuthContext = createContext<AuthContextType | undefined>(undefined);

// 认证提供者组件
export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const router = useRouter();
  const pathname = usePathname();

  // 检查认证状态
  useEffect(() => {
    const checkAuthStatus = async () => {
      setIsLoading(true);
      try {
        const { authenticated } = await checkAuth();
        setIsAuthenticated(authenticated);
      } catch (error) {
        setIsAuthenticated(false);
      } finally {
        setIsLoading(false);
      }
    };

    checkAuthStatus();
  }, []);

  // 根据认证状态和路径进行重定向
  useEffect(() => {
    if (isLoading) return;

    // 如果在受保护路径但未认证，重定向到登录页面
    if (!isAuthenticated && !pathname.startsWith('/auth')) {
      router.push('/auth');
    }

    // 如果已认证但在登录页面，重定向到首页
    if (isAuthenticated && pathname.startsWith('/auth')) {
      router.push('/');
    }
  }, [isAuthenticated, isLoading, pathname, router]);

  // 验证密钥
  const verifyKey = async (key: string) => {
    try {
      const result = await verifyApiKey(key);
      setIsAuthenticated(result.success);

      // 如果验证成功，将密钥存储在 localStorage 中
      if (result.success) {
        localStorage.setItem('apiKey', key);
      }

      return result.success;
    } catch (error) {
      return false;
    }
  };

  // 登出
  const logout = async () => {
    try {
      // 调用后端API清除cookie
      await logoutApi();

      // 删除localStorage中的apiKey
      localStorage.removeItem('apiKey');

      // 更新认证状态
      setIsAuthenticated(false);

      // 重定向到登录页面
      router.push('/auth');
    } catch (error) {
      console.error('登出失败:', error);
    }
  };

  return (
    <AuthContext.Provider value={{ isAuthenticated, isLoading, verifyKey, logout }}>
      {children}
      <Toaster position="bottom-center" expand={true} richColors/>
    </AuthContext.Provider>
  );
}

// 使用认证上下文的钩子
export function useAuth() {
  const context = useContext(AuthContext);
  if (context === undefined) {
    throw new Error('useAuth 必须在 AuthProvider 内部使用');
  }
  return context;
}
