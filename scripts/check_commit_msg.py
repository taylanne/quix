"""Valida mensagens de commit no padrão Conventional Commits (ver CONTRIBUTING.md)."""
import re
import sys

TIPOS = "feat|fix|docs|style|refactor|perf|test|build|ci|chore|revert"
PADRAO = re.compile(rf"^({TIPOS})(\([a-z0-9-]+\))?!?: [^A-Z].*[^.]$")
IGNORAR = re.compile(r"^(Merge |Revert \"|fixup! |squash! )")

with open(sys.argv[1], encoding="utf-8") as f:
    linhas = [l for l in f.read().splitlines() if not l.startswith("#")]
titulo = next((l for l in linhas if l.strip()), "")

if IGNORAR.match(titulo) or (PADRAO.match(titulo) and len(titulo) <= 100):
    sys.exit(0)

sys.stdout.reconfigure(errors="replace")
print(f"\nCommit recusado: '{titulo}'")
print("Use: tipo(escopo opcional): descrição em minúscula, sem ponto final")
print(f"Tipos: {TIPOS.replace('|', ', ')}")
print("Exemplo: feat(quiz): adiciona barra de progresso\n")
sys.exit(1)
