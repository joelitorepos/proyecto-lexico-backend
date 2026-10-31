import os
from pathlib import Path

def generate_tree_lines(dir_path: Path, prefix: str = "", ignore_dirs=None):
    if ignore_dirs is None:
        # Carpetas a ignorar para no generar "ruido" en el mapa de contexto
        ignore_dirs = {'.git', 'node_modules', 'dist', 'build', '.DS_Store', '.env',}
        
    lines = []
    try:
        # Ordenamos: primero las carpetas, luego los archivos
        entries = sorted(list(dir_path.iterdir()), key=lambda e: (e.is_file(), e.name.lower()))
    except PermissionError:
        return lines

    # Filtramos las carpetas ignoradas
    entries = [e for e in entries if e.name not in ignore_dirs]
    entries_count = len(entries)
    
    for i, entry in enumerate(entries):
        # Determinamos el conector adecuado según si es el último elemento
        connector = "└── " if i == entries_count - 1 else "├── "
        lines.append(f"{prefix}{connector}{entry.name}")
        
        if entry.is_dir():
            # Añadimos la sangría correspondiente para los hijos
            extension = "    " if i == entries_count - 1 else "│   "
            lines.extend(generate_tree_lines(entry, prefix + extension, ignore_dirs))
            
    return lines

if __name__ == "__main__":
    target_dir = Path("app")
    root_dir = Path(".")
    output_file = "AI-MAP.md"
    
    # Exclusiones para la recursión de src/
    ignore_for_src = {'.git', 'node_modules', 'dist', 'build', '.DS_Store', '.env'}
    
    # Exclusiones visuales mínimas para la raíz (sólo quitamos git y archivos de sistema)
    ignore_for_root = {'.git', '.DS_Store'}
    
    with open(output_file, "w", encoding="utf-8") as f:
        f.write("# Mapa del Proyecto\n\n")
        
        # --- PARTE 1: Árbol de src/ ---
        f.write("## Estructura de `src/`\n")
        f.write("```text\n")
        if target_dir.exists() and target_dir.is_dir():
            f.write(f"{target_dir.name}/\n")
            tree_lines = generate_tree_lines(target_dir, ignore_dirs=ignore_for_src)
            f.write("\n".join(tree_lines))
        else:
            f.write("❌ El directorio 'src' no se encuentra en esta ubicación.\n")
        f.write("\n```\n\n")
        
        # --- PARTE 2: Contenido del Directorio Raíz ---
        f.write("## Contenido del Directorio Raíz\n")
        f.write("```text\n")
        f.write("./ (Raíz del proyecto)\n")
        
        try:
            # Iteramos solo el primer nivel (profundidad 1)
            root_entries = sorted(list(root_dir.iterdir()), key=lambda e: (e.is_file(), e.name.lower()))
            root_entries = [e for e in root_entries if e.name not in ignore_for_root]
            
            entries_count = len(root_entries)
            for i, entry in enumerate(root_entries):
                connector = "└── " if i == entries_count - 1 else "├── "
                # Añadimos "/" al final si es un directorio para distinguirlos visualmente
                suffix = "/" if entry.is_dir() else ""
                f.write(f"{connector}{entry.name}{suffix}\n")
        except PermissionError:
            f.write("❌ Error de permisos al leer la raíz.\n")
            
        f.write("```\n")
        
    print(f"✅ Mapa de arquitectura generado exitosamente en {output_file}")