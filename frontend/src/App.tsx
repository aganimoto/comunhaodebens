import { BrowserRouter } from "react-router-dom";
import { AppRouter } from "./router";
import { ToasterHost } from "./components/ui/ToasterHost";
import { ToastProvider } from "./components/ui/toast-primitives";

export default function App() {
  return (
    <ToastProvider swipeDirection="right">
      <BrowserRouter
        future={{
          v7_startTransition: true,
          v7_relativeSplatPath: true,
        }}
      >
        <AppRouter />
      </BrowserRouter>
      <ToasterHost />
    </ToastProvider>
  );
}
