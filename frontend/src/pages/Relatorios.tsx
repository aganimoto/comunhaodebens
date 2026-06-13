import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { FileText, Download, Loader2, Plus, Calendar } from "lucide-react";
import { api } from "../lib/api";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "../components/ui/card";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "../components/ui/dialog";
import { useToast } from "../hooks/use-toast";
import { formatDateTime } from "../lib/utils";

type Relatorio = {
  nome: string;
  caminho: string;
  tamanho_bytes: number;
  modificado_em: string;
};

const MESES = [
  "Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho",
  "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro",
];

export function Relatorios() {
  const qc = useQueryClient();
  const { toast } = useToast();
  const [open, setOpen] = useState(false);
  const [ano, setAno] = useState(new Date().getFullYear());
  const [mes, setMes] = useState(new Date().getMonth() + 1);

  const { data, isLoading } = useQuery({
    queryKey: ["relatorios"],
    queryFn: async () => {
      const { data: res } = await api.get<Relatorio[]>("/relatorios");
      return res;
    },
  });

  const gerar = useMutation({
    mutationFn: async () => {
      const { data: res } = await api.post("/relatorios/gerar-sync", { ano, mes });
      return res;
    },
    onSuccess: (res) => {
      qc.invalidateQueries({ queryKey: ["relatorios"] });
      setOpen(false);
      toast({
        title: "Relatório gerado",
        description: `Arquivo: ${res?.arquivo ?? ""}`,
        variant: "success",
      });
    },
    onError: () =>
      toast({
        title: "Erro ao gerar",
        description: "Verifique se há contribuições no período.",
        variant: "destructive",
      }),
  });

  function download(nome: string) {
    window.open(
      `${import.meta.env.VITE_API_BASE_URL ?? "/api/v1"}/relatorios/${encodeURIComponent(nome)}/download`,
      "_blank"
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-3xl font-semibold tracking-tight">Relatórios PDF</h2>
          <p className="text-sm text-muted-foreground">
            Geração mensal automatizada via Celery Beat.
          </p>
        </div>
        <Dialog open={open} onOpenChange={setOpen}>
          <DialogTrigger asChild>
            <Button>
              <Plus className="h-4 w-4" />
              Gerar manualmente
            </Button>
          </DialogTrigger>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>Gerar relatório</DialogTitle>
              <DialogDescription>
                Será gerado um PDF A4 com todas as contribuições confirmadas
                no período selecionado.
              </DialogDescription>
            </DialogHeader>
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-1.5">
                <Label htmlFor="mes">Mês</Label>
                <select
                  id="mes"
                  className="flex h-10 w-full rounded-md border border-input bg-background px-3 text-sm"
                  value={mes}
                  onChange={(e) => setMes(Number(e.target.value))}
                >
                  {MESES.map((nome, i) => (
                    <option key={i + 1} value={i + 1}>
                      {nome}
                    </option>
                  ))}
                </select>
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="ano">Ano</Label>
                <Input
                  id="ano"
                  type="number"
                  min={2020}
                  max={new Date().getFullYear() + 1}
                  value={ano}
                  onChange={(e) => setAno(Number(e.target.value))}
                />
              </div>
            </div>
            <DialogFooter>
              <Button variant="outline" onClick={() => setOpen(false)}>
                Cancelar
              </Button>
              <Button onClick={() => gerar.mutate()} disabled={gerar.isPending}>
                {gerar.isPending ? (
                  <>
                    <Loader2 className="h-4 w-4 animate-spin" />
                    Gerando…
                  </>
                ) : (
                  <>
                    <FileText className="h-4 w-4" />
                    Gerar PDF
                  </>
                )}
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Histórico de relatórios</CardTitle>
          <CardDescription>
            {data?.length ?? 0} PDF(s) disponível(is)
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
              {data.map((r) => (
                <li
                  key={r.nome}
                  className="py-3 flex items-center justify-between gap-4 hover:bg-muted/30 -mx-2 px-2 rounded"
                >
                  <div className="flex items-center gap-3 min-w-0">
                    <div className="h-9 w-9 rounded-md bg-brand/10 text-brand flex items-center justify-center shrink-0">
                      <FileText className="h-4 w-4" />
                    </div>
                    <div className="min-w-0">
                      <p className="font-medium truncate font-mono text-sm">{r.nome}</p>
                      <p className="text-xs text-muted-foreground flex items-center gap-1">
                        <Calendar className="h-3 w-3" />
                        {formatDateTime(r.modificado_em)} ·{" "}
                        {(r.tamanho_bytes / 1024).toFixed(1)} KB
                      </p>
                    </div>
                  </div>
                  <Button size="sm" variant="outline" onClick={() => download(r.nome)}>
                    <Download className="h-4 w-4" />
                    Baixar
                  </Button>
                </li>
              ))}
            </ul>
          ) : (
            <div className="text-center py-12 text-muted-foreground text-sm">
              Nenhum relatório gerado ainda. Clique em <strong>Gerar manualmente</strong>.
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
