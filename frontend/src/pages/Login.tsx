import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { LogIn, Mail, Lock } from "lucide-react";
import { api } from "../lib/api";
import { useAuthStore } from "../stores/auth.store";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";
import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from "../components/ui/card";

const schema = z.object({
  email: z.string().email("E-mail inválido"),
  senha: z.string().min(6, "Senha deve ter ao menos 6 caracteres"),
});

type FormData = z.infer<typeof schema>;

export function Login() {
  const [erro, setErro] = useState("");
  const [loading, setLoading] = useState(false);
  const setToken = useAuthStore((s) => s.setToken);
  const navigate = useNavigate();

  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<FormData>({
    // sem resolver para evitar mais deps; validação básica no submit
  });

  async function onSubmit(values: FormData) {
    const parsed = schema.safeParse(values);
    if (!parsed.success) {
      setErro(parsed.error.issues[0]?.message || "Dados inválidos");
      return;
    }
    setErro("");
    setLoading(true);
    try {
      const { data } = await api.post("/auth/login", parsed.data);
      setToken(data.access_token);
      navigate("/");
    } catch {
      setErro("Credenciais inválidas");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-muted/30 p-4">
      <Card className="w-full max-w-sm">
        <CardHeader>
          <div className="flex items-center gap-2">
            <div className="h-10 w-10 rounded-md bg-brand text-white flex items-center justify-center">
              <LogIn className="h-5 w-5" />
            </div>
            <div>
              <CardTitle>CDB Shalom</CardTitle>
              <CardDescription>Comunhão de Bens — painel administrativo</CardDescription>
            </div>
          </div>
        </CardHeader>
        <form onSubmit={handleSubmit(onSubmit)}>
          <CardContent className="space-y-4">
            <div className="space-y-1.5">
              <Label htmlFor="email">E-mail</Label>
              <div className="relative">
                <Mail className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                <Input
                  id="email"
                  type="email"
                  autoComplete="email"
                  className="pl-9"
                  placeholder="seu@email.com"
                  {...register("email", { required: true })}
                />
              </div>
              {errors.email && (
                <p className="text-xs text-destructive">{errors.email.message}</p>
              )}
            </div>

            <div className="space-y-1.5">
              <Label htmlFor="senha">Senha</Label>
              <div className="relative">
                <Lock className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                <Input
                  id="senha"
                  type="password"
                  autoComplete="current-password"
                  className="pl-9"
                  placeholder="••••••••"
                  {...register("senha", { required: true })}
                />
              </div>
              {errors.senha && (
                <p className="text-xs text-destructive">{errors.senha.message}</p>
              )}
            </div>

            {erro && (
              <div className="text-sm text-destructive bg-destructive/10 px-3 py-2 rounded">
                {erro}
              </div>
            )}
          </CardContent>
          <CardFooter>
            <Button type="submit" className="w-full" disabled={loading}>
              {loading ? "Entrando…" : "Entrar"}
            </Button>
          </CardFooter>
        </form>
      </Card>
    </div>
  );
}
