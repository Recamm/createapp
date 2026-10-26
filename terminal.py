"""Interactive defaults-first terminal wizard, with a plain-text fallback."""
import copy
from pathlib import Path

from catalog import AGENTS, PACKS, roles_for
from engine import ConfigError, detect_stack, initialize, preview
from runtime import VERSION, project_defaults

class Cancelled(Exception):
    pass

class Prompts:
    def __init__(self):
        try:
            import questionary
            self.q = questionary
        except ImportError:
            self.q = None

    def ask(self, kind, message, choices=None, default=None):
        if self.q:
            if kind == "multi":
                prompt = self.q.checkbox(message, choices=[self.q.Choice(label, value=value, checked=value in default) for value, label in choices])
            elif kind == "select":
                prompt = self.q.select(message, choices=[self.q.Choice(label, value=value) for value, label in choices], default=default)
            elif kind == "confirm": prompt = self.q.confirm(message, default=default)
            else: prompt = self.q.text(message, default=str(default or ""))
            result = prompt.ask()
            if result is None: raise Cancelled()
            return result
        print("\n" + message)
        if choices:
            for n, (value, label) in enumerate(choices, 1):
                selected = value in default if kind == "multi" else value == default
                print(f" {n}. {'[x]' if selected else '[ ]'} {label}")
        try: answer = input("Enter conserva la selección; números separados por coma para cambiar: " if choices else f"[{default}] ").strip()
        except (EOFError, KeyboardInterrupt): raise Cancelled()
        if not answer: return default
        if kind == "confirm": return answer.lower() in ("s", "si", "sí", "y", "yes")
        if choices:
            try:
                selected = [] if answer == "-" else [choices[int(n.strip()) - 1][0] for n in answer.split(",") if 1 <= int(n.strip()) <= len(choices)]
                if kind == "select" and len(selected) != 1: raise ValueError()
                return selected if kind == "multi" else selected[0]
            except (ValueError, IndexError): raise ConfigError("Selección inválida. Volvé a ejecutar el configurador.")
        return answer

def collect(project, prompts, base=None):
    project = Path(project).resolve()
    if not project.is_dir(): raise ConfigError("La carpeta del proyecto debe existir.")
    c = copy.deepcopy(base) if base is not None else project_defaults(project)
    c["directory"] = "."
    c["template"] = "config-only"
    c["agents"] = prompts.ask("multi", "Asistentes (Espacio marca; Enter continúa)", list(AGENTS.items()), c["agents"])
    if not c["agents"]: raise ConfigError("Seleccioná al menos un asistente.")
    c["agent"] = c["agents"][0] if len(c["agents"]) == 1 else prompts.ask("select", "Asistente principal", [(a, AGENTS[a]) for a in c["agents"]], c["agent"] if c["agent"] in c["agents"] else c["agents"][0])
    c["packs"] = prompts.ask("multi", "Paquetes (los recomendados ya están marcados)", [(p["id"], p["name"] + (" · opcional" if not p["default"] else "")) for p in PACKS], c["packs"])
    c["mode"] = prompts.ask("select", "Forma de trabajar", [("fast", "Ágil"), ("balanced", "Equilibrado · recomendado"), ("rigorous", "Riguroso")], c["mode"])
    c["testing"] = "strict" if c["mode"] == "rigorous" else "balanced"
    c["autonomy"] = {"fast": "autonomous", "balanced": "milestones", "rigorous": "guided"}[c["mode"]]
    detected = detect_stack(project)
    c["stack"] = prompts.ask("select", "Stack del proyecto", [("auto", "Detectar · " + detected), ("react-vite", "React + Vite"), ("nextjs", "Next.js"), ("web", "Web / otro frontend"), ("python", "Python / backend")], "auto")
    c["stack"] = detected if c["stack"] == "auto" else c["stack"]
    c["database"] = prompts.ask("select", "Referencia de base de datos", [("none", "Ninguna"), ("postgres", "Postgres / Supabase")], c["database"])
    coordinators = [(p, label) for p, label in [("superpowers", "Superpowers"), ("matt", "Matt Pocock")] if p in c["packs"]] + [("simple", "Proceso simple")]
    default_coordinator = c["coordinator"] if c["coordinator"] in {x[0] for x in coordinators} else coordinators[0][0]
    c["coordinator"] = prompts.ask("select", "Único coordinador del proceso", coordinators, default_coordinator)
    if prompts.ask("confirm", "¿Ajustar skills individuales y reglas avanzadas?", default=False):
        extras = prompts.ask("multi", "Complementos de Vercel", [("vercel_react", "React Best Practices · solo React/Next"), ("vercel_web", "Web Design Guidelines · web"), ("vercel_composition", "Composition Patterns · bajo pedido")], [k for k in ("vercel_react", "vercel_web", "vercel_composition") if c[k]])
        for key in ("vercel_react", "vercel_web", "vercel_composition"): c[key] = key in extras
        available = roles_for(c, include_unselected=True)
        c["skills"] = prompts.ask("multi", "Skills activas para esta selección", [(k, "ca-" + k + " · " + v[3]) for k, v in available.items()], list(available) if c["skills"] is None else c["skills"])
        c["autonomy"] = prompts.ask("select", "Autonomía", [("milestones", "Acordar enfoque y avanzar"), ("autonomous", "Avanzar con supuestos explícitos"), ("guided", "Revisar cada hito")], c["autonomy"])
        c["testing"] = prompts.ask("select", "Pruebas", [("balanced", "Proporcionales"), ("strict", "TDD para comportamiento")], c["testing"])
        c["design"] = prompts.ask("select", "Diseño", [("existing", "Conservar el diseño existente"), ("balanced", "Usabilidad e identidad"), ("expressive", "Mayor libertad visual")], c["design"])
        c["parallel"] = prompts.ask("confirm", "¿Permitir subagentes en tareas independientes?", default=c["parallel"])
    return c

def run(project, cache=None, prompts=None):
    prompts = prompts or Prompts()
    print(f"\nCreateApp {VERSION} · Configurar un proyecto existente")
    if project is None:
        project = Path(prompts.ask("text", "Carpeta del proyecto", default=str(Path.cwd()))).expanduser()
    project = Path(project).resolve()
    print("Proyecto:", project)
    try:
        c = collect(project, prompts)
        p = preview(c, project)
        print("\nVista previa")
        print("  Asistentes:", ", ".join(AGENTS[a] for a in p["config"]["agents"]))
        print("  Coordinador:", c["coordinator"], "· Pruebas:", c["testing"])
        print("  Perfiles:", ", ".join("ca-" + name for name in p["roles"]) or "ninguno")
        print("  Archivos de configuración:", len(p["files"]))
        print("  El código y las dependencias del proyecto se conservan.")
        for message in p["warnings"]: print("  ·", message)
        if p["conflicts"]: raise ConfigError("Hay conflictos: " + ", ".join(p["conflicts"]))
        if not prompts.ask("confirm", "¿Aplicar esta configuración local?", default=False):
            print("Cancelado. No se modificó el proyecto.")
            return None
        result = initialize(p["config"], project, cache, print)
        print("\nListo:", result["target"])
        print(result["next"])
        return result
    except Cancelled:
        print("\nCancelado. No se modificó el proyecto.")
        return None
