import { Users, FileSpreadsheet } from "lucide-react";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "../components/ui/card";

export function Membros() {
  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-3xl font-semibold tracking-tight">Membros</h2>
        <p className="text-sm text-muted-foreground">
          Cadastro gerenciado na aba <strong>Membros</strong> do Google Sheets
        </p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Origem dos dados</CardTitle>
            <FileSpreadsheet className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <p className="text-2xl font-semibold">Sheets</p>
            <p className="text-xs text-muted-foreground mt-1">
              Aba <code>Membros</code> · colunas: Telefone, Nome, Categoria, Ativo
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Cache local</CardTitle>
            <Users className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <p className="text-2xl font-semibold">5 min</p>
            <p className="text-xs text-muted-foreground mt-1">
              TTL configurável via aba Configuração
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Identificação</CardTitle>
            <Users className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <p className="text-2xl font-semibold">Por telefone</p>
            <p className="text-xs text-muted-foreground mt-1">
              A IA nunca vê nome ou categoria
            </p>
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Como gerenciar?</CardTitle>
          <CardDescription>
            Edite os membros diretamente na planilha do Google Sheets
          </CardDescription>
        </CardHeader>
        <CardContent className="prose prose-sm max-w-none text-muted-foreground">
          <ol className="list-decimal pl-5 space-y-1">
            <li>Abra a planilha compartilhada com a equipe financeira</li>
            <li>Adicione uma linha na aba <strong>Membros</strong></li>
            <li>Coloque o telefone no formato E.164 (ex.: <code>5511999990001</code>)</li>
            <li>Use <code>TRUE</code>/<code>FALSE</code> na coluna <strong>Ativo</strong></li>
            <li>Categoria: <code>comunidade_de_vida</code>, <code>comunidade_de_alianca</code>, <code>obra</code> ou <code>benfeitor</code></li>
          </ol>
        </CardContent>
      </Card>
    </div>
  );
}
