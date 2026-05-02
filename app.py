from fastapi import FastAPI, Request, Header, HTTPException
import os
import json
from openai import OpenAI
from typing import List, Dict

app = FastAPI()

# =========================
# VARIABLES DE ENTORNO
# =========================

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
TOKEN = os.getenv("BP_PROXY_TOKEN")

if not OPENAI_API_KEY:
    raise Exception("Falta OPENAI_API_KEY")

client = OpenAI(api_key=OPENAI_API_KEY)

# =========================
# MEMORIA SIMPLE
# =========================

LAST_ANALYSIS = None
LAST_DATA = None

# =========================
# HELPERS
# =========================

def clean_json(text):
    text = text.strip()
    if text.startswith("```"):
        text = text.replace("```json", "").replace("```", "").strip()
    return text

# =========================
# HEALTH
# =========================

@app.get("/")
def root():
    return {"status": "running", "app": "solar-om-agent"}

@app.get("/health")
def health():
    return {
        "status": "running",
        "has_analysis": LAST_ANALYSIS is not None
    }

# =========================
# ANALYZE
# =========================

@app.post("/analyze")
async def analyze(data: List[Dict], x_bp_token: str = Header(None)):

    global LAST_ANALYSIS, LAST_DATA

    # 🔒 Seguridad opcional (desactivada para demo)
    # if x_bp_token != TOKEN:
    #     raise HTTPException(status_code=401, detail="Unauthorized")

    prompt = f"""
Eres un sistema experto en O&M solar.

Analiza esta serie temporal:

{data}

Detecta:
- anomalías
- caída de potencia
- incoherencia irradiancia vs potencia
- desviaciones por equipo
- temperatura elevada
- causa probable
- impacto
- recomendación

Criterios:
- Irradiancia estable + caída de potencia → problema interno
- Temperatura > 80°C → crítica
- Comparar equipos entre sí

Devuelve SOLO JSON:

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
            {"role": "system", "content": "Responde solo JSON válido."},
            {"role": "user", "content": prompt}
        ],
        temperature=0
    )

    result_text = response.choices[0].message.content

    try:
        result_json = json.loads(clean_json(result_text))
    except:
        return {"status": "error", "raw": result_text}

    # 💾 guardar memoria
    LAST_ANALYSIS = result_json
    LAST_DATA = data

    return {
        "status": "ok",
        "analysis": result_json
    }

# =========================
# CHAT
# =========================

@app.post("/chat")
async def chat(body: dict, x_bp_token: str = Header(None)):

    global LAST_ANALYSIS, LAST_DATA

    # 🔒 Seguridad opcional (alineada con analyze)
    # if x_bp_token != TOKEN:
    #     raise HTTPException(status_code=401, detail="Unauthorized")

    question = body.get("question")
    context = body.get("analysis") or LAST_ANALYSIS

    if not context:
        return {
            "status": "error",
            "message": "No hay análisis previo cargado. Ejecuta primero /analyze."
        }

    prompt = f"""
Eres jefe O&M solar.

ANÁLISIS:
{context}

DATOS ORIGINALES:
{LAST_DATA}

PREGUNTA:
{question}

INSTRUCCIONES:
- Usa SOLO el análisis y datos
- No inventes
- Prioriza acción técnica
- Sé concreto

RESPUESTA:
"""

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "Responde como experto técnico."},
            {"role": "user", "content": prompt}
        ],
        temperature=0.2
    )

    return {
        "status": "ok",
        "respuesta": response.choices[0].message.content
    }

# =========================
# LEGACY
# =========================

@app.post("/legacy-eval")
async def evaluar(request: Request, x_bp_token: str = Header(None)):

    # 🔒 opcional
    # if x_bp_token != TOKEN:
    #     raise HTTPException(status_code=401, detail="Unauthorized")

    body = await request.json()

    prompt = f"""
Evalúa este registro:

{body}

Reglas:
- Temp > 80 → ALTA
- 70-80 → MEDIA

Devuelve JSON.
"""

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        temperature=0
    )

    return {
        "status": "ok",
        "evaluacion": response.choices[0].message.content
    }
