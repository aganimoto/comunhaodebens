# Scripts do CDB Shalom

Organização dos scripts do projeto.

## Estrutura

```
scripts/
├── README.md          ← este arquivo
├── windows/           ← Scripts .bat / .ps1 para Windows
└── dev/               ← Scripts utilitários de desenvolvimento (Python, Shell)
```

### `windows/`

Scripts para iniciar os serviços (backend, celery, whatsapp, frontend) no Windows.  
Consulte [scripts/windows/README.md](windows/README.md) para detalhes.

### `dev/`

Scripts utilitários para setup inicial, seed de dados, etc.  
Consulte [scripts/dev/README.md](dev/README.md) para detalhes.