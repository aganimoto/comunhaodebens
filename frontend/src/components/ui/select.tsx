// Select minimalista baseado em <select> nativo estilizado.
// (Implementação leve para evitar mais uma dependência Radix.)
import * as React from "react";
import { cn } from "./utils";

export type SelectProps = React.SelectHTMLAttributes<HTMLSelectElement>;

export const Select = React.forwardRef<HTMLSelectElement, SelectProps>(
  ({ className, children, ...props }, ref) => (
    <select
      ref={ref}
      className={cn(
        "flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50",
        className
      )}
      {...props}
    >
      {children}
    </select>
  )
);
Select.displayName = "Select";

// Wrappers para simular a API do shadcn (SelectTrigger/Value/Content/Item).
export function SelectTrigger({ children }: { children: React.ReactNode }) {
  return <div className="contents">{children}</div>;
}
export function SelectValue({ placeholder }: { placeholder?: string }) {
  return <option value="" disabled>{placeholder}</option>;
}
export function SelectContent({ children }: { children: React.ReactNode }) {
  return <>{children}</>;
}
export function SelectItem({ value, children }: { value: string; children: React.ReactNode }) {
  return <option value={value}>{children}</option>;
}
