from plantillas import lineas_de_plantilla, quitar_plantilla
from triage import limpiar_cuerpo

PLANTILLA_MD = """---
name: Bug report
about: Create a report to help us improve
labels: bug
---

**Describe the bug**
A clear and concise description of what the bug is.

**To Reproduce**
Steps to reproduce the behavior:
1. Go to '...'
2. Click on '....'
3. See error

**Expected behavior**
A clear and concise description of what you expected to happen.

**Screenshots**
If applicable, add screenshots to help explain your problem.
"""

PLANTILLA_YML = """name: Bug report
description: File a bug report
body:
  - type: textarea
    attributes:
      label: Describe the bug
      description: What happened?
  - type: input
    attributes:
      label: Version
  - type: checkboxes
    attributes:
      label: Checklist
      options:
        - label: I have searched the existing issues
          required: true
"""

CASOS = [
    ("md vacío", "bug_report.md", PLANTILLA_MD,
     PLANTILLA_MD.split("---", 2)[2], False),
    ("md lleno", "bug_report.md", PLANTILLA_MD,
     "**Describe the bug**\nThe app crashes when I open settings on Windows 11.\n\n"
     "**To Reproduce**\n1. Open the app\n2. Click on settings\n3. See error\n\n"
     "**Expected behavior**\nThe settings page should open normally.", True),
    ("formulario vacío", "bug.yml", PLANTILLA_YML,
     "### Describe the bug\n\n_No response_\n\n### Version\n\n_No response_\n\n"
     "### Checklist\n\n- [X] I have searched the existing issues", False),
    ("formulario lleno", "bug.yml", PLANTILLA_YML,
     "### Describe the bug\n\nExporting a PDF with images freezes the editor for 30 seconds.\n\n"
     "### Version\n\n2.4.1\n\n### Checklist\n\n- [X] I have searched the existing issues", True),
]

fallos = 0
for nombre, archivo, plantilla, cuerpo, esperado_util in CASOS:
    lineas = lineas_de_plantilla(archivo, plantilla)
    antes = len(limpiar_cuerpo(cuerpo))
    despues = len(limpiar_cuerpo(quitar_plantilla(cuerpo, lineas)))
    util = despues >= 30
    estado = "OK" if util == esperado_util else "FALLA"
    fallos += estado == "FALLA"
    print(f"{estado:5} {nombre:18} antes: {antes:4} caracteres  después: {despues:4} caracteres")

print("Todas las pruebas pasaron" if not fallos else f"{fallos} pruebas fallaron")