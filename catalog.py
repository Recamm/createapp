"""Curated roles. Upstream packs are references, never competing orchestrators."""

PACKS = [
    {"id": "superpowers", "name": "Superpowers", "default": True, "detail": "Planificación, ejecución, diagnóstico y verificación. Dirige el proceso por defecto."},
    {"id": "ponytail", "name": "Ponytail", "default": True, "detail": "Simplicidad, reutilización y revisión. Respeta la política de pruebas elegida."},
    {"id": "uiux", "name": "UI UX Pro Max", "default": True, "detail": "Usabilidad, responsive, accesibilidad y sistema de diseño."},
    {"id": "anthropic", "name": "Anthropic Skills", "default": True, "detail": "Selección: frontend-design y webapp-testing. No instala el paquete entero."},
    {"id": "addy", "name": "Addy Osmani Agent Skills", "default": True, "detail": "Selección: documentación oficial, seguridad y rendimiento. Sin segundo planificador."},
    {"id": "matt", "name": "Matt Pocock Skills", "default": False, "detail": "Opcional: handoff y diseño de módulos; puede elegirse como coordinador alternativo."},
    {"id": "graphify", "name": "Graphify", "default": False, "detail": "Opcional: mapa del código, solo bajo pedido. Su CLI se prepara en un entorno local separado."},
]

AGENTS = {"copilot": "GitHub Copilot", "codex": "Codex", "claude": "Claude Code", "cursor": "Cursor", "opencode": "OpenCode"}

# repo, paths to reference, narrowly scoped description
ROLES = {
    "workflow": ("superpowers", "obra/superpowers", ["skills/brainstorming/SKILL.md", "skills/writing-plans/SKILL.md", "skills/executing-plans/SKILL.md", "skills/test-driven-development/SKILL.md", "skills/verification-before-completion/SKILL.md", "skills/requesting-code-review/SKILL.md"], "Planificar y ejecutar funcionalidades de este proyecto según su política. No reiniciar una especificación ya acordada."),
    "debug": ("superpowers", "obra/superpowers", ["skills/systematic-debugging/SKILL.md"], "Investigar errores reproducibles o fallos de pruebas. Encontrar la causa antes de corregir."),
    "simplicity": ("ponytail", "DietrichGebert/ponytail", ["skills/ponytail/SKILL.md", "skills/ponytail-review/SKILL.md"], "Aplicar simplicidad al código de este proyecto. No dirigir el proceso ni reducir los requisitos o las pruebas acordadas."),
    "ux": ("uiux", "nextlevelbuilder/ui-ux-pro-max-skill", [".claude/skills/ui-ux-pro-max/SKILL.md"], "Diseñar o revisar interacción, accesibilidad y responsive. Respetar el sistema de diseño acordado."),
    "visual": ("anthropic", "anthropics/skills", ["skills/frontend-design/SKILL.md"], "Definir o implementar identidad visual cuando la tarea involucre interfaz. No sustituir decisiones ya aprobadas."),
    "browser-test": ("anthropic", "anthropics/skills", ["skills/webapp-testing/SKILL.md"], "Probar flujos web en navegador cuando cambie el comportamiento de la interfaz. Usar herramientas existentes antes de añadir otras."),
    "sources": ("addy", "addyosmani/agent-skills", ["skills/source-driven-development/SKILL.md"], "Verificar APIs o patrones desconocidos con documentación oficial de la versión instalada."),
    "security": ("addy", "addyosmani/agent-skills", ["skills/security-and-hardening/SKILL.md"], "Revisar confianza, entradas, permisos, datos y secretos al modificar esas superficies."),
    "performance": ("addy", "addyosmani/agent-skills", ["skills/performance-optimization/SKILL.md"], "Investigar un problema de rendimiento medido o solicitado. No optimizar de forma especulativa."),
    "handoff": ("matt", "mattpocock/skills", ["skills/productivity/handoff/SKILL.md"], "Bajo pedido: guardar un traspaso de trabajo para continuar en otra sesión."),
    "module-design": ("matt", "mattpocock/skills", ["skills/engineering/codebase-design/SKILL.md"], "Bajo pedido: revisar límites de módulos cuando exista acoplamiento o dificultad real para probarlos."),
    "matt-workflow": ("matt", "mattpocock/skills", ["skills/engineering/grill-with-docs/SKILL.md", "skills/engineering/implement/SKILL.md", "skills/engineering/tdd/SKILL.md", "skills/engineering/code-review/SKILL.md"], "Planificar e implementar usando Matt como único coordinador, según la política del proyecto."),
    "graph": ("graphify", "Graphify-Labs/graphify", ["graphify/skill-agents.md"], "Bajo pedido: construir o consultar un mapa estructural. No ejecutar escaneos, watchers ni servicios automáticamente."),
    "react": ("vercel_react", "vercel-labs/agent-skills", ["skills/react-best-practices/SKILL.md"], "Aplicar patrones de rendimiento React a código React. Omitir reglas de Next.js en Vite y APIs incompatibles con la versión instalada."),
    "web-review": ("vercel_web", "vercel-labs/agent-skills", ["skills/web-design-guidelines/SKILL.md"], "Bajo pedido o al cerrar un cambio de interfaz: revisar accesibilidad y comportamiento sin rediseñar la identidad."),
    "composition": ("vercel_composition", "vercel-labs/agent-skills", ["skills/composition-patterns/SKILL.md"], "Bajo pedido: mejorar componentes con complejidad demostrada. No crear compound components ni contextos por anticipado."),
    "postgres": ("postgres", "supabase/agent-skills", ["skills/supabase-postgres-best-practices/SKILL.md"], "Revisar SQL, índices, conexiones y RLS solo cuando el proyecto usa Postgres o Supabase."),
    "next": ("next", "vercel-labs/openreview", [".agents/skills/next-best-practices/SKILL.md"], "Aplicar convenciones y límites RSC solo a proyectos Next.js y tras verificar la versión."),
}

DEFAULTS = {
    "name": "mi-app", "directory": ".", "agent": "copilot", "agents": ["copilot"], "stack": "auto",
    "template": "config-only", "mode": "balanced", "coordinator": "superpowers",
    "testing": "balanced", "autonomy": "milestones", "parallel": False,
    "design": "existing", "database": "none", "goal": "", "skills": None,
    "packs": [p["id"] for p in PACKS if p["default"]],
    "vercel_react": True, "vercel_web": True, "vercel_composition": False,
}

def roles_for(config, *, include_unselected=False):
    enabled = set(config["packs"])
    if config["vercel_react"] and config["stack"] in ("react-vite", "nextjs"): enabled.add("vercel_react")
    if config["vercel_web"] and config["stack"] in ("react-vite", "nextjs", "web"): enabled.add("vercel_web")
    if config["vercel_composition"] and config["stack"] in ("react-vite", "nextjs"): enabled.add("vercel_composition")
    if config["database"] == "postgres": enabled.add("postgres")
    if config["stack"] == "nextjs": enabled.add("next")
    roles = {k: v for k, v in ROLES.items() if v[0] in enabled}
    if config["coordinator"] != "superpowers":
        roles.pop("workflow", None)
        roles.pop("debug", None)
    if config["coordinator"] != "matt": roles.pop("matt-workflow", None)
    if not include_unselected and config.get("skills") is not None:
        roles = {name: value for name, value in roles.items() if name in config["skills"]}
    return roles
