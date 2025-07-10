import { clsx, type ClassValue } from "clsx"
import { twMerge } from "tailwind-merge"

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

export const ProviderFormat = {
  "openai": "OpenAI",
  "deepseek": "DeepSeek",
  "anthropic": "Anthropic",
  "google": "Google",
}

export const ModelFormat = {
  "openai": "OpenAI",
  "deepseek": "DeepSeek",
  "anthropic": "Anthropic",
}
