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

    global LAST_ANALYSIS  # ← PRIMERA línea dentro de la función

    # if x_bp_token != TOKEN:
    #     raise HTTPException(status_code=401, detail="Unauthorized")

    prompt = f"""
    ...
    """

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        temperature=0
    )

    import json

    result_text = response.choices[0].message.content

    try:
        result_json = json.loads(result_text)
    except:
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
async def chat(request: Request, x_bp_token: str = Header(None)):

    if x_bp_token != TOKEN:
        raise HTTPException(status_code=401, detail="Unauthorized")

    body = await request.json()
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
