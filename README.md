# Proyecto Final - Análisis Léxico (Backend)

Curso: Lenguajes Formales y Autómatas

API REST del sistema de análisis léxico: registro/login de usuarios, generación
de credenciales en PDF, y procesamiento léxico de documentos de texto.

## Tecnologías

- .NET 8.0
- ASP.NET Core Web API (Controllers)
- Swagger / OpenAPI
- JWT (autenticación)

## Requisitos previos

- **Visual Studio 2022** (versión 17.8 o superior, con soporte para .NET 8) o
  **.NET SDK 8** + VS Code si prefieres línea de comandos.
- **Git**

Verifica que tienes el SDK correcto instalado:

```bash
dotnet --version
```

Debe mostrar una versión `8.x.x`.

## Instalación

1. Clona el repositorio:

```bash
git clone https://github.com/USUARIO/proyecto-lexico-backend.git
cd proyecto-lexico-backend
```

2. Restaura las dependencias:

```bash
dotnet restore
```

3. Corre el proyecto:

```bash
dotnet run
```

O si usas Visual Studio: abre el archivo `.sln`, asegúrate que el proyecto de
inicio (Startup Project) sea el correcto, y presiona **F5** o el botón ▶️.

4. Verifica que funciona abriendo Swagger en el navegador, en la URL que te
   indique la terminal, agregando `/swagger` (por ejemplo:
   `https://localhost:7123/swagger`).

## Configuración de variables sensibles

El archivo `appsettings.Development.json` (connection strings, JWT secret,
etc.) **no se sube al repositorio** por seguridad. Cada integrante debe
crearlo localmente en la raíz del proyecto API con esta estructura mínima:

```json
{
  "ConnectionStrings": {
    "DefaultConnection": "TU_CADENA_DE_CONEXION_AQUI"
  },
  "Jwt": {
    "Key": "UNA_LLAVE_SECRETA_LARGA_AQUI",
    "Issuer": "ProyectoLexico",
    "Audience": "ProyectoLexico"
  }
}
```

Pide la cadena de conexión real al encargado de Base de Datos del equipo.

## Estructura del proyecto (por capas)

```
/src
  /API             → Controllers, Program.cs, configuración de endpoints
  /Application      → Lógica de negocio, servicios
  /Domain           → Entidades, modelos de dominio
  /Infrastructure    → Acceso a datos, Entity Framework, repositorios
/tests
  /UnitTests        → Pruebas unitarias
```

## Flujo de trabajo con Git

- `main` → rama estable, no se hacen commits directos aquí.
- `develop` → rama de integración.
- Cada tarea se trabaja en una rama `feature/nombre-de-la-tarea` a partir de
  `develop`, y se sube mediante Pull Request.

```bash
git checkout develop
git pull
git checkout -b feature/nombre-de-la-tarea
# ... trabajas y haces commits ...
git push -u origin feature/nombre-de-la-tarea
```

Luego abres el Pull Request en GitHub hacia `develop`.

## Despliegue

El backend se despliega en una máquina virtual administrada por el encargado
de repositorios/infraestructura del equipo.