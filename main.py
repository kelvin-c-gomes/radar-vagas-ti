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

# Aqui é para fazer buscas em empresas de Marília-SP e também buscar por estágios remoto de TI em todo o Brasil.
QUERIES_BUSCA = [
    'site:linkedin.com/jobs/view "estágio" ("TI" OR "desenvolvimento" OR "software" OR "dados") "remoto"',
    'site:gupy.io "estágio" ("tecnologia" OR "desenvolvimento" OR "dados" OR "sistemas") "remoto"',
    '(site:greenhouse.io OR site:lever.co OR site:solides.com.br OR site:vagas.com.br) "estágio" ("TI" OR "desenvolvimento" OR "software") "remoto"',
    '("estágio" OR "estagiário") ("TI" OR "tecnologia" OR "sistemas" OR "desenvolvimento" OR "suporte") ("Marília" OR "Pompeia") -site:instagram.com -site:facebook.com',
    '(site:gupy.io OR site:linkedin.com/jobs OR site:ciee.org.br) ("Tray" OR "TOTVS" OR "Senior" OR "Life" OR "Dori" OR "Marilan" OR "Jacto" OR "Unimar") ("estágio" OR "estagiário") ("TI" OR "tecnologia" OR "desenvolvimento" OR "sistemas" OR "dados")'
]
]

# Aqui ele bloqueia todos os dominios que possam gerar spam e links antigos
DOMINIOS_BLOQUEADOS = [
    "instagram.com", "facebook.com", "tiktok.com", "youtube.com",
    "jobgether.com", "jooble.org", "bebee.com", "adzuna.com.br", "talent.com"
]


def carregar_memoria():
    if os.path.exists(ARQUIVO_MEMORIA):
        with open(ARQUIVO_MEMORIA, "r", encoding="utf-8") as f:
            return set(json.load(f))
    return set()


def salvar_memoria(vagas_vistas):
    with open(ARQUIVO_MEMORIA, "w", encoding="utf-8") as f:
        json.dump(list(vagas_vistas), f, indent=2, ensure_ascii=False)


def link_valido(url):
    url_lower = url.lower()
    return not any(dominio in url_lower for dominio in DOMINIOS_BLOQUEADOS)


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
            "tbs": "qdr:m"  # Últimos 30 dias: tempo ideal para o Google indexar Gupy e LinkedIn
        }
        
        try:
            resposta = requests.post(url, headers=headers, json=payload, timeout=15)
            if resposta.status_code == 200:
                resultados = resposta.json().get("organic", [])
                print(f"Query '{query[:30]}...' -> {len(resultados)} resultados")
                for item in resultados:
                    link = item.get("link")
                    if link and link not in vagas_vistas and link_valido(link):
                        vagas_vistas.add(link)
                        novas_vagas.append({
                            "titulo": item.get("title", ""),
                            "link": link,
                            "resumo": item.get("snippet", ""),
                            "data": item.get("date", "Recente")
                        })
        except Exception as e:
            print(f"Erro na busca: {e}")
            
    return novas_vagas, vagas_vistas


def obter_modelos_ativos(client):
    modelos_validos = []
    try:
        for m in client.models.list():
            nome = m.name.replace("models/", "")
            acoes = getattr(m, "supported_generation_methods", []) or getattr(m, "supported_actions", [])
            if "flash" in nome.lower() and ("generateContent" in str(acoes) or not acoes):
                modelos_validos.append(nome)
    except Exception:
        pass
    
    prioridade = ["gemini-3.8-flash", "gemini-3.8-flash-lite", "gemini-3-flash-preview"]
    ordenados = [m for m in prioridade if m in modelos_validos]
    for m in modelos_validos:
        if m not in ordenados:
            ordenados.append(m)
            
    return ordenados if ordenados else prioridade


def filtrar_com_gemini(vagas_brutas):
    if not vagas_brutas:
        return None

    client = genai.Client(api_key=GEMINI_API_KEY)
    
    prompt = f"""
    Você é um filtro automatizado de vagas de estágio em TI para um estudante de ADS de Marília-SP.
    Analise os links reais encontrados e selecione NO MÁXIMO AS 5 MELHORES oportunidades legítimas.

    Regras rígidas:
    - NÃO escreva saudação, introdução, despedida ou dicas. Entregue APENAS a lista de vagas.
    - Descarte vagas que mencionem datas antigas (2024 ou 2025), vagas encerradas, vagas Pleno/Sênior ou fora de TI.
    - Aceite links diretos de vagas (LinkedIn, Gupy, Greenhouse, Sólides, Vagas.com, CIEE, InfoJobs) e páginas ativas de recrutamento de empresas de Marília/SP.
    - Priorize 100% qualquer vaga em MARÍLIA - SP no topo.

    Formato obrigatório:
    - Se for em MARÍLIA - SP:
      🚨🔥 VAGA EM MARÍLIA/SP! 🔥🚨
      🏢 [Cargo] | [Empresa]
      📍 [Presencial / Híbrido / Remoto - Marília/SP]
      📌 [Tecnologias/Resumo em 1 linha]
      🔗 [URL exata]

    - Se for REMOTA (Brasil):
      🔹 [Cargo] | [Empresa]
      📌 [Tecnologias/Resumo em 1 linha]
      🔗 [URL exata]

    Se absolutamente NENHUMA vaga passar, responda apenas: NENHUMA

    Vagas encontradas:
    {json.dumps(vagas_brutas[:45], ensure_ascii=False, indent=2)}
    """

    modelos = obter_modelos_ativos(client)
    for modelo in modelos:
        try:
            response = client.models.generate_content(
                model=modelo,
                contents=prompt,
            )
            texto = response.text.strip()
            return None if texto == "NENHUMA" else texto
        except Exception as e:
            print(f"Falha no modelo {modelo}: {e}")
            time.sleep(2)

    return None


def enviar_telegram(mensagem):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    for i in range(0, len(mensagem), 3900):
        payload = {
            "chat_id": TELEGRAM_CHAT_ID,
            "text": f"🎯 Radar de Estágios TI\n\n{mensagem[i:i+3900]}",
            "disable_web_page_preview": True
        }
        requests.post(url, json=payload, timeout=15)


def main():
    vagas_vistas = carregar_memoria()
    novas_vagas, vagas_vistas_atualizadas = buscar_vagas_google(vagas_vistas)
    print(f"Total de links válidos inéditos: {len(novas_vagas)}")
    
    if novas_vagas:
        relatorio = filtrar_com_gemini(novas_vagas)
        if relatorio:
            enviar_telegram(relatorio)
        else:
            enviar_telegram(f"🤖 Varredura feita ({len(novas_vagas)} links analisados), mas nenhuma vaga nova passou no filtro.")
    else:
        enviar_telegram("🤖 Varredura feita: 0 links novos encontrados nesta rodada.")
            
    salvar_memoria(vagas_vistas_atualizadas)


if __name__ == "__main__":
    main()
