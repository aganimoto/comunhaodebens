import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Download,
  Search,
  Loader2,
  RefreshCw,
  Image as ImageIcon,
} from "lucide-react";
import { api } from "../lib/api";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "../components/ui/card";
import { Input } from "../components/ui/input";
import { Button } from "../components/ui/button";
import { Badge } from "../components/ui/badge";
import { Label } from "../components/ui/label";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "../components/ui/table";
import { Select, SelectItem } from "../components/ui/select";
import { formatBRL, formatDate } from "../lib/utils";
import { useToast } from "../hooks/use-toast";

type Item = {
  id: string;
  protocolo: string;
  telefone: string;
  valor: number;
  data_pagamento: string;
  status: string;
  confianca: number;
};

const STATUS_LABEL: Record<string, { label: string; variant: "default" | "warning" | "info" | "destructive" | "success" | "secondary" }> = {
  confirmado: { label: "Confirmado", variant: "success" },
  pendente: { label: "Pendente", variant: "warning" },
  processando: { label: "Processando", variant: "info" },
  revisao: { label: "Em revisão (legado)", variant: "warning" },
  duplicado: { label: "Duplicado", variant: "info" },
  erro: { label: "Erro", variant: "destructive" },
};

export function Contribuicoes() {
  const [status, setStatus] = useState<string>("all");
  const [busca, setBusca] = useState("");
  const qc = useQueryClient();
  const { toast } = useToast();

  const { data, isLoading } = useQuery({
    queryKey: ["contribuicoes", status],
    queryFn: async () => {
      const { data: res } = await api.get<{ items: Item[]; total: number }>(
        "/contribuicoes",
        { params: { limit: 100, ...(status !== "all" ? { status } : {}) } }
      );
      return res;
    },
  });

  const reprocessar = useMutation({
    mutationFn: (id: string) =>
      api.post(`/contribuicoes/${id}/reprocessar`),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["contribuicoes"] });
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

  function abrirComprovante(id: string) {
    // Pega o token atual do auth store (Zustand)
    // para autenticar o download do comprovante
    // (axios não consegue fazer download via Authorization em window.open)
    const tokenRaw = (api.defaults.headers.common as any)?.Authorization;
    const token = typeof tokenRaw === "string" ? tokenRaw.replace("Bearer ", "") : "";
    const baseURL = (api.defaults.baseURL || "").replace(/\/$/, "");
    const url = `${baseURL}/contribuicoes/${id}/comprovante`;
    fetch(url, { headers: { Authorization: `Bearer ${token}` } })
      .then((r) => {
        if (!r.ok) throw new Error("HTTP " + r.status);
        return r.blob();
      })
      .then((blob) => {
        const objectUrl = URL.createObjectURL(blob);
        window.open(objectUrl, "_blank", "noopener,noreferrer");
      })
      .catch(() =>
        toast({
          title: "Erro ao abrir comprovante",
          description: "Arquivo pode não estar disponível (pré-Fase 4?).",
          variant: "destructive",
        })
      );
  }

  const itens = data?.items.filter((c) =>
    busca ? c.protocolo.toLowerCase().includes(busca.toLowerCase()) : true
  );

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-3xl font-semibold tracking-tight">Contribuições</h2>
          <p className="text-sm text-muted-foreground">
            Total: {data?.total ?? 0} registros
          </p>
        </div>
        <Button variant="outline">
          <Download className="h-4 w-4" />
          Exportar CSV
        </Button>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Filtros</CardTitle>
          <CardDescription>Refine a lista por status ou protocolo.</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div className="space-y-1.5">
              <Label htmlFor="busca">Buscar protocolo</Label>
              <div className="relative">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                <Input
                  id="busca"
                  value={busca}
                  onChange={(e) => setBusca(e.target.value)}
                  placeholder="CDB-..."
                  className="pl-9"
                />
              </div>
            </div>
            <div className="space-y-1.5">
              <Label>Status</Label>
              <Select
                value={status}
                onChange={(e) => setStatus(e.target.value)}
              >
                <SelectItem value="all">Todos</SelectItem>
                <SelectItem value="confirmado">Confirmado</SelectItem>
                <SelectItem value="pendente">Pendente</SelectItem>
                <SelectItem value="processando">Processando</SelectItem>
                <SelectItem value="revisao">Em revisão (legado)</SelectItem>
                <SelectItem value="duplicado">Duplicado</SelectItem>
                <SelectItem value="erro">Erro</SelectItem>
              </Select>
            </div>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardContent className="p-0">
          {isLoading ? (
            <div className="flex items-center justify-center gap-2 py-12 text-muted-foreground">
              <Loader2 className="h-4 w-4 animate-spin" />
              Carregando…
            </div>
          ) : itens?.length ? (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Protocolo</TableHead>
                  <TableHead>Valor</TableHead>
                  <TableHead>Data</TableHead>
                  <TableHead>Telefone</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead className="text-right">Confiança</TableHead>
                  <TableHead className="text-right">Ações</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {itens.map((c) => {
                  const st = STATUS_LABEL[c.status] ?? { label: c.status, variant: "secondary" as const };
                  const podeReprocessar =
                    c.status === "pendente" ||
                    c.status === "revisao" ||
                    c.status === "erro";
                  return (
                    <TableRow key={c.id}>
                      <TableCell className="font-mono text-xs">{c.protocolo}</TableCell>
                      <TableCell className="font-medium">{formatBRL(c.valor)}</TableCell>
                      <TableCell>{formatDate(c.data_pagamento)}</TableCell>
                      <TableCell className="font-mono text-xs">{c.telefone}</TableCell>
                      <TableCell>
                        <Badge variant={st.variant}>{st.label}</Badge>
                      </TableCell>
                      <TableCell className="text-right tabular-nums">
                        {(c.confianca * 100).toFixed(0)}%
                      </TableCell>
                      <TableCell className="text-right">
                        <div className="flex items-center justify-end gap-1">
                          <Button
                            size="sm"
                            variant="ghost"
                            onClick={() => abrirComprovante(c.id)}
                            title="Ver comprovante original"
                          >
                            <ImageIcon className="h-4 w-4" />
                          </Button>
                          {podeReprocessar ? (
                            <Button
                              size="sm"
                              variant="outline"
                              onClick={() => reprocessar.mutate(c.id)}
                              disabled={reprocessar.isPending}
                              title="Reprocessar OCR/IA"
                            >
                              {reprocessar.isPending ? (
                                <Loader2 className="h-4 w-4 animate-spin" />
                              ) : (
                                <RefreshCw className="h-4 w-4" />
                              )}
                            </Button>
                          ) : null}
                        </div>
                      </TableCell>
                    </TableRow>
                  );
                })}
              </TableBody>
            </Table>
          ) : (
            <div className="text-center py-12 text-muted-foreground text-sm">
              Nenhuma contribuição encontrada com os filtros atuais.
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
