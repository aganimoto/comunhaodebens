# Scripts Windows (.bat / .ps1)

Scripts para iniciar os serviços do CDB Shalom no Windows.

## Scripts Disponíveis

| Script | Função |
|---|---|
| `dev-all.bat` | Inicia todos os serviços (backend, celery, whatsapp, frontend) em terminais separados |
| `dev-all.ps1` | Mesmo que dev-all.bat, em PowerShell |
| `dev-backend.bat` | Inicia apenas o backend + celery worker |
| `dev-frontend.bat` | Inicia apenas o frontend |
| `dev-whatsapp.bat` | Inicia apenas o WhatsApp Service |
| `run-backend.bat` | Executa o backend diretamente (útil para debug) |
| `run-frontend.bat` | Executa o frontend diretamente |
| `run-whatsapp.bat` | Executa o WhatsApp Service diretamente |
| `dev-backend-local.ps1` | Script legacy para backend local (PowerShell) |

## Uso

```cmd
# A partir da raiz do projeto:
scripts\windows\dev-all.bat

# Ou navegue até a pasta e execute:
cd scripts\windows
dev-all.bat
```

## Observações

- O `dev-all.bat` usa caminhos relativos (`%~dp0..\..`) para funcionar de qualquer diretório.
- O `run-backend.bat` configura `PYTHONPATH` automaticamente.
- Certifique-se de ter Python, Node.js e Redis instalados antes de executar.