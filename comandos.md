# Guía de Comandos - AI Infra Monitor

Este archivo contiene los comandos necesarios para ejecutar, probar y mantener el sistema.

## 1. Ejecución del Sistema (3 Terminales)

Para ver el sistema completo funcionando, necesitas abrir 3 terminales y ejecutar un componente en cada una.

### Terminal 1: Backend (Servidor)

Recibe los datos y sirve la API.

```powershell
python -m uvicorn backend.app.main:app --reload
```

_URL:_ http://localhost:8000 (o 8001 según configuración)

### Terminal 2: Worker (Alertas)

Procesa los datos en segundo plano y genera alertas.

```powershell
python backend/worker/run_worker.py
```

### Terminal 3: Agente (Recolector)

Recolecta métricas de tu PC y las envía al backend.

```powershell
python -m agent run
```

---

## 2. Pruebas y Datos

### Insertar Datos Sintéticos

Inyecta datos falsos (normales y de pánico) para probar alertas sin estresar tu PC.

```powershell
python backend/scripts/insert_synthetic_data.py
```

### Ejecutar Tests Automatizados

Corre todos los tests para asegurar que el código está bien.

```powershell
# Tests del Backend
python -m pytest backend/tests

# Tests del Agente
python -m pytest agent/tests
```

---

# Guía de Comandos - AI Infra Monitor

Este archivo contiene los comandos necesarios para ejecutar, probar y mantener el sistema.

## 1. Ejecución del Sistema (3 Terminales)

Para ver el sistema completo funcionando, necesitas abrir 3 terminales y ejecutar un componente en cada una.

### Terminal 1: Backend (Servidor)

Recibe los datos y sirve la API.

```powershell
python -m uvicorn backend.app.main:app --reload
```

_URL:_ http://localhost:8000 (o 8001 según configuración)

### Terminal 2: Worker (Alertas)

Procesa los datos en segundo plano y genera alertas.

```powershell
python backend/worker/run_worker.py
```

### Terminal 3: Agente (Recolector)

Recolecta métricas de tu PC y las envía al backend.

```powershell
python -m agent run
```

---

## 2. Pruebas y Datos

### Insertar Datos Sintéticos

Inyecta datos falsos (normales y de pánico) para probar alertas sin estresar tu PC.

```powershell
python backend/scripts/insert_synthetic_data.py
```

### Ejecutar Tests Automatizados

Corre todos los tests para asegurar que el código está bien.

```powershell
# Tests del Backend
python -m pytest backend/tests

# Tests del Agente
python -m pytest agent/tests
```

---

## 3. Mantenimiento de Base de Datos

El script de limpieza elimina datos antiguos de la tabla `metrics_raw`.

### Verificación (Dry Run)

Simula la limpieza para ver cuántos registros se borrarían, sin borrar nada.

```powershell
# Ver qué se borraría si la política fuera de 1 día
python backend/scripts/cleanup_data.py --days 1 --dry-run

# Ver qué se borraría si la política fuera de 0 días (borrar todo lo anterior a hoy)
python backend/scripts/cleanup_data.py --days 0 --dry-run
```

### Ejecución Real (Borrar datos)

Elimina físicamente los registros. **¡Cuidado! No se puede deshacer.**

```powershell
# Borrar datos más viejos de 7 días (default)
python backend/scripts/cleanup_data.py

# Borrar datos más viejos de 1 día
python backend/scripts/cleanup_data.py --days 1

# Borrar TODO (útil para reiniciar pruebas)
python backend/scripts/cleanup_data.py --days 0
```

---

## 4. Dashboard Web (Sprint 4)

El dashboard React permite visualizar hosts, métricas en tiempo real y alertas con análisis de IA.

### Iniciar el Dashboard

Abre una **nueva terminal** (Terminal 5) y ejecuta:

```powershell
cd dashboard
npm run dev
```

Luego abre tu navegador en: **http://localhost:5173**

### Rutas Disponibles

- `/hosts` - Lista de todos los hosts
- `/hosts/{id}` - Detalles de un host con gráfico de CPU en tiempo real
- `/alerts` - Feed de alertas con botón "Analyze"

### Actualizar la Base de Datos (Solo primera vez)

Si actualizaste desde Sprint 3, necesitas agregar la columna `alert_id` a la tabla `analyses`:

```powershell
# Conectarse a PostgreSQL y ejecutar:
psql -U postgres -d ai_infra_monitor
```

```sql
ALTER TABLE analyses ADD COLUMN alert_id INTEGER REFERENCES alerts(id) ON DELETE CASCADE;
```
