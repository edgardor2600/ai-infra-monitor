# Guía de Comandos - AI Infra Monitor

Este archivo contiene todos los comandos necesarios para ejecutar, probar y mantener el sistema.

---

## 1. Ejecución del Sistema Completo

Para ver el sistema funcionando completamente, necesitas abrir **5 terminales** y ejecutar cada componente:

### Terminal 1: Backend (Servidor API)

Recibe los datos y sirve la API REST.

```powershell
cd backend
python -m uvicorn app.main:app --reload --port 8000
```

**URL:** http://localhost:8000  
**Docs:** http://localhost:8000/docs (Swagger UI)

### Terminal 2: Worker (Procesamiento de Alertas)

Procesa métricas en segundo plano y genera alertas automáticas.

```powershell
python backend/worker/run_worker.py
```

**Función:** Evalúa reglas (CPU > 90%, deltas anormales) cada 10 segundos.

### Terminal 3: Analysis Worker (LLM para Análisis de Alertas)

Procesa análisis de alertas usando IA (Gemini) cuando el usuario hace clic en "Analyze".

```powershell
python backend/worker/analysis_worker.py
```

**Función:** Escucha cola de análisis y genera diagnósticos con IA.  
**Requisito:** Variable `GEMINI_API_KEY` en `.env`

### Terminal 4: Agente (Recolector de Métricas)

Recolecta métricas de tu PC (CPU, memoria, procesos) y las envía al backend.

```powershell
python -m agent run
```

**Función:**

- Recolecta CPU/memoria cada 5 segundos
- Recolecta procesos cada 60 segundos (top 10 por CPU y RAM)
- Envía batches al backend

### Terminal 5: Dashboard (Frontend React)

Interfaz web para visualizar hosts, métricas, alertas y procesos.

```powershell
cd dashboard
npm run dev
```

**URL:** http://localhost:5173

---

## 2. Rutas del Dashboard

### Navegación Principal

- **`/hosts`** - Lista de todos los hosts monitoreados
- **`/hosts/{id}`** - Detalles de un host con gráficos en tiempo real
- **`/hosts/{id}/processes`** - Monitor de procesos del host (NUEVO)
- **`/alerts`** - Feed de alertas con análisis de IA

### Funcionalidades

- **Gráficos en tiempo real** - CPU y memoria actualizados cada 3 segundos
- **Análisis de alertas** - Botón "Analyze" usa IA para diagnosticar problemas
- **Monitor de procesos** - Ver aplicaciones que consumen más recursos
  - Tabs: Top por CPU / Top por RAM
  - Búsqueda de procesos
  - Gráficos históricos por proceso
  - Auto-refresh cada 5 segundos

---

## 3. Migraciones de Base de Datos

### Migración Inicial (Primera vez)

Crea todas las tablas del sistema:

```powershell
python backend/scripts/init_db.py
```

### Migración de Procesos (Sprint Actual)

Agrega la tabla `process_metrics` para monitoreo de procesos:

```powershell
python backend/scripts/add_process_metrics_table.py
```

### Migración de Análisis (Sprint 4)

Agrega columna `alert_id` a la tabla `analyses`:

```sql
-- Conectarse a PostgreSQL
psql -U postgres -d ai_infra_monitor

-- Ejecutar migración
ALTER TABLE analyses ADD COLUMN IF NOT EXISTS alert_id INTEGER REFERENCES alerts(id) ON DELETE CASCADE;
```

---

## 4. Pruebas y Datos de Prueba

### Insertar Datos Sintéticos

Inyecta datos falsos (normales y de pánico) para probar alertas sin estresar tu PC.

```powershell
python backend/scripts/insert_synthetic_data.py
```

**Genera:**

- Métricas normales (CPU 20-40%, RAM 30-50%)
- Picos de CPU (>90%) para disparar alertas HIGH
- Deltas anormales para alertas MEDIUM

### Ejecutar Tests Automatizados

```powershell
# Tests del Backend
python -m pytest backend/tests -v

# Tests del Agente
python -m pytest agent/tests -v

# Tests específicos
python -m pytest backend/tests/test_analysis_worker.py -v
```

---

## 5. Mantenimiento de Base de Datos

### Limpieza de Datos Antiguos

El script de limpieza elimina datos antiguos de `metrics_raw`.

#### Verificación (Dry Run)

Simula la limpieza sin borrar nada:

```powershell
# Ver qué se borraría (7 días por defecto)
python backend/scripts/cleanup_data.py --dry-run

# Ver qué se borraría (1 día)
python backend/scripts/cleanup_data.py --days 1 --dry-run

# Ver qué se borraría (todo)
python backend/scripts/cleanup_data.py --days 0 --dry-run
```

#### Ejecución Real

**⚠️ CUIDADO: Esto borra datos permanentemente**

```powershell
# Borrar datos más viejos de 7 días (default)
python backend/scripts/cleanup_data.py

# Borrar datos más viejos de 1 día
python backend/scripts/cleanup_data.py --days 1

# Borrar TODO (útil para reiniciar pruebas)
python backend/scripts/cleanup_data.py --days 0
```

---

## 6. Configuración de Variables de Entorno

Asegúrate de tener un archivo `.env` en la raíz del proyecto:

```env
# Base de datos PostgreSQL
DB_NAME=ai_infra_monitor
DB_USER=postgres
DB_PASSWORD=tu_password
DB_HOST=localhost
DB_PORT=5432

# API Key para análisis con IA (Gemini)
GEMINI_API_KEY=tu_api_key_aqui

# Configuración del agente
AGENT_INTERVAL=5
AGENT_BATCH_MAX=20
AGENT_BATCH_TIMEOUT=20
BACKEND_URL=http://localhost:8000
AGENT_HOST_ID=1
```

---

## 7. Endpoints API Principales

### Hosts

- `GET /api/v1/hosts` - Lista de hosts
- `GET /api/v1/hosts/{id}` - Detalles de un host

### Métricas

- `POST /api/v1/ingest/metrics` - Ingerir métricas (usado por el agente)
- `GET /api/v1/metrics?host_id={id}&limit={n}` - Obtener métricas

### Alertas

- `GET /api/v1/alerts?status=open` - Lista de alertas
- `POST /api/v1/alerts/{id}/analyze` - Solicitar análisis con IA
- `GET /api/v1/alerts/{id}/analysis` - Obtener resultado del análisis

### Procesos (NUEVO)

- `GET /api/v1/processes/top?host_id={id}&metric=cpu&limit=10` - Top procesos
- `GET /api/v1/processes/{name}/history?host_id={id}&hours=1` - Histórico de proceso
- `GET /api/v1/processes/list?host_id={id}` - Lista de procesos únicos

---

## 8. Solución de Problemas Comunes

### El agente no envía datos

```powershell
# Verificar que el backend esté corriendo
curl http://localhost:8000/health

# Ejecutar agente en modo dry-run para ver los datos
python -m agent run --dry-run
```

### Las alertas no se generan

```powershell
# Verificar que el worker esté corriendo
# Revisar logs del worker para ver si procesa hosts

# Insertar datos sintéticos para forzar alertas
python backend/scripts/insert_synthetic_data.py
```

### El análisis de IA no funciona

```powershell
# Verificar que analysis_worker esté corriendo
# Verificar que GEMINI_API_KEY esté en .env
# Revisar logs del analysis_worker
```

### Los procesos no aparecen en el dashboard

```powershell
# Verificar que la migración se ejecutó
python backend/scripts/add_process_metrics_table.py

# Verificar que el agente esté recolectando procesos
# (Debe mostrar "Collecting process metrics" cada 60 segundos en logs)
```

---

## 9. Desarrollo

### Instalar Dependencias

```powershell
# Backend
pip install -r requirements.txt

# Frontend
cd dashboard
npm install
```

### Ejecutar en Modo Desarrollo

```powershell
# Backend con auto-reload
cd backend
python -m uvicorn app.main:app --reload

# Frontend con hot-reload
cd dashboard
npm run dev
```

### Build de Producción

```powershell
# Frontend
cd dashboard
npm run build
```

---

## 10. Resumen de Componentes

| Componente      | Puerto | Comando                                    | Función            |
| --------------- | ------ | ------------------------------------------ | ------------------ |
| Backend API     | 8000   | `uvicorn app.main:app`                     | API REST           |
| Worker          | -      | `python backend/worker/run_worker.py`      | Genera alertas     |
| Analysis Worker | -      | `python backend/worker/analysis_worker.py` | Análisis con IA    |
| Agent           | -      | `python -m agent run`                      | Recolecta métricas |
| Dashboard       | 5173   | `npm run dev`                              | UI React           |
| PostgreSQL      | 5432   | -                                          | Base de datos      |

---

## 11. Orden de Inicio Recomendado

1. **PostgreSQL** (debe estar corriendo)
2. **Backend API** (Terminal 1)
3. **Worker** (Terminal 2)
4. **Analysis Worker** (Terminal 3) - Opcional, solo si usas análisis de IA
5. **Agent** (Terminal 4)
6. **Dashboard** (Terminal 5)

Espera unos segundos entre cada inicio para que los servicios se conecten correctamente.
