/**
 * Painel flutuante de debug no estilo "React DevTools" para o backend.
 *
 * Exibe logs detalhados do backend (OCR, IA, webhooks, banco) em tempo
 * real via SSE. Pode ser aberto/fechado com o botão "🐛 Debug" no canto
 * inferior direito da tela.
 *
 * Níveis de log com cores:
 * - debug:  cinza
 * - info:   azul
 * - warn:   amarelo
 * - error:  vermelho
 */
import { useEffect, useRef, useState } from "react";
import { X, Bug, Trash2, ChevronDown, ChevronUp } from "lucide-react";
import { Button } from "./ui/button";
import { Badge } from "./ui/badge";

type DebugEntry = {
  nivel: string;
  modulo: string;
  mensagem: string;
  detalhes: Record<string, unknown>;
  timestamp: string;
};

const NIVEL_CORES: Record<string, string> = {
  debug: "text-gray-400",
  info: "text-blue-400",
  warn: "text-amber-400",
  error: "text-red-400",
};

const NIVEL_BADGE: Record<string, string> = {
  debug: "bg-gray-500",
  info: "bg-blue-500",
  warn: "bg-amber-500",
  error: "bg-red-500",
};

export function DebugPanel() {
  const [aberto, setAberto] = useState(false);
  const [logs, setLogs] = useState<DebugEntry[]>([]);
  const [autoScroll, setAutoScroll] = useState(true);
  const [filtro, setFiltro] = useState<string>("todos");
  const logEndRef = useRef<HTMLDivElement>(null);
  const eventSourceRef = useRef<EventSource | null>(null);

  useEffect(() => {
    if (!aberto) {
      if (eventSourceRef.current) {
        eventSourceRef.current.close();
        eventSourceRef.current = null;
      }
      return;
    }

    const baseUrl = (import.meta as any).env.VITE_API_BASE_URL?.replace("/api/v1", "") || "http://localhost:8000";
    const url = `${baseUrl}/api/v1/debug/stream`;

    const es = new EventSource(url);
    eventSourceRef.current = es;

    es.addEventListener("debug-log", (event) => {
      try {
        const data: DebugEntry = JSON.parse(event.data);
        setLogs((prev) => [...prev.slice(-499), data]);
      } catch (e) {
        console.error("Erro ao parsear debug SSE:", e);
      }
    });

    es.onerror = () => {
      // Reconexão automática do EventSource
    };

    return () => {
      es.close();
      eventSourceRef.current = null;
    };
  }, [aberto]);

  // Rolagem automática
  useEffect(() => {
    if (autoScroll && logEndRef.current) {
      logEndRef.current.scrollIntoView({ behavior: "smooth" });
    }
  }, [logs, autoScroll]);

  const logsFiltrados = filtro === "todos"
    ? logs
    : logs.filter((l) => l.nivel === filtro);

  const contarPorNivel = (nivel: string) =>
    logs.filter((l) => l.nivel === nivel).length;

  function limparLogs() {
    setLogs([]);
    // Também limpa no backend
    fetch(`${(import.meta as any).env.VITE_API_BASE_URL?.replace("/api/v1", "") || "http://localhost:8000"}/api/v1/debug/clear`, {
      method: "POST",
    }).catch(() => {});
  }

  function formatarTimestamp(ts: string) {
    const d = new Date(ts);
    return d.toLocaleTimeString("pt-BR", { hour12: false });
  }

  return (
    <>
      {/* Botão flutuante para abrir/fechar */}
      <button
        onClick={() => setAberto(!aberto)}
        className="fixed bottom-4 right-4 z-50 flex items-center gap-1.5 px-3 py-2 rounded-full bg-foreground text-background shadow-lg hover:opacity-90 transition-opacity text-sm font-medium"
        title="Abrir painel de debug"
      >
        <Bug className="h-4 w-4" />
        Debug
        {logs.filter((l) => l.nivel === "error").length > 0 && (
          <Badge variant="destructive" className="ml-1 text-xs h-5 px-1.5">
            {logs.filter((l) => l.nivel === "error").length}
          </Badge>
        )}
      </button>

      {/* Painel */}
      {aberto && (
        <div className="fixed bottom-16 right-4 z-50 w-[600px] max-w-[calc(100vw-2rem)] max-h-[70vh] bg-black/95 text-white rounded-lg shadow-2xl border border-gray-700 flex flex-col overflow-hidden">
          {/* Header */}
          <div className="flex items-center justify-between px-3 py-2 border-b border-gray-700 bg-gray-900">
            <div className="flex items-center gap-2">
              <Bug className="h-4 w-4 text-green-400" />
              <span className="text-sm font-semibold">Debug Backend</span>
              <span className="text-xs text-gray-500">({logs.length} eventos)</span>
            </div>
            <div className="flex items-center gap-1">
              <Button
                size="sm"
                variant="ghost"
                className="h-7 text-xs text-gray-400 hover:text-white"
                onClick={limparLogs}
                title="Limpar logs"
              >
                <Trash2 className="h-3 w-3" />
              </Button>
              <Button
                size="sm"
                variant="ghost"
                className="h-7 text-xs text-gray-400 hover:text-white"
                onClick={() => setAutoScroll(!autoScroll)}
                title={autoScroll ? "Auto-scroll ativado" : "Auto-scroll desativado"}
              >
                {autoScroll ? <ChevronDown className="h-3 w-3" /> : <ChevronUp className="h-3 w-3" />}
              </Button>
              <Button
                size="sm"
                variant="ghost"
                className="h-7 text-xs text-gray-400 hover:text-white"
                onClick={() => setAberto(false)}
              >
                <X className="h-3 w-3" />
              </Button>
            </div>
          </div>

          {/* Filtros */}
          <div className="flex items-center gap-1.5 px-3 py-1.5 border-b border-gray-800 bg-gray-900/50">
            {["todos", "error", "warn", "info", "debug"].map((n) => (
              <button
                key={n}
                onClick={() => setFiltro(n)}
                className={`px-2 py-0.5 rounded text-xs font-medium transition-colors ${
                  filtro === n
                    ? "bg-gray-600 text-white"
                    : "text-gray-400 hover:text-white hover:bg-gray-800"
                }`}
              >
                {n}
                {contarPorNivel(n) > 0 && (
                  <span className="ml-1 text-[10px] opacity-60">({contarPorNivel(n)})</span>
                )}
              </button>
            ))}
          </div>

          {/* Lista de logs */}
          <div className="flex-1 overflow-y-auto p-2 font-mono text-xs space-y-0.5">
            {logsFiltrados.length === 0 ? (
              <div className="text-gray-600 text-center py-8 text-sm">
                Nenhum log disponível.
                <br />
                Envie uma imagem pelo WhatsApp para ver logs em tempo real.
              </div>
            ) : (
              logsFiltrados.map((log, i) => (
                <div
                  key={i}
                  className="flex items-start gap-2 p-1 rounded hover:bg-white/5"
                >
                  {/* Timestamp */}
                  <span className="text-gray-600 shrink-0 w-14 text-right">
                    {formatarTimestamp(log.timestamp)}
                  </span>

                  {/* Nível */}
                  <span
                    className={`inline-block px-1 rounded text-[10px] font-bold uppercase leading-4 shrink-0 ${NIVEL_BADGE[log.nivel] || "bg-gray-500"} text-white`}
                    style={{ minWidth: 36, textAlign: "center" }}
                  >
                    {log.nivel}
                  </span>

                  {/* Módulo */}
                  <span className="text-cyan-400 shrink-0 w-20 truncate">
                    {log.modulo}
                  </span>

                  {/* Mensagem */}
                  <span className={`${NIVEL_CORES[log.nivel] || "text-gray-300"} break-words min-w-0 flex-1`}>
                    {log.mensagem}
                  </span>

                  {/* Detalhes (tooltip expandido) */}
                  {Object.keys(log.detalhes).length > 0 && (
                    <span
                      className="text-gray-600 cursor-help shrink-0"
                      title={JSON.stringify(log.detalhes, null, 2)}
                    >
                      {`{${Object.keys(log.detalhes).length}}`}
                    </span>
                  )}
                </div>
              ))
            )}
            <div ref={logEndRef} />
          </div>
        </div>
      )}
    </>
  );
}