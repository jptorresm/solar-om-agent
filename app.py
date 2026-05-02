from fastapi import FastAPI, Request, Header, HTTPException
from fastapi.staticfiles import StaticFiles
import requests
import os
from openai import OpenAI

app = FastAPI()

# =========================
# VARIABLES DE ENTORNO
# =========================

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
TOKEN = os.getenv("BP_PROXY_TOKEN")
SHEETS_WEBHOOK = os.getenv("SHEETS_WEBHOOK")
print("OPENAI_API_KEY cargada:", OPENAI_API_KEY[:12] if OPENAI_API_KEY else "None")
print("OPENAI_API_KEY largo:", len(OPENAI_API_KEY) if OPENAI_API_KEY else 0)
if not TOKEN:
    raise Exception("Falta BP_PROXY_TOKEN")

client = OpenAI(api_key=OPENAI_API_KEY)

# =========================
# MEMORIA SIMPLE (demo)
# =========================

LAST_ANALYSIS = {}

# =========================
# HEALTH CHECK
# =========================

@app.get("/health")
def health():
    return {"status": "running"}

# =========================
# ANALYZE (NUEVO)
# =========================

from typing import List, Dict

@app.post("/analyze")
async def analyze(data: List[Dict], x_bp_token: str = Header(None)):

    global LAST_ANALYSIS

    # Seguridad desactivada temporalmente para prueba
    # if x_bp_token != TOKEN:
    #     raise HTTPException(status_code=401, detail="Unauthorized")

    prompt = f"""
Eres un sistema avanzado de monitoreo O&M solar, actuando como ingeniero experto.

Analiza los siguientes datos como una serie temporal operacional de planta solar:

{data}

Debes detectar:
- anomalías
- tendencias
- caídas de potencia
- incoherencias entre irradiancia y potencia
- temperatura elevada
- desviaciones por equipo
- causa probable
- impacto operacional
- recomendación concreta de mantenimiento

Criterios:
- Si la irradiancia sube o se mantiene estable y la potencia cae, es una anomalía.
- Si un equipo se comporta peor que otros bajo condiciones similares, debe marcarse.
- Si la temperatura supera 80°C, la criticidad debe ser crítica.
- Prioriza por impacto en generación y riesgo operacional.

Devuelve SOLO JSON válido, sin markdown, sin explicación adicional:

{{
  "resumen": {{
    "total_alertas": 0,
    "criticas": 0,
    "medias": 0,
    "bajas": 0,
    "riesgo_principal": "texto"
  }},
  "alertas": [
    {{
      "timestamp": "texto",
      "equipo": "texto",
      "criticidad": "critica/media/baja",
      "anomalia": "texto",
      "causa_probable": "texto",
      "impacto": "texto",
      "recomendacion": "texto",
      "prioridad": 1
    }}
  ]
}}
"""

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {
                "role": "system",
                "content": "Responde siempre solo con JSON válido. No uses markdown."
            },
            {
                "role": "user",
                "content": prompt
            }
        ],
        temperature=0
    )

    import json

    result_text = response.choices[0].message.content

    try:
        result_json = json.loads(result_text)
    except Exception:
        return {
            "status": "error",
            "raw": result_text
        }

    LAST_ANALYSIS = {
        "data": data,
        "analysis": result_json
    }

    return {
        "status": "ok",
        "analysis": result_json
    }
# =========================
# CHAT EXPERTO (MEJORADO)
# =========================

@app.post("/chat")
async def chat(body: dict, x_bp_token: str = Header(None)):

    if x_bp_token != TOKEN:
        raise HTTPException(status_code=401, detail="Unauthorized")

    question = body.get("question", "")

    context = LAST_ANALYSIS.get("analysis", "Sin análisis previo")

    prompt = f"""
Eres un jefe de O&M solar.

Contexto del sistema:
{context}

Pregunta del usuario:
{question}

Responde como experto:
- claro
- directo
- accionable
- priorizando impacto en producción

No inventes datos fuera del contexto.
"""

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.3
    )

    answer = response.choices[0].message.content

    return {
        "status": "ok",
        "respuesta": answer
    }

# =========================
# ENDPOINT LEGACY (compatibilidad)
# =========================

@app.post("/legacy-eval")
async def evaluar(request: Request, x_bp_token: str = Header(None)):

    if x_bp_token != TOKEN:
        raise HTTPException(status_code=401, detail="Unauthorized")

    body = await request.json()

    prompt = f"""
Evalúa este registro solar:

{body}

Reglas:
- Temperatura > 80°C → ALTA
- 70-80 → MEDIA

Devuelve JSON:
{{
  "alerta": true/false,
  "criticidad": "...",
  "mensaje": "...",
  "recomendacion": "..."
}}
"""

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        temperature=0
    )

    result_text = response.choices[0].message.content

    if SHEETS_WEBHOOK:
        try:
            requests.post(SHEETS_WEBHOOK, json={
                "timestamp": body.get("timestamp"),
                "resultado": result_text
            })
        except Exception as e:
            print("Error Sheets:", e)

    return {
        "status": "ok",
        "evaluacion": result_text
    }
