import { useEffect, useRef, useState } from "react";
import {
  MessageCircle,
  RefreshCw,
  Wifi,
  WifiOff,
  Loader2,
  QrCode,
  ScrollText,
  Table2,
  ExternalLink,
} from "lucide-react";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "../components/ui/card";
import { Badge } from "../components/ui/badge";
import { Button } from "../components/ui/button";
import { api } from "../lib/api";
import { cn } from "../components/ui/utils";

// ── Types ──────────────────────────────────────────────────────────
type WhatsAppStatus = "connected" | "qr_pending" | "disconnected";
type Tab = "qrcode" | "log" | "sheets";

interface QrResponse {
  status: WhatsAppStatus;
  qr: string | null;
}

interface LogEntry {
  id: string;
  telefone: string;
  timestamp: string;
  tipo: string;
  status: string;
  media_path: string | null;
}

interface SheetsResponse {
  available: boolean;
  spreadsheet_url: string | null;
  sheets: Record<string, string[][]>;
}

const POLL_INTERVAL_MS = 3000;

const statusLabel: Record<WhatsAppStatus, string> = {
  connected: "Conectado",
  qr_pending: "Aguardando escaneamento",
  disconnected: "Desconectado",
};

const statusVariant: Record<
  WhatsAppStatus,
  "success" | "warning" | "destructive"
> = {
  connected: "success",
  qr_pending: "warning",
  disconnected: "destructive",
};

const logStatusVariant: Record<string, "success" | "warning" | "destructive" | "info"> = {
  processando: "info",
  pendencia: "warning",
  duplicado: "warning",
  concluido: "success",
  recebida: "info",
};

// ── Component ──────────────────────────────────────────────────────
export function WhatsAppConnect() {
  const [tab, setTab] = useState<Tab>("qrcode");
  const [status, setStatus] = useState<WhatsAppStatus>("disconnected");
  const [qrDataUrl, setQrDataUrl] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [reconnecting, setReconnecting] = useState(false);

  // Log
  const [logs, setLogs] = useState<LogEntry[]>([]);
  const [logsLoading, setLogsLoading] = useState(false);

  // Sheets
  const [sheets, setSheets] = useState<SheetsResponse | null>(null);
  const [sheetsLoading, setSheetsLoading] = useState(false);
  const [activeSheet, setActiveSheet] = useState("Membros");

  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // ── Fetchers ─────────────────────────────────────────────────────
  async function fetchStatus() {
    try {
      const { data } = await api.get<QrResponse>("/whatsapp/status");
      setStatus(data.status);
    } catch {
      setStatus("disconnected");
    }
  }

  async function fetchQr() {
    try {
      const { data } = await api.get<QrResponse>("/whatsapp/qr");
      setStatus(data.status);
      setQrDataUrl(data.qr);
    } catch {
      /* manter estado anterior */
    }
  }

  async function fetchLogs() {
    setLogsLoading(true);
    try {
      const { data } = await api.get<LogEntry[]>("/whatsapp/log");
      setLogs(data);
    } catch {
      setLogs([]);
    } finally {
      setLogsLoading(false);
    }
  }

  async function fetchSheets() {
    setSheetsLoading(true);
    try {
      const { data } = await api.get<SheetsResponse>("/whatsapp/sheets");
      setSheets(data);
    } catch {
      setSheets(null);
    } finally {
      setSheetsLoading(false);
    }
  }

  async function handleReconnect() {
    setReconnecting(true);
    try {
      await api.post("/whatsapp/reconnect");
    } catch {
      /* ignorar erro de rede */
    } finally {
      setReconnecting(false);
    }
  }

  // ── Effects ──────────────────────────────────────────────────────
  useEffect(() => {
    Promise.all([fetchStatus(), fetchQr()]).then(() => setLoading(false));
    timerRef.current = setInterval(() => {
      fetchStatus();
      fetchQr();
    }, POLL_INTERVAL_MS);
    return () => {
      if (timerRef.current) clearInterval(timerRef.current);
    };
  }, []);

  useEffect(() => {
    if (tab === "log") fetchLogs();
    if (tab === "sheets") fetchSheets();
  }, [tab]);

  // ── Tab buttons ──────────────────────────────────────────────────
  const tabs: { key: Tab; label: string; icon: React.ElementType }[] = [
    { key: "qrcode", label: "QR Code", icon: QrCode },
    { key: "log", label: "Log de Mensagens", icon: ScrollText },
    { key: "sheets", label: "Planilha", icon: Table2 },
  ];

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center gap-3">
        <MessageCircle className="h-8 w-8 text-emerald-600" />
        <div>
          <h1 className="text-2xl font-bold">WhatsApp</h1>
          <p className="text-sm text-muted-foreground">
            Conexão, escaneamento do QR Code e monitoramento
          </p>
        </div>
      </div>

      {/* Status bar */}
      <Card>
        <CardContent className="py-3 flex items-center gap-3">
          <span className="text-sm font-medium">Status:</span>
          <Badge variant={statusVariant[status]}>
            {loading ? "Verificando..." : statusLabel[status]}
          </Badge>
          {status !== "connected" && (
            <Button
              size="sm"
              variant="outline"
              onClick={handleReconnect}
              disabled={reconnecting}
              className="ml-auto gap-1"
            >
              <RefreshCw
                className={`h-3 w-3 ${reconnecting ? "animate-spin" : ""}`}
              />
              Reconectar
            </Button>
          )}
        </CardContent>
      </Card>

      {/* Tabs */}
      <div className="flex gap-1 border-b">
        {tabs.map(({ key, label, icon: Icon }) => (
          <button
            key={key}
            onClick={() => setTab(key)}
            className={cn(
              "flex items-center gap-1.5 px-4 py-2 text-sm font-medium border-b-2 transition-colors -mb-px",
              tab === key
                ? "border-emerald-600 text-emerald-700"
                : "border-transparent text-muted-foreground hover:text-foreground"
            )}
          >
            <Icon className="h-4 w-4" />
            {label}
          </button>
        ))}
      </div>

      {/* ── Tab: QR Code ─────────────────────────────────────────── */}
      {tab === "qrcode" && (
        <Card>
          <CardContent className="py-6">
            {status === "connected" && (
              <div className="flex flex-col items-center gap-3 py-6">
                <div className="rounded-full bg-emerald-100 p-4">
                  <Wifi className="h-10 w-10 text-emerald-600" />
                </div>
                <p className="text-center text-sm text-muted-foreground">
                  WhatsApp conectado com sucesso. As mensagens estão sendo
                  recebidas.
                </p>
              </div>
            )}

            {status === "disconnected" && (
              <div className="flex flex-col items-center gap-3 py-6">
                <div className="rounded-full bg-red-100 p-4">
                  <WifiOff className="h-10 w-10 text-red-600" />
                </div>
                <p className="text-center text-sm text-muted-foreground">
                  WhatsApp desconectado. Clique em reconectar para gerar um
                  novo QR Code.
                </p>
              </div>
            )}

            {status === "qr_pending" && (
              <div className="flex flex-col items-center gap-4 py-4">
                {qrDataUrl ? (
                  <div className="rounded-lg border bg-white p-4 shadow-sm">
                    <img
                      src={qrDataUrl}
                      alt="QR Code WhatsApp"
                      className="h-64 w-64"
                    />
                  </div>
                ) : (
                  <div className="flex flex-col items-center gap-2 py-8">
                    <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
                    <p className="text-sm text-muted-foreground">
                      Gerando QR Code...
                    </p>
                  </div>
                )}
                <p className="text-center text-sm text-muted-foreground max-w-sm">
                  Abra o <strong>WhatsApp</strong> no seu celular, vá em{" "}
                  <strong>Dispositivos conectados</strong> e escaneie o código
                  acima.
                </p>
              </div>
            )}
          </CardContent>
        </Card>
      )}

      {/* ── Tab: Log ─────────────────────────────────────────────── */}
      {tab === "log" && (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <ScrollText className="h-5 w-5" />
              Log de Mensagens Recebidas
            </CardTitle>
            <CardDescription>
              Últimas mensagens recebidas via WhatsApp e seus status de
              processamento.
            </CardDescription>
          </CardHeader>
          <CardContent>
            {logsLoading ? (
              <div className="flex justify-center py-8">
                <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
              </div>
            ) : logs.length === 0 ? (
              <p className="text-sm text-muted-foreground text-center py-8">
                Nenhuma mensagem recebida ainda.
              </p>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b text-left text-muted-foreground">
                      <th className="pb-2 font-medium">Data/Hora</th>
                      <th className="pb-2 font-medium">Telefone</th>
                      <th className="pb-2 font-medium">Tipo</th>
                      <th className="pb-2 font-medium">Status</th>
                    </tr>
                  </thead>
                  <tbody>
                    {logs.map((log) => (
                      <tr key={log.id} className="border-b last:border-0">
                        <td className="py-2 whitespace-nowrap">
                          {log.timestamp
                            ? new Date(log.timestamp).toLocaleString("pt-BR")
                            : "-"}
                        </td>
                        <td className="py-2">{log.telefone}</td>
                        <td className="py-2">
                          <Badge variant="outline">{log.tipo}</Badge>
                        </td>
                        <td className="py-2">
                          <Badge variant={logStatusVariant[log.status] || "info"}>
                            {log.status}
                          </Badge>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
            <div className="mt-4 flex justify-end">
              <Button variant="outline" size="sm" onClick={fetchLogs}>
                <RefreshCw className="h-3 w-3 mr-1" />
                Atualizar
              </Button>
            </div>
          </CardContent>
        </Card>
      )}

      {/* ── Tab: Planilha ────────────────────────────────────────── */}
      {tab === "sheets" && (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Table2 className="h-5 w-5" />
              Planilha Google Sheets
              {sheets?.spreadsheet_url && (
                <a
                  href={sheets.spreadsheet_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-sm text-emerald-600 hover:underline ml-2"
                >
                  Abrir no Google Sheets
                  <ExternalLink className="h-3 w-3 inline ml-1" />
                </a>
              )}
            </CardTitle>
            <CardDescription>
              Dados atuais da planilha sincronizada com o sistema.
            </CardDescription>
          </CardHeader>
          <CardContent>
            {sheetsLoading ? (
              <div className="flex justify-center py-8">
                <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
              </div>
            ) : !sheets?.available ? (
              <p className="text-sm text-muted-foreground text-center py-8">
                Planilha não disponível. Verifique as credenciais Google no
                <code className="mx-1">.env</code>.
              </p>
            ) : (
              <>
                {/* Sub-tabs for sheets */}
                <div className="flex gap-1 mb-4 border-b">
                  {Object.keys(sheets.sheets).map((name) => (
                    <button
                      key={name}
                      onClick={() => setActiveSheet(name)}
                      className={cn(
                        "px-3 py-1.5 text-xs font-medium border-b-2 transition-colors -mb-px",
                        activeSheet === name
                          ? "border-emerald-600 text-emerald-700"
                          : "border-transparent text-muted-foreground hover:text-foreground"
                      )}
                    >
                      {name}
                      <span className="ml-1 text-muted-foreground">
                        ({sheets.sheets[name]?.length || 0})
                      </span>
                    </button>
                  ))}
                </div>

                {/* Table */}
                {sheets.sheets[activeSheet]?.length ? (
                  <div className="overflow-x-auto max-h-96 overflow-y-auto">
                    <table className="w-full text-sm">
                      <tbody>
                        {sheets.sheets[activeSheet].map((row, rowIndex) => (
                          <tr
                            key={`${activeSheet}-${rowIndex}`}
                            className={cn(
                              "border-b last:border-0",
                              rowIndex === 0 && "bg-muted/60 font-medium"
                            )}
                          >
                            {row.map((cell, cellIndex) => (
                              <td
                                key={`${activeSheet}-${rowIndex}-${cellIndex}`}
                                className="min-w-32 px-3 py-2 align-top"
                              >
                                {cell || "-"}
                              </td>
                            ))}
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                ) : (
                  <p className="text-sm text-muted-foreground text-center py-8">
                    Nenhum dado encontrado nesta aba.
                  </p>
                )}
              </>
            )}
            <div className="mt-4 flex justify-end">
              <Button variant="outline" size="sm" onClick={fetchSheets}>
                <RefreshCw className="h-3 w-3 mr-1" />
                Atualizar
              </Button>
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
