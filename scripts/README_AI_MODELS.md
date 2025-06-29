# 🤖 Script de Gestión de Modelos de IA

## 📖 Descripción

Este script permite gestionar fácilmente los modelos de IA soportados en el sistema de monitoreo de SapiensAI. Puedes agregar nuevos modelos, verificar soporte y ver la lista completa sin necesidad de tocar el código fuente.

## 🚀 Uso Rápido

### Modo Interactivo (Recomendado para principiantes)
```bash
python scripts/add_ai_model.py
```

### Agregar Modelo Específico
```bash
python scripts/add_ai_model.py --provider gemini --model gemini-3.0-flash --input-price 0.0005 --output-price 0.002
```

### Ver Modelos Soportados
```bash
python scripts/add_ai_model.py --list
```

### Verificar Soporte de un Modelo
```bash
python scripts/add_ai_model.py --check --provider gemini --model gemini-2.5-flash
```

### Agregar Modelos en Lote
```bash
python scripts/add_ai_model.py --batch
```

## 📋 Comandos Disponibles

| Comando | Descripción | Ejemplo |
|---------|-------------|---------|
| `--list` | Lista todos los modelos soportados | `python scripts/add_ai_model.py --list` |
| `--check` | Verifica si un modelo está soportado | `python scripts/add_ai_model.py --check --provider gemini --model gemini-2.5-flash` |
| `--batch` | Agrega múltiples modelos predefinidos | `python scripts/add_ai_model.py --batch` |
| Sin argumentos | Modo interactivo | `python scripts/add_ai_model.py` |

## 🎯 Casos de Uso Comunes

### 1. Agregar Nuevos Modelos Gemini 2.5
```bash
# Gemini 2.5 Flash Preview
python scripts/add_ai_model.py \
  --provider gemini \
  --model gemini-2.5-flash-preview-04-17 \
  --input-price 0.0003 \
  --output-price 0.0025

# Gemini 2.5 Pro Preview
python scripts/add_ai_model.py \
  --provider gemini \
  --model gemini-2.5-pro-preview-05-06 \
  --input-price 0.00125 \
  --output-price 0.01
```

### 2. Agregar Modelos Experimentales
```bash
# Modelo experimental con precios estimados
python scripts/add_ai_model.py \
  --provider openai \
  --model gpt-5-preview \
  --input-price 0.02 \
  --output-price 0.08
```

### 3. Verificar Modelos Antes de Usar
```bash
# Verificar soporte antes de integrar
python scripts/add_ai_model.py --check --provider claude --model claude-4-opus
```

## 📊 Proveedores Soportados

### Gemini (Google)
- `gemini-2.5-*` - Serie más reciente
- `gemini-2.0-*` - Serie estable
- `gemini-1.5-*` - Serie legacy

### OpenAI
- `gpt-4o*` - Modelos multimodales
- `gpt-4*` - Serie GPT-4
- `gpt-3.5-*` - Serie legacy
- `o1-*` - Modelos de razonamiento

### Claude (Anthropic)
- `claude-3-5-*` - Serie más reciente
- `claude-3-*` - Serie estable
- `claude-2*` - Serie legacy

## 💰 Precios de Referencia (USD por 1K tokens)

### Gemini 2.5 (Actualizados)
```
gemini-2.5-pro: Input $0.00125, Output $0.01
gemini-2.5-flash: Input $0.0003, Output $0.0025
gemini-2.5-flash-lite: Input $0.0001, Output $0.0004
```

### OpenAI (Comunes)
```
gpt-4o: Input $0.005, Output $0.015
gpt-4o-mini: Input $0.00015, Output $0.0006
gpt-4: Input $0.03, Output $0.06
```

### Claude (Comunes)
```
claude-3-5-sonnet: Input $0.003, Output $0.015
claude-3-haiku: Input $0.00025, Output $0.00125
claude-3-opus: Input $0.015, Output $0.075
```

## 🔧 Modo Lote (Batch)

El modo lote agrega automáticamente estos modelos si no existen:

```python
# Modelos incluidos en --batch
batch_models = [
    # Nuevos Gemini 2.5
    ("gemini", "google/gemini-2.5-flash-preview", 0.0003, 0.0025),
    ("gemini", "gemini-2.5-flash-preview-04-17", 0.0003, 0.0025),
    ("gemini", "gemini-2.5-pro-preview-05-06", 0.00125, 0.01),
    
    # OpenAI recientes
    ("openai", "gpt-4o-2024-08-06", 0.0025, 0.01),
    ("openai", "gpt-4o-2024-11-20", 0.0025, 0.01),
    
    # Claude recientes
    ("claude", "claude-3-5-sonnet-latest", 0.003, 0.015),
    ("claude", "claude-3-5-haiku-latest", 0.0008, 0.004),
]
```

## ⚠️ Consideraciones Importantes

### Permisos
- El script modifica la configuración de MongoDB
- Asegúrate de tener permisos de escritura en la base de datos
- Los cambios afectan a todo el sistema

### Precios
- **Verifica siempre los precios oficiales** antes de agregar modelos
- Los precios pueden cambiar sin previo aviso
- Usa fuentes oficiales: [Google AI](https://ai.google.dev/pricing), [OpenAI](https://openai.com/pricing), [Anthropic](https://www.anthropic.com/pricing)

### Nombres de Modelos
- Usa nombres exactos como aparecen en las APIs
- Algunos modelos tienen múltiples variantes del nombre
- Ejemplo: `gemini-2.5-flash-preview-04-17` vs `google/gemini-2.5-flash-preview`

## 🐛 Resolución de Problemas

### Error: "No se pudo conectar a la base de datos"
```bash
# Verificar que MongoDB esté ejecutándose
mongo --eval "db.stats()"

# Verificar configuración en config.py
grep MONGODB config.py
```

### Error: "Campo obligatorio faltante"
```bash
# Asegúrate de incluir todos los campos requeridos
python scripts/add_ai_model.py \
  --provider gemini \
  --model tu-modelo \
  --input-price 0.001 \
  --output-price 0.002
```

### Error: "Proveedor no válido"
```bash
# Solo se permiten estos proveedores:
# gemini, openai, claude
```

## 📝 Ejemplos Completos

### Agregar Modelo Completamente Nuevo
```bash
# 1. Verificar si ya existe
python scripts/add_ai_model.py --check --provider gemini --model gemini-3.0

# 2. Si no existe, agregarlo
python scripts/add_ai_model.py \
  --provider gemini \
  --model gemini-3.0 \
  --input-price 0.001 \
  --output-price 0.003

# 3. Verificar que se agregó correctamente
python scripts/add_ai_model.py --list | grep gemini-3.0
```

### Mantenimiento Periódico
```bash
# Script de mantenimiento mensual
#!/bin/bash

echo "🔄 Actualizando modelos de IA..."

# Agregar modelos en lote
python scripts/add_ai_model.py --batch

# Verificar modelos críticos
python scripts/add_ai_model.py --check --provider gemini --model gemini-2.5-flash
python scripts/add_ai_model.py --check --provider openai --model gpt-4o
python scripts/add_ai_model.py --check --provider claude --model claude-3-5-sonnet

echo "✅ Mantenimiento completado"
```

## 🚀 Integración con CI/CD

### GitHub Actions
```yaml
name: Update AI Models
on:
  schedule:
    - cron: '0 9 1 * *'  # Primer día de cada mes
  workflow_dispatch:

jobs:
  update-models:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - name: Setup Python
        uses: actions/setup-python@v2
        with:
          python-version: '3.9'
      - name: Install dependencies
        run: pip install -r requirements.txt
      - name: Update AI models
        run: python scripts/add_ai_model.py --batch
```

---

**¿Necesitas ayuda?** Contacta al equipo de desarrollo o revisa la documentación completa en `docs/FRONTEND_INTEGRATION_AI_MONITORING.md` 