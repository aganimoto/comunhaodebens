import { Outlet, NavLink } from "react-router-dom";
import { LogOut, BarChart3, FileText, AlertTriangle, Users, Folder, MessageCircle } from "lucide-react";
import { cn } from "../ui/utils";
import { Button } from "../ui/button";
import { useAuthStore } from "../../stores/auth.store";

const links = [
  { to: "/", label: "Dashboard", icon: BarChart3 },
  { to: "/contribuicoes", label: "Contribuições", icon: FileText },
  { to: "/pendencias", label: "Pendências", icon: AlertTriangle },
  { to: "/membros", label: "Membros", icon: Users },
  { to: "/relatorios", label: "Relatórios", icon: Folder },
  { to: "/whatsapp", label: "WhatsApp", icon: MessageCircle },
];

export function Layout() {
  const logout = useAuthStore((s) => s.logout);

  return (
    <div className="flex min-h-screen bg-muted/30">
      <aside className="w-60 bg-brand text-white flex flex-col">
        <div className="px-5 py-5 border-b border-white/10">
          <h1 className="text-lg font-semibold tracking-tight">CDB Shalom</h1>
          <p className="text-xs text-white/60 mt-0.5">Comunhão de Bens</p>
        </div>
        <nav className="flex-1 px-3 py-4 space-y-1">
          {links.map(({ to, label, icon: Icon }) => (
            <NavLink
              key={to}
              to={to}
              end={to === "/"}
              className={({ isActive }) =>
                cn(
                  "flex items-center gap-2 px-3 py-2 rounded-md text-sm transition-colors",
                  isActive
                    ? "bg-white/15 text-white"
                    : "text-white/80 hover:bg-white/10 hover:text-white"
                )
              }
            >
              <Icon className="h-4 w-4" />
              {label}
            </NavLink>
          ))}
        </nav>
        <div className="p-3 border-t border-white/10">
          <Button
            variant="ghost"
            className="w-full justify-start text-white/80 hover:text-white hover:bg-white/10"
            onClick={logout}
          >
            <LogOut className="h-4 w-4" />
            Sair
          </Button>
        </div>
      </aside>
      <main className="flex-1 p-8 overflow-y-auto">
        <Outlet />
      </main>
    </div>
  );
}
