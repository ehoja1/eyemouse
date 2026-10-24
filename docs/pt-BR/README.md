# EyeMouse

**Controle o mouse com os olhos usando só uma webcam.** O cursor segue o seu olhar; o clique é feito com **três piscadas rápidas**.

[English](../../README.md) · **[Guia completo passo a passo](GUIA.md)**

## Recursos
- Cursor guiado pela posição da íris (MediaPipe), sem hardware especial.
- **Clique por 3 piscadas rápidas** com limiar adaptativo por usuário; piscar um olho só, piscada única ou olhos fechados por mais tempo **não** clicam.
- O cursor congela quando os olhos começam a fechar: o clique cai onde você estava olhando.
- Calibração rápida (16 pontos, ~25 s) com estimativa de precisão.
- Movimento suave (filtro One Euro). Pausa: feche os olhos ≈ 2 s; mexer o mouse físico também pausa.
- Modos `--dry-run` (não move o mouse real) e `--preview`; diagnóstico com `eyemouse doctor`.
- Privacidade: o vídeo é processado só no seu computador e nunca é salvo nem enviado.

## Início rápido
```bash
git clone https://github.com/ehoja1/eyemouse.git && cd eyemouse
python -m venv .venv
.venv\Scripts\activate               # Windows   (Mac/Linux: source .venv/bin/activate)
pip install -e ".[all]"
eyemouse doctor --fetch-model
eyemouse run --preview
```
Teste com segurança primeiro: `eyemouse run --dry-run --preview`.

Instruções detalhadas (VS Code, GitHub, ajustes, problemas): **[GUIA.md](GUIA.md)**.
