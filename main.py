import os
import json
import time
import requests
from google import genai

GEMINI_API_KEY = os.environ["GEMINI_API_KEY"]
SERPER_API_KEY = os.environ["SERPER_API_KEY"]
TELEGRAM_TOKEN = os.environ["TELEGRAM_TOKEN"]
TELEGRAM_CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]

ARQUIVO_MEMORIA = "vagas_vistas.json"

QUERIES_BUSCA = [
    'vaga estagio TI remoto home office',
    'vaga estagio desenvolvimento software remoto',
    'site:gupy.io estagio tecnologia remoto',
    'site:linkedin.com/jobs estagio TI remoto',
    'vaga estagio TI tecnologia informatica "Marilia"',
    'estagio desenvolvimento sistemas "Marilia" SP'
]


def carregar_memoria():
    if os.path.exists(ARQUIVO_MEMORIA):
        with open(ARQUIVO_MEMORIA, "r", encoding="utf-8") as f:
            return set(json.load(f))
    return set()


def salvar_memoria(vagas_vistas):
    with open(ARQUIVO_MEMORIA, "w", encoding="utf-8") as f:
        json.dump(list(vagas_vistas), f, indent=2, ensure_ascii=False)


def buscar_vagas_google(vagas_vistas):
    url = "https://google.serper.dev/search"
    headers = {
        "X-API-KEY": SERPER_API_KEY,
        "Content-Type": "application/json"
    }
    
    novas_vagas = []
    
    for query in QUERIES_BUSCA:
        payload = {
            "q": query,
            "gl": "br",
            "hl": "pt-br",
            "num": 15,
            "tbs": "qdr:m"
        }
        
        try:
            resposta = requests.post(url, headers=headers, json=payload, timeout=15)
            if resposta.status_code == 200:
                resultados = resposta.json().get("organic", [])
                for item in resultados:
                    link = item.get("link")
                    if link and link not in vagas_vistas:
                        vagas_vistas.add(link)
                        novas_vagas.append({
                            "titulo": item.get("title", ""),
                            "link": link,
                            "resumo": item.get("snippet", "")
                        })
        except Exception as e:
            print(f"Erro na busca: {e}")
            
    return novas_vagas, vagas_vistas


def filtrar_com_gemini(vagas_brutas):
    if not vagas_brutas:
        return None

    client = genai.Client(api_key=GEMINI_API_KEY)
    
    prompt = f"""
    Você é um assistente de carreira para um estudante de Análise e Desenvolvimento de Sistemas (ADS) de MARÍLIA - SP.
    Abaixo está uma lista de links encontrados agora no Google sobre estágios em TI.
    
    Sua tarefa é selecionar NO MÁXIMO AS 5 MELHORES oportunidades reais da lista (priorizando sempre vagas em Marília/SP primeiro, e depois as melhores vagas 100% remotas em desenvolvimento/TI).
    - Descarte APENAS notícias, artigos de blog ("como conseguir estágio"), cursos pagos ou vagas Sênior/Pleno.

    Formatação obrigatória:
    - Se houver qualquer oportunidade em MARÍLIA - SP (presencial, híbrida ou remota), coloque NO TOPO com este destaque:
      🚨🔥 OPORTUNIDADE EM MARÍLIA/SP! 🔥🚨
      🏙️ [Título / Empresa ou Portal]
      📍 Modalidade: [Presencial / Híbrido / Remoto - Marília/SP]
      📌 Detalhes: [Resumo curto]
      🔗 Link: [URL exata]

    - Para as demais oportunidades remotas em TI:
      🔹 [Título / Empresa ou Portal]
      📌 Detalhes: [Resumo curto]
      🔗 Link: [URL exata]

    Lista de resultados:
    {json.dumps(vagas_brutas[:50], ensure_ascii=False, indent=2)}
    """

    modelos = ["gemini-3.8-flash", "gemini-3.8-flash-lite", "gemini-3-flash"]
    ultimo_erro = ""

    for modelo in modelos:
        for tentativa in range(2):
            try:
                response = client.models.generate_content(
                    model=modelo,
                    contents=prompt,
                )
                return response.text.strip()
            except Exception as e:
                ultimo_erro = str(e)
                print(f"Falha no modelo {modelo} (tentativa {tentativa+1}): {e}")
                time.sleep(3)

    return f"⚠️ Todos os modelos do Gemini estão sobrecarregados no momento. Último erro: {ultimo_erro}"


def enviar_telegram(mensagem):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    for i in range(0, len(mensagem), 3900):
        payload = {
            "chat_id": TELEGRAM_CHAT_ID,
            "text": f"🚀 Radar de Estágios TI\n\n{mensagem[i:i+3900]}",
            "disable_web_page_preview": True
        }
        requests.post(url, json=payload, timeout=15)


def main():
    vagas_vistas = carregar_memoria()
    novas_vagas, vagas_vistas_atualizadas = buscar_vagas_google(vagas_vistas)
    
    if novas_vagas:
        relatorio = filtrar_com_gemini(novas_vagas)
        if relatorio:
            enviar_telegram(relatorio)
    else:
        enviar_telegram("⚠️ Nenhum link inédito nesta rodada (todos já estão em vagas_vistas.json).")
            
    salvar_memoria(vagas_vistas_atualizadas)


if __name__ == "__main__":
    main()
