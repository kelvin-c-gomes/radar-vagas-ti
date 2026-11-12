import os
import json
import requests
from google import genai

GEMINI_API_KEY = os.environ["GEMINI_API_KEY"]
SERPER_API_KEY = os.environ["SERPER_API_KEY"]
TELEGRAM_TOKEN = os.environ["TELEGRAM_TOKEN"]
TELEGRAM_CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]

ARQUIVO_MEMORIA = "vagas_vistas.json"

# Inclui buscas remotas nacionais + busca dedicada para Marília/SP
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
            "num": 20,
            "tbs": "qdr:m"
        }
        
        try:
            resposta = requests.post(url, headers=headers, json=payload, timeout=15)
            print(f"Query: '{query}' | Status: {resposta.status_code}")
            if resposta.status_code == 200:
                resultados = resposta.json().get("organic", [])
                print(f"-> Resultados encontrados: {len(resultados)}")
                for item in resultados:
                    link = item.get("link")
                    if link and link not in vagas_vistas:
                        vagas_vistas.add(link)
                        novas_vagas.append({
                            "titulo": item.get("title", ""),
                            "link": link,
                            "resumo": item.get("snippet", ""),
                            "data": item.get("date", "Recente")
                        })
            else:
                print(f"Erro na API Serper: {resposta.text}")
        except Exception as e:
            print(f"Exceção na busca: {e}")
            
    return novas_vagas, vagas_vistas


def filtrar_com_gemini(vagas_brutas):
    if not vagas_brutas:
        return None

    client = genai.Client(api_key=GEMINI_API_KEY)
    
    prompt = f"""
    Você é um recrutador especialista em tecnologia filtrando oportunidades para um estudante de Análise e Desenvolvimento de Sistemas (ADS) que mora em MARÍLIA - SP.
    Analise a lista de resultados de busca abaixo e selecione oportunidades reais de ESTÁGIO em TI/Tecnologia.

    Critérios de aprovação:
    1. PRIORIDADE MÁXIMA (MARÍLIA/SP): Qualquer vaga de estágio em TI, desenvolvimento, suporte, dados ou sistemas localizada em MARÍLIA - SP (seja presencial, híbrida ou remota).
    2. REMOTAS (BRASIL): Vagas de estágio em TI/Tecnologia que sejam 100% REMOTAS (home office) ou híbridas flexíveis.
    3. Aceite tanto links de vagas individuais quanto páginas ativas de portais (Gupy, LinkedIn, CIEE, InfoJobs, Vagas.com) que listem vagas abertas de estágio em TI no perfil acima.
    4. Descarte apenas artigos de blog, cursos pagos, notícias ou vagas claramente Sênior/Pleno.

    Formatação obrigatória:
    - Se a vaga for em MARÍLIA - SP (presencial, híbrida ou remota), coloque ela NO TOPO da lista com este destaque exato:
      🚨🔥 OPORTUNIDADE EM MARÍLIA/SP! 🔥🚨
      🏙️ [Título da Vaga / Empresa]
      📍 Modalidade: [Presencial / Híbrido / Remoto - Marília/SP]
      📌 Área/Stack: [Resumo curto]
      🔗 Link: [URL exata]

    - Para as demais vagas remotas fora de Marília, use este padrão:
      🔹 [Título da Vaga / Empresa]
      📌 Área/Stack: [Resumo curto]
      🔗 Link: [URL exata]

    Se absolutamente NENHUMA oportunidade passar no filtro, responda apenas: NENHUMA

    Lista de resultados encontrados:
    {json.dumps(vagas_brutas, ensure_ascii=False, indent=2)}
    """

    try:
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
        )
        texto = response.text.strip()
        print(f"Resposta bruta do Gemini (primeiros 200 chars): {texto[:200]}")
        if texto == "NENHUMA" or not texto:
            return None
        return texto
    except Exception as e:
        print(f"ERRO CRÍTICO NA API DO GEMINI: {e}")
        return f"⚠️ Erro na API do Gemini: {e}"


def enviar_telegram(mensagem):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    for i in range(0, len(mensagem), 3900):
        payload = {
            "chat_id": TELEGRAM_CHAT_ID,
            "text": f"🚀 Radar de Estágios TI\n\n{mensagem[i:i+3900]}",
            "disable_web_page_preview": True
        }
        resp = requests.post(url, json=payload, timeout=15)
        print(f"Status envio Telegram: {resp.status_code}")


def main():
    print("Iniciando varredura...")
    vagas_vistas = carregar_memoria()
    novas_vagas, vagas_vistas_atualizadas = buscar_vagas_google(vagas_vistas)
    
    print(f"Total de links inéditos encontrados: {len(novas_vagas)}")
    
    if novas_vagas:
        relatorio = filtrar_com_gemini(novas_vagas)
        if relatorio:
            print("Enviando relatório no Telegram...")
            enviar_telegram(relatorio)
        else:
            print("Nenhuma vaga passou no filtro do Gemini.")
            enviar_telegram("🤖 Busca concluída: encontrou links, mas o Gemini descartou todos.")
    else:
        print("Nenhum link novo encontrado.")
            
    salvar_memoria(vagas_vistas_atualizadas)
    print("Varredura concluída.")


if __name__ == "__main__":
    main()
