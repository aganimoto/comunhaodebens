// Hook simples de toast (sem dependências extras além do Radix Toast).
import { useCallback, useState } from "react";

export type ToastVariant = "default" | "destructive" | "success";

export interface ToastItem {
  id: string;
  title?: string;
  description?: string;
  variant?: ToastVariant;
  duration?: number;
}

let counter = 0;

export function useToast() {
  const [toasts, setToasts] = useState<ToastItem[]>([]);

  const dismiss = useCallback((id: string) => {
    setToasts((curr) => curr.filter((t) => t.id !== id));
  }, []);

  const toast = useCallback(
    (item: Omit<ToastItem, "id">) => {
      const id = `toast-${++counter}`;
      const next: ToastItem = { id, duration: 4500, ...item };
      setToasts((curr) => [...curr, next]);
      setTimeout(() => dismiss(id), next.duration);
      return id;
    },
    [dismiss]
  );

  return { toasts, toast, dismiss };
}
