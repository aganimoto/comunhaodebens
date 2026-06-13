import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Bar,
  BarChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
  CartesianGrid,
} from "recharts";
import {
  AlertTriangle,
  CheckCircle2,
  FileText,
  Wallet,
  TrendingUp,
  RefreshCw,
  Loader2,
} from "lucide-react";
import { api } from "../lib/api";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "../components/ui/card";
import { Badge } from "../components/ui/badge";
import { Button } from "../components/ui/button";
import { formatBRL, formatDateTime } from "../components/ui/utils";
import { useToast } from "../hooks/use-toast";
import { OCRProgressBar } from "../components/OCRProgressBar";

type Stats = {
  total_contribuicoes: number;
  contribuicoes_confirmadas: number;
  contribuicoes_pendentes: number;
  pendencias_abertas: number;
  valor_total_confirmado: number;
  valor_hoje: number;
  valor_mes: number;
  ultimas_contribuicoes: ContribuicaoResumo[];
};

type ContribuicaoResumo = {
  protocolo: string;
  data: string;
  nome: string;
  valor: string;
  status: string;
  confianca: string;
};

export function Dashboard() {
  const qc = useQueryClient();
  const { toast } = useToast();

  const { data: stats, isLoading } = useQuery({
    queryKey: ["dashboard-stats"],
    queryFn: async () => {
      const { data } = await api.get<Stats>("/admin/dashboard/stats");
      return data;
    },
  });

  const [ocrHashes, setOcrHashes] = useState<string[]>([]);

  const reprocessar = useMutation({
    mutationFn: (protocolo: string) =>
      api.post(`/contribuicoes/${protocolo}/reprocessar`),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["dashboard-stats"] });
      qc.invalidateQueries({ queryKey: ["pendencias"] });
      toast({
        title: "Reprocessamento solicitado",
        description: "Reenvie o comprovante pelo WhatsApp para reprocessar.",
        variant: "success",
      });
    },
    onError: () =>
      toast({
        title: "Erro ao reprocessar",
        description: "Reprocessamento manual não disponível. Reenvie pelo WhatsApp.",
        variant: "destructive",
      }),
  });

  // Sincroniza hashes das contribuições em processamento
  useEffect(() => {
    if (stats) {
      setOcrHashes([]);
    }
  }, [stats]);

  const chartData = stats
    ? [
        { name: "Confirmadas", valor: stats.contribuicoes_confirmadas },
        { name: "Pendentes", valor: stats.contribuicoes_pendentes },
        { name: "Pendências", valor: stats.pendencias_abertas },
      ]
    : [];

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-3xl font-semibold tracking-tight">Dashboard</h2>
        <p className="text-sm text-muted-foreground">
          Visão geral da operação financeira — atualizado em{" "}
          {formatDateTime(new Date().toISOString())}
        </p>
      </div>

      {/* Linha 1: cards clássicos */}
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
          title="Arrecadado hoje"
          value={formatBRL(stats?.valor_hoje ?? 0)}
          icon={<TrendingUp className="h-5 w-5" />}
          tone="default"
        />
        <StatCard
          title="Arrecadado no mês"
          value={formatBRL(stats?.valor_mes ?? 0)}
          icon={<TrendingUp className="h-5 w-5" />}
          tone="default"
        />
      </div>

      {/* Linha 2: status */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <StatCard
          title="Confirmadas"
          value={stats?.contribuicoes_confirmadas ?? "—"}
          icon={<CheckCircle2 className="h-5 w-5" />}
          tone="success"
        />
        <StatCard
          title="Pendentes"
          value={stats?.contribuicoes_pendentes ?? "—"}
          icon={<AlertTriangle className="h-5 w-5" />}
          tone="warning"
        />
        <StatCard
          title="Pendências abertas"
          value={stats?.pendencias_abertas ?? "—"}
          icon={<AlertTriangle className="h-5 w-5" />}
          tone="destructive"
        />
      </div>

      {/* Gráfico */}
      <Card>
        <CardHeader>
          <CardTitle>Distribuição por status</CardTitle>
          <CardDescription>
            Contribuições e pendências no período atual.
          </CardDescription>
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

      {/* Últimas contribuições */}
      <Card>
        <CardHeader>
          <CardTitle>Últimas contribuições</CardTitle>
          <CardDescription>5 mais recentes processadas.</CardDescription>
        </CardHeader>
        <CardContent>
          {stats?.ultimas_contribuicoes?.length ? (
            <ul className="divide-y">
              {stats.ultimas_contribuicoes.map((c) => (
                <li
                  key={c.protocolo}
                  className="py-3 flex items-center justify-between gap-4"
                >
                  <div className="min-w-0 flex-1">
                    <p className="font-mono text-xs">{c.protocolo}</p>
                    <p className="text-sm text-muted-foreground">
                      {c.nome} · {c.data}
                    </p>
                  </div>
                  <div className="flex items-center gap-3">
                    <Badge
                      variant={
                        c.status === "CONFIRMADO"
                          ? "success"
                          : c.status === "PENDENTE"
                          ? "warning"
                          : "secondary"
                      }
                    >
                      {c.status}
                    </Badge>
                    <span className="font-medium tabular-nums">
                      {c.valor}
                    </span>
                  </div>
                </li>
              ))}
            </ul>
          ) : (
            <div className="text-center py-8 text-muted-foreground text-sm">
              Nenhuma contribuição registrada ainda.
            </div>
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
            <p className="text-xs uppercase tracking-wide text-muted-foreground">
              {title}
            </p>
            <p className="mt-2 text-2xl font-semibold">{value}</p>
          </div>
          <div className={`p-2 rounded-md ${toneClass}`}>{icon}</div>
        </div>
      </CardContent>
    </Card>
  );
}