import { Navigate, Route, Routes } from "react-router-dom";
import { Layout } from "./components/layout/Layout";
import { useAuthStore } from "./stores/auth.store";
import { Contribuicoes } from "./pages/Contribuicoes";
import { Dashboard } from "./pages/Dashboard";
import { Login } from "./pages/Login";
import { Membros } from "./pages/Membros";
import { Pendencias } from "./pages/Pendencias";
import { Relatorios } from "./pages/Relatorios";
import { WhatsAppConnect } from "./pages/WhatsAppConnect";

function PrivateRoute({ children }: { children: React.ReactNode }) {
  const token = useAuthStore((s) => s.token);
  if (!token) return <Navigate to="/login" replace />;
  return <>{children}</>;
}

export function AppRouter() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route
        path="/"
        element={
          <PrivateRoute>
            <Layout />
          </PrivateRoute>
        }
      >
        <Route index element={<Dashboard />} />
        <Route path="contribuicoes" element={<Contribuicoes />} />
        <Route path="pendencias" element={<Pendencias />} />
        <Route path="membros" element={<Membros />} />
        <Route path="relatorios" element={<Relatorios />} />
        <Route path="whatsapp" element={<WhatsAppConnect />} />
      </Route>
    </Routes>
  );
}
