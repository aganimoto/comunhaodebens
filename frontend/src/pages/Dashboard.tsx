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

type ContribuicaoResumo = {
  id: string;
  protocolo: string;
  telefone: string;
  valor: number;
  data_pagamento: string;
  status: string;
  confianca: number;
};

type PendenciaResumo = {
  id: string;
  telefone: string | null;
  motivo: string;
  status: string;
  contribuicao_id: string | null;
  criado_em: string | null;
};

type Stats = {
  total_contribuicoes: number;
  contribuicoes_confirmadas: number;
  contribuicoes_revisao: number;
  contribuicoes_pendentes: number;
  contribuicoes_processando: number;
  pendencias_abertas: number;
  valor_total_confirmado: number;
  valor_hoje: number;
  valor_mes: number;
  ultimas_contribuicoes: ContribuicaoResumo[];
  pendencias_ocr: PendenciaResumo[];
};

const MOTIVO_LABEL: Record<string, string> = {
  ocr_baixa_confianca: "OCR com baixa confiança",
  ia_baixa_confianca: "IA com baixa confiança",
  erro_processamento: "Erro de processamento",
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

  const reprocessar = useMutation({
    mutationFn: (id: string) =>
      api.post(`/contribuicoes/${id}/reprocessar`),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["dashboard-stats"] });
      qc.invalidateQueries({ queryKey: ["pendencias"] });
      toast({
        title: "Reprocessamento iniciado",
        description: "Aguarde alguns instantes e atualize a tela.",
        variant: "success",
      });
    },
    onError: () =>
      toast({
        title: "Erro ao reprocessar",
        description: "Tente novamente em alguns instantes.",
        variant: "destructive",
      }),
  });

  const chartData = stats
    ? [
        { name: "Confirmadas", valor: stats.contribuicoes_confirmadas },
        { name: "Pendentes", valor: stats.contribuicoes_pendentes },
        { name: "Processando", valor: stats.contribuicoes_processando },
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

      {/* Linha 1: cards clássicos + Fase 6 (hoje/mês) */}
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

      {/* Linha 2: status (pílulas) */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
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
          title="Em revisão (legado)"
          value={stats?.contribuicoes_revisao ?? "—"}
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
                  key={c.id}
                  className="py-3 flex items-center justify-between gap-4"
                >
                  <div className="min-w-0 flex-1">
                    <p className="font-mono text-xs">{c.protocolo}</p>
                    <p className="text-sm text-muted-foreground">
                      {c.telefone} · {c.data_pagamento}
                    </p>
                  </div>
                  <div className="flex items-center gap-3">
                    <Badge
                      variant={
                        c.status === "confirmado"
                          ? "success"
                          : c.status === "pendente"
                          ? "warning"
                          : "secondary"
                      }
                    >
                      {c.status}
                    </Badge>
                    <span className="font-medium tabular-nums">
                      {formatBRL(c.valor)}
                    </span>
                    {c.status === "pendente" || c.status === "erro" ? (
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={() => reprocessar.mutate(c.id)}
                        disabled={reprocessar.isPending}
                      >
                        {reprocessar.isPending ? (
                          <Loader2 className="h-4 w-4 animate-spin" />
                        ) : (
                          <RefreshCw className="h-4 w-4" />
                        )}
                        Reprocessar
                      </Button>
                    ) : null}
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

      {/* Pendências OCR/IA com botão Reprocessar */}
      <Card>
        <CardHeader>
          <CardTitle>Pendências OCR / IA</CardTitle>
          <CardDescription>
            Comprovantes com falha de leitura — clique em "Reprocessar"
            para reexecutar o OCR/IA sem precisar reenviar pelo WhatsApp.
          </CardDescription>
        </CardHeader>
        <CardContent>
          {stats?.pendencias_ocr?.length ? (
            <ul className="divide-y">
              {stats.pendencias_ocr.map((p) => (
                <li
                  key={p.id}
                  className="py-3 flex items-center justify-between gap-4"
                >
                  <div className="min-w-0 flex-1">
                    <p className="font-medium truncate">
                      {MOTIVO_LABEL[p.motivo] ?? p.motivo}
                    </p>
                    <p className="text-xs text-muted-foreground font-mono">
                      {p.telefone ?? "—"} · {p.criado_em ?? "—"}
                    </p>
                  </div>
                  {p.contribuicao_id ? (
                    <Button
                      size="sm"
                      onClick={() => reprocessar.mutate(p.contribuicao_id!)}
                      disabled={reprocessar.isPending}
                    >
                      {reprocessar.isPending ? (
                        <Loader2 className="h-4 w-4 animate-spin" />
                      ) : (
                        <RefreshCw className="h-4 w-4" />
                      )}
                      Reprocessar
                    </Button>
                  ) : (
                    <Badge variant="warning">Sem contribuição</Badge>
                  )}
                </li>
              ))}
            </ul>
          ) : (
            <div className="text-center py-8 text-muted-foreground text-sm">
              🎉 Nenhuma pendência de OCR/IA. Tudo processado com sucesso!
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
