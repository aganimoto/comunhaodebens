import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  CheckCircle2,
  AlertTriangle,
  Loader2,
  RefreshCw,
  UserPlus,
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
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from "../components/ui/dialog";
import { Input } from "../components/ui/input";
import { Select, SelectItem } from "../components/ui/select";
import { useToast } from "../hooks/use-toast";

type Pendencia = {
  id: string;
  telefone: string;
  motivo: string;
  status: string;
  contribuicao_id?: string | null;
  observacao?: string;
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

/** Extrai o nome sugerido da observação (ex: "Nome sugerido: Tominaga do Shalom") */
function extrairNomeSugerido(obs: string): string {
  const match = obs.match(/^Nome sugerido:\s*(.+)/);
  return match ? match[1].trim() : "";
}

const CATEGORIAS = [
  { value: "comunidade_de_vida", label: "Comunidade de Vida" },
  { value: "comunidade_de_alianca", label: "Comunidade de Aliança" },
  { value: "obra", label: "Obra" },
  { value: "benfeitor", label: "Benfeitor" },
];

export function Pendencias() {
  const qc = useQueryClient();
  const { toast } = useToast();

  // Estado do modal de cadastro
  const [modalAberto, setModalAberto] = useState(false);
  const [pendenciaAtual, setPendenciaAtual] = useState<Pendencia | null>(null);
  const [nomeCadastro, setNomeCadastro] = useState("");
  const [categoriaCadastro, setCategoriaCadastro] = useState("benfeitor");

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

  const cadastrarMembro = useMutation({
    mutationFn: (data: { pendencia_id: string; nome: string; categoria: string }) =>
      api.post("/pendencias/cadastrar-membro", data),
    onSuccess: (res) => {
      qc.invalidateQueries({ queryKey: ["pendencias"] });
      setModalAberto(false);
      toast({
        title: "Membro cadastrado",
        description: `${res.data.nome} · ${res.data.telefone}`,
        variant: "success",
      });
    },
    onError: (err: any) => {
      const msg = err?.response?.data?.detail || "Erro ao cadastrar membro";
      toast({
        title: "Erro",
        description: msg,
        variant: "destructive",
      });
    },
  });

  function abrirCadastro(p: Pendencia) {
    const nomeSugerido = extrairNomeSugerido(p.observacao || "");
    setPendenciaAtual(p);
    setNomeCadastro(nomeSugerido);
    setCategoriaCadastro("benfeitor");
    setModalAberto(true);
  }

  function confirmarCadastro() {
    if (!pendenciaAtual || !nomeCadastro.trim()) return;
    cadastrarMembro.mutate({
      pendencia_id: pendenciaAtual.id,
      nome: nomeCadastro.trim(),
      categoria: categoriaCadastro,
    });
  }

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
                const nomeSugerido = extrairNomeSugerido(p.observacao || "");
                const ehNaoCadastrado = p.motivo === "telefone_nao_cadastrado";
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
                    {nomeSugerido && (
                      <p className="text-xs text-blue-500 mt-0.5">
                        💡 Sugestão: {nomeSugerido}
                      </p>
                    )}
                  </div>
                  {p.status === "aberto" ? (
                    <div className="flex items-center gap-2">
                      {ehNaoCadastrado && (
                        <Button
                          size="sm"
                          variant="default"
                          onClick={() => abrirCadastro(p)}
                          title="Cadastrar membro e resolver pendência"
                        >
                          <UserPlus className="h-4 w-4" />
                          Cadastrar
                        </Button>
                      )}
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
                        variant={podeReprocessar || ehNaoCadastrado ? "ghost" : "default"}
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

      {/* Modal de cadastro de membro */}
      <Dialog open={modalAberto} onOpenChange={setModalAberto}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Cadastrar novo membro</DialogTitle>
            <DialogDescription>
              Telefone: <strong>{pendenciaAtual?.telefone}</strong>
              {pendenciaAtual?.observacao && extrairNomeSugerido(pendenciaAtual.observacao) && (
                <span className="block text-blue-500 mt-1">
                  💡 Nome sugerido pelo WhatsApp: {extrairNomeSugerido(pendenciaAtual.observacao)}
                </span>
              )}
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-4 py-2">
            <div>
              <label className="text-sm font-medium">Nome completo</label>
              <Input
                value={nomeCadastro}
                onChange={(e) => setNomeCadastro(e.target.value)}
                placeholder="Ex.: João Silva"
              />
            </div>
            <div>
              <label className="text-sm font-medium">Categoria</label>
              <Select
                value={categoriaCadastro}
                onChange={(e) => setCategoriaCadastro(e.target.value)}
              >
                {CATEGORIAS.map((cat) => (
                  <SelectItem key={cat.value} value={cat.value}>
                    {cat.label}
                  </SelectItem>
                ))}
              </Select>
            </div>
          </div>

          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => setModalAberto(false)}
            >
              Cancelar
            </Button>
            <Button
              onClick={confirmarCadastro}
              disabled={!nomeCadastro.trim() || cadastrarMembro.isPending}
            >
              {cadastrarMembro.isPending ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <UserPlus className="h-4 w-4" />
              )}
              Cadastrar e resolver
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}