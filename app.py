from fastapi import FastAPI, Request, Header, HTTPException
import requests
import os
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

app = FastAPI()

client = OpenAI(api_key=os.getenv("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"))

SHEETS_WEBHOOK = os.getenv("SHEETS_WEBHOOK")
TOKEN = os.getenv("BP_PROXY_TOKEN")


@app.post("/chat")
async def evaluar(request: Request, x_bp_token: str = Header(None)):

    # Seguridad básica (igual que Buscaprop)
    if x_bp_token != TOKEN:
        raise HTTPException(status_code=401, detail="Unauthorized")

    body = await request.json()

    prompt = f"""
Eres un sistema de monitoreo O&M solar.

Evalúa este registro:
{body}

Reglas:
- Temperatura > 80°C → criticidad ALTA
- Temperatura entre 70-80 → MEDIA
- Caída de potencia relevante → MEDIA
- Inconsistencias → alerta

Responde SOLO en JSON:

{{
  "alerta": true/false,
  "criticidad": "BAJA/MEDIA/ALTA",
  "mensaje": "explicación breve",
  "recomendacion": "acción concreta"
}}
"""

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        temperature=0
    )

    result_text = response.choices[0].message.content

    # 🔥 MVP: reenvío directo sin parsear
    try:
        requests.post(SHEETS_WEBHOOK, json={
            "timestamp": body.get("timestamp"),
            "resultado": result_text
        })
    except Exception as e:
        print("Error enviando a Sheets:", e)

    return {
        "status": "ok",
        "evaluacion": result_text
    }


@app.get("/")
def health():
    return {"status": "running"}
