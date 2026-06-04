import { useQuery } from "@tanstack/react-query";
import { Bar, BarChart, ResponsiveContainer, Tooltip, XAxis, YAxis, CartesianGrid } from "recharts";
import { AlertTriangle, CheckCircle2, FileText, Wallet } from "lucide-react";
import { api } from "../lib/api";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "../components/ui/card";
import { Badge } from "../components/ui/badge";
import { formatBRL, formatDateTime } from "../components/ui/utils";

type Stats = {
  total_contribuicoes: number;
  contribuicoes_confirmadas: number;
  contribuicoes_revisao: number;
  pendencias_abertas: number;
  valor_total_confirmado: number;
};

export function Dashboard() {
  const { data: stats, isLoading } = useQuery({
    queryKey: ["dashboard-stats"],
    queryFn: async () => {
      const { data } = await api.get<Stats>("/admin/dashboard/stats");
      return data;
    },
  });

  const chartData = stats
    ? [
        { name: "Confirmadas", valor: stats.contribuicoes_confirmadas },
        { name: "Em revisão", valor: stats.contribuicoes_revisao },
        { name: "Pendências", valor: stats.pendencias_abertas },
      ]
    : [];

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-3xl font-semibold tracking-tight">Dashboard</h2>
        <p className="text-sm text-muted-foreground">
          Visão geral da operação financeira — atualizado em {formatDateTime(new Date().toISOString())}
        </p>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard
          title="Total contribuições"
          value={stats?.total_contribuicoes ?? "—"}
          icon={<FileText className="h-5 w-5" />}
          tone="default"
        />
        <StatCard
          title="Valor confirmado"
          value={formatBRL(stats?.valor_total_confirmado ?? 0)}
          icon={<Wallet className="h-5 w-5" />}
          tone="success"
        />
        <StatCard
          title="Em revisão"
          value={stats?.contribuicoes_revisao ?? "—"}
          icon={<CheckCircle2 className="h-5 w-5" />}
          tone="warning"
        />
        <StatCard
          title="Pendências abertas"
          value={stats?.pendencias_abertas ?? "—"}
          icon={<AlertTriangle className="h-5 w-5" />}
          tone="destructive"
        />
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Distribuição por status</CardTitle>
          <CardDescription>Contribuições e pendências no período atual.</CardDescription>
        </CardHeader>
        <CardContent className="h-72">
          {isLoading ? (
            <div className="h-full flex items-center justify-center text-muted-foreground">
              Carregando…
            </div>
          ) : (
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={chartData}>
                <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
                <XAxis dataKey="name" stroke="#6b7280" />
                <YAxis allowDecimals={false} stroke="#6b7280" />
                <Tooltip
                  contentStyle={{
                    borderRadius: 6,
                    border: "1px solid #e5e7eb",
                    boxShadow: "0 4px 12px rgb(0 0 0 / 0.05)",
                  }}
                />
                <Bar dataKey="valor" fill="#1e4d3a" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

function StatCard({
  title,
  value,
  icon,
  tone,
}: {
  title: string;
  value: string | number;
  icon: React.ReactNode;
  tone: "default" | "success" | "warning" | "destructive";
}) {
  const toneClass = {
    default: "bg-brand/10 text-brand",
    success: "bg-emerald-50 text-emerald-700",
    warning: "bg-amber-50 text-amber-700",
    destructive: "bg-rose-50 text-rose-700",
  }[tone];
  return (
    <Card>
      <CardContent className="p-5">
        <div className="flex items-start justify-between">
          <div>
            <p className="text-xs uppercase tracking-wide text-muted-foreground">{title}</p>
            <p className="mt-2 text-2xl font-semibold">{value}</p>
          </div>
          <div className={`p-2 rounded-md ${toneClass}`}>{icon}</div>
        </div>
      </CardContent>
    </Card>
  );
}
