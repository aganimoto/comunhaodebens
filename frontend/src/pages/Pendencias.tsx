import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  CheckCircle2,
  AlertTriangle,
  Loader2,
  RefreshCw,
} from "lucide-react";
import { api } from "../lib/api";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "../components/ui/card";
import { Button } from "../components/ui/button";
import { Badge } from "../components/ui/badge";
import { useToast } from "../hooks/use-toast";

type Pendencia = {
  id: string;
  telefone: string;
  motivo: string;
  status: string;
  contribuicao_id?: string | null;
};

const MOTIVO_LABEL: Record<string, string> = {
  telefone_nao_cadastrado: "Telefone não cadastrado",
  ocr_baixa_confianca: "OCR com baixa confiança",
  ia_baixa_confianca: "IA com baixa confiança",
  comprovante_duplicado: "Comprovante duplicado",
  valor_nao_identificado: "Valor não identificado",
  erro_processamento: "Erro de processamento",
};

const MOTIVO_REPROCESSAVEL: Record<string, boolean> = {
  ocr_baixa_confianca: true,
  ia_baixa_confianca: true,
  erro_processamento: true,
};

export function Pendencias() {
  const qc = useQueryClient();
  const { toast } = useToast();

  const { data, isLoading } = useQuery({
    queryKey: ["pendencias"],
    queryFn: async () => {
      const { data: res } = await api.get<Pendencia[]>("/pendencias");
      return res;
    },
  });

  const resolver = useMutation({
    mutationFn: (id: string) =>
      api.patch(`/pendencias/${id}/resolver`, { observacao: "Resolvido via painel" }),
    onSuccess: (_d, id) => {
      qc.invalidateQueries({ queryKey: ["pendencias"] });
      toast({
        title: "Pendência resolvida",
        description: `ID: ${id.slice(0, 8)}…`,
        variant: "success",
      });
    },
    onError: () =>
      toast({
        title: "Erro ao resolver",
        description: "Tente novamente em alguns instantes.",
        variant: "destructive",
      }),
  });

  const reprocessar = useMutation({
    mutationFn: (contribuicaoId: string) =>
      api.post(`/contribuicoes/${contribuicaoId}/reprocessar`),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["pendencias"] });
      qc.invalidateQueries({ queryKey: ["dashboard-stats"] });
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

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-3xl font-semibold tracking-tight">Pendências</h2>
        <p className="text-sm text-muted-foreground">
          {data?.length ?? 0} pendência(s) registrada(s)
        </p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Lista de pendências</CardTitle>
          <CardDescription>
            Itens que exigem ação da equipe financeira.
          </CardDescription>
        </CardHeader>
        <CardContent>
          {isLoading ? (
            <div className="flex items-center justify-center gap-2 py-12 text-muted-foreground">
              <Loader2 className="h-4 w-4 animate-spin" />
              Carregando…
            </div>
          ) : data && data.length > 0 ? (
            <ul className="divide-y">
              {data.map((p) => {
                const podeReprocessar =
                  !!MOTIVO_REPROCESSAVEL[p.motivo] && !!p.contribuicao_id;
                return (
                <li key={p.id} className="py-3 flex items-center justify-between gap-4">
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-2">
                      <AlertTriangle className="h-4 w-4 text-amber-500 shrink-0" />
                      <p className="font-medium truncate">
                        {MOTIVO_LABEL[p.motivo] ?? p.motivo}
                      </p>
                    </div>
                    <p className="text-xs text-muted-foreground mt-1 font-mono">
                      {p.telefone ?? "—"} · {p.status}
                    </p>
                  </div>
                  {p.status === "aberto" ? (
                    <div className="flex items-center gap-2">
                      {podeReprocessar ? (
                        <Button
                          size="sm"
                          variant="outline"
                          onClick={() => reprocessar.mutate(p.contribuicao_id!)}
                          disabled={reprocessar.isPending}
                          title="Reexecutar OCR/IA a partir da imagem original"
                        >
                          {reprocessar.isPending ? (
                            <Loader2 className="h-4 w-4 animate-spin" />
                          ) : (
                            <RefreshCw className="h-4 w-4" />
                          )}
                          Reprocessar
                        </Button>
                      ) : null}
                      <Button
                        size="sm"
                        variant={podeReprocessar ? "ghost" : "default"}
                        onClick={() => resolver.mutate(p.id)}
                        disabled={resolver.isPending}
                        title="Marcar como resolvida manualmente"
                      >
                        <CheckCircle2 className="h-4 w-4" />
                        Resolver
                      </Button>
                    </div>
                  ) : (
                    <Badge variant="success">Resolvida</Badge>
                  )}
                </li>
                );
              })}
            </ul>
          ) : (
            <div className="text-center py-12 text-muted-foreground text-sm">
              🎉 Nenhuma pendência aberta. Operação em dia!
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
