/**
 * Componente de barra de progresso e log em tempo real da análise OCR.
 *
 * Uso:
 *   <OCRProgressBar
 *       identificador="hash_sha256_da_imagem"
 *       onConcluido={() => {}}
 *   />
 *
 * O componente se conecta ao endpoint SSE do backend e exibe:
 * - Barra de progresso animada
 * - Etapas com emojis
 * - Detalhes da etapa atual
 * - Status de erro (se houver)
 */
import { useEffect, useRef, useState } from "react";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "./ui/card";
import { Loader2, CheckCircle2, XCircle, FileText } from "lucide-react";

type EtapaOCR = {
  identificador: string;
  etapa: string;
  status: string; // "andamento" | "concluido" | "erro"
  detalhes: string;
  progresso: number;
  timestamp: string;
};

interface Props {
  identificador: string;
  onConcluido?: () => void;
  autoStart?: boolean;
}

export function OCRProgressBar({ identificador, onConcluido, autoStart = true }: Props) {
  const [etapas, setEtapas] = useState<EtapaOCR[]>([]);
  const [concluido, setConcluido] = useState(false);
  const [erro, setErro] = useState<string | null>(null);
  const [conectado, setConectado] = useState(false);
  const eventSourceRef = useRef<EventSource | null>(null);

  const progresso = etapas.length > 0 ? etapas[etapas.length - 1].progresso : 0;
  const ultimoStatus = etapas.length > 0 ? etapas[etapas.length - 1].status : "andamento";

  useEffect(() => {
    if (!identificador || !autoStart) return;

    const baseUrl = (import.meta as any).env.VITE_API_BASE_URL?.replace("/api/v1", "") || "http://localhost:8000";
    const url = `${baseUrl}/api/v1/ocr-progress/${identificador}`;

    const es = new EventSource(url);
    eventSourceRef.current = es;

    es.onopen = () => setConectado(true);

    es.addEventListener("ocr-progresso", (event) => {
      try {
        const data: EtapaOCR = JSON.parse(event.data);
        setEtapas((prev) => [...prev, data]);
      } catch (e) {
        console.error("Erro ao parsear SSE:", e);
      }
    });

    es.addEventListener("ocr-concluido", () => {
      setConcluido(true);
      setConectado(false);
      es.close();
      onConcluido?.();
    });

    es.onerror = () => {
      if (etapas.length === 0) {
        setErro("Não foi possível conectar ao serviço de OCR");
        setConectado(false);
      }
      es.close();
    };

    return () => {
      es.close();
      eventSourceRef.current = null;
    };
  }, [identificador]);

  if (!identificador) return null;

  return (
    <Card className="w-full">
      <CardHeader className="pb-3">
        <CardTitle className="flex items-center gap-2 text-base">
          <FileText className="h-4 w-4" />
          Análise do Comprovante
        </CardTitle>
        <CardDescription>
          {concluido
            ? "Análise concluída"
            : erro
              ? "Erro na análise"
              : conectado
                ? "Processando..."
                : "Aguardando..."}
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-3">
        {/* Barra de progresso */}
        <div className="w-full bg-secondary rounded-full h-2.5 overflow-hidden">
          <div
            className={`h-full rounded-full transition-all duration-500 ease-out ${
              erro
                ? "bg-destructive"
                : concluido
                  ? "bg-green-500"
                  : "bg-primary animate-pulse"
            }`}
            style={{ width: `${Math.round(progresso * 100)}%` }}
          />
        </div>

        {/* Porcentagem */}
        <p className="text-xs text-muted-foreground text-right">
          {Math.round(progresso * 100)}%
        </p>

        {/* Lista de etapas */}
        {etapas.length > 0 && (
          <ul className="space-y-1.5">
            {etapas.map((e, i) => (
              <li
                key={i}
                className={`flex items-start gap-2 text-sm ${
                  e.status === "erro"
                    ? "text-destructive"
                    : i === etapas.length - 1 && !concluido
                      ? "text-foreground font-medium"
                      : "text-muted-foreground"
                }`}
              >
                {e.status === "erro" ? (
                  <XCircle className="h-4 w-4 shrink-0 mt-0.5 text-destructive" />
                ) : i === etapas.length - 1 && !concluido ? (
                  <Loader2 className="h-4 w-4 shrink-0 mt-0.5 animate-spin text-primary" />
                ) : (
                  <CheckCircle2 className="h-4 w-4 shrink-0 mt-0.5 text-green-500" />
                )}
                <div className="min-w-0">
                  <span className="block truncate">{e.etapa}</span>
                  {e.detalhes && (
                    <span className="block text-xs opacity-70 truncate">
                      {e.detalhes}
                    </span>
                  )}
                </div>
              </li>
            ))}
          </ul>
        )}

        {/* Mensagem de erro */}
        {erro && (
          <div className="flex items-start gap-2 text-sm text-destructive">
            <XCircle className="h-4 w-4 shrink-0 mt-0.5" />
            <span>{erro}</span>
          </div>
        )}

        {/* Concluído */}
        {concluido && (
          <div className="flex items-center gap-2 text-sm text-green-600">
            <CheckCircle2 className="h-4 w-4 shrink-0" />
            <span>Comprovante analisado com sucesso!</span>
          </div>
        )}
      </CardContent>
    </Card>
  );
}