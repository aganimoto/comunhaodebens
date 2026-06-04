import { useToast } from "../../hooks/use-toast";
import { Toast, ToastClose, ToastDescription, ToastTitle, ToastViewport } from "./toast-primitives";

/** Renderiza a fila de toasts ativos. */
export function ToasterHost() {
  const { toasts, dismiss } = useToast();
  return (
    <>
      {toasts.map(({ id, title, description, variant }: any) => (
        <Toast
          key={id}
          variant={variant ?? "default"}
          onOpenChange={(open: boolean) => {
            if (!open) dismiss(id);
          }}
        >
          <div className="grid gap-1">
            {title && <ToastTitle>{title}</ToastTitle>}
            {description && <ToastDescription>{description}</ToastDescription>}
          </div>
          <ToastClose />
        </Toast>
      ))}
      <ToastViewport />
    </>
  );
}
