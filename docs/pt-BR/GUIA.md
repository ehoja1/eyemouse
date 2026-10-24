# Guia completo (Português do Brasil)

Este guia leva você do zero até o projeto rodando no VS Code e publicado no GitHub.

## Parte 1 — Instalar o que é necessário

1. **Python 3.10 a 3.13**: https://www.python.org/downloads/
   - Windows: na instalação, marque **"Add python.exe to PATH"**.
   - Confira no terminal: `python --version` (no Mac/Linux pode ser `python3`).
2. **Git**: https://git-scm.com/downloads — confira com `git --version`.
3. **VS Code**: https://code.visualstudio.com/
4. Uma **webcam** e uma conta no **GitHub**: https://github.com/signup

## Parte 2 — Abrir o projeto no VS Code

1. Extraia o ZIP `eyemouse.zip` (por exemplo em `Documentos`).
2. VS Code → **File → Open Folder…** → escolha a pasta `eyemouse`.
3. Aceite a sugestão **"Install recommended extensions"** (Python, Pylance, Ruff, TOML).
4. Abra o terminal: **Terminal → New Terminal**.

## Parte 3 — Criar o ambiente e instalar

No terminal do VS Code, dentro da pasta `eyemouse`:

**Windows (PowerShell)**
```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
```
Se o PowerShell bloquear scripts: `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` e tente de novo.

**macOS / Linux**
```bash
python3 -m venv .venv
source .venv/bin/activate
```

Depois (todos os sistemas):
```bash
pip install --upgrade pip
pip install -e ".[all,dev]"
```
No VS Code pressione `Ctrl+Shift+P` → **Python: Select Interpreter** → escolha o que está em `.venv`.

## Parte 4 — Verificar e rodar

```bash
pytest                              # roda os testes (não precisa de câmera)
eyemouse doctor --fetch-model       # diagnostica e baixa o modelo de rosto (uma vez)
eyemouse run --dry-run --preview    # modo seguro: mostra a câmera, NÃO move o mouse real
eyemouse run --preview              # uso real
```

Na **primeira execução** o programa faz a **calibração**: uma tela preta mostra 16 pontos. Olhe para cada ponto até ele sumir, sem mexer a cabeça e com os olhos abertos (≈ 25 s). `ESC` cancela. A calibração fica salva; para refazer: `eyemouse run --recalibrate`.

Também dá para rodar pelo VS Code: aba **Run and Debug** (`Ctrl+Shift+D`) → escolha *EyeMouse: run (dry-run + preview)* → ▶.

## Parte 5 — Como usar

| Gesto | Efeito |
|---|---|
| Olhar | O cursor segue o olhar |
| **3 piscadas rápidas** (em até ~1,5 s) | Clique esquerdo onde você estava olhando |
| Fechar os dois olhos ≈ 2 s | Pausa / retoma o controle |
| Mexer o mouse físico | Pausa automática |
| `p` / `q` na janela de prévia | Pausar / sair |

Dicas: luz boa e de frente (nada de janela atrás de você), câmera na altura dos olhos, 40–70 cm de distância, cabeça relativamente parada. Piscar um pouco **mais firme e rápido** do que o normal ajuda. Piscar um olho só **não** conta.

## Parte 6 — Ajustar o comportamento

Copie `config.example.toml` para `meu.toml`, altere só o que precisa e rode:
```bash
eyemouse run --config meu.toml --preview
```
Os ajustes mais úteis:
- `cursor.min_cutoff` menor → cursor mais estável; `cursor.beta` maior → mais rápido.
- `blink.close_ratio` (0,70) → maior = piscadas detectadas com mais facilidade.
- `blink.max_gap_s` / `blink.max_sequence_s` → tempo permitido entre/durante as 3 piscadas.
- `cursor.button = "right"` → clique direito.
- `blink.required_blinks = 2` → clique com duas piscadas.

Erros de digitação no arquivo são recusados com uma mensagem clara.

## Parte 7 — Publicar no GitHub

1. No GitHub: **New repository** → nome `eyemouse` → deixe **sem** README/.gitignore/licença (o projeto já tem) → **Create repository**.
2. O usuário `ehoja1` já está configurado nos links do projeto (README, pyproject, CONTRIBUTING). Confira apenas o nome do autor em `LICENSE` e `pyproject.toml`.
3. No terminal, dentro da pasta do projeto:
```bash
git init -b main
git add .
git commit -m "Initial release of EyeMouse 0.1.0"
git remote add origin https://github.com/ehoja1/eyemouse.git
git push -u origin main
```
   Na primeira vez o Git pede login; use o navegador/VS Code quando solicitado (ou um *Personal Access Token*).
4. Abra a aba **Actions** no GitHub: o CI roda sozinho (lint, tipos e testes em Windows, macOS e Linux).
5. Em **Settings → Security**, ative *Private vulnerability reporting* e *Dependabot alerts*.

### Publicar uma versão
```bash
git tag v0.1.0
git push origin v0.1.0
```
Depois, no GitHub: **Releases → Draft a new release** → escolha a tag `v0.1.0` → copie o texto do `CHANGELOG.md`.

## Parte 8 — Desenvolvimento diário

- Formatar/lint/tipos/testes de uma vez: **Terminal → Run Build Task** (`Ctrl+Shift+B`).
- Fluxo com Git: `git checkout -b minha-melhoria` → editar → `git commit` → `git push` → abrir *Pull Request*.
- Regra de ouro da arquitetura: a lógica (`features`, `blink`, `calibration`, `filters`, `pipeline`) **nunca** importa câmera, MediaPipe ou pyautogui. Veja `docs/ARCHITECTURE.md`.

## Parte 9 — Problemas comuns

Veja `docs/TROUBLESHOOTING.md`. Os mais frequentes:
- **Câmera não abre**: feche Zoom/Teams/Meet; tente `--camera 1`.
- **macOS**: permita **Câmera** e **Acessibilidade** para o Terminal/VS Code e reinicie-o.
- **Linux**: use sessão **X11** (Wayland não permite controlar o mouse).
- **Cursor impreciso**: recalibre com boa luz e a cabeça parada.
- **Não clica**: use `--preview`, observe os valores EAR e ajuste `blink.close_ratio`.

## Aviso importante
Rastreamento ocular por webcam é **aproximado** (erro típico de 1 a 3 cm na tela). Ele serve muito bem para acessibilidade e navegação sem as mãos, mas não para tarefas que exigem precisão de pixel. O software não é um dispositivo médico.
