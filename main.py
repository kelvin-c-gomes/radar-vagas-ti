import os
import json
import requests
from google import genai

GEMINI_API_KEY = os.environ["GEMINI_API_KEY"]
SERPER_API_KEY = os.environ["SERPER_API_KEY"]
TELEGRAM_TOKEN = os.environ["TELEGRAM_TOKEN"]
TELEGRAM_CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]

ARQUIVO_MEMORIA = "vagas_vistas.json"

# Buscas ampliadas cobrindo os principais portais de estágio e tech do Brasil
QUERIES_BUSCA = [
    '("estágio" OR "estagiário") ("TI" OR "desenvolvimento" OR "software" OR "dados") ("remoto" OR "home office")',
    'site:gupy.io ("estágio" OR "estagiário") ("tecnologia" OR "desenvolvedor" OR "sistemas" OR "dados") ("remoto" OR "home office")',
    'site:linkedin.com/jobs ("estágio" OR "estagiário") ("TI" OR "programação" OR "web" OR "python" OR "php") "remoto"',
    '(site:ciee.org.br OR site:solides.com.br OR site:greenhouse.io OR site:vagas.com.br) ("estágio" OR "estagiário") ("TI" OR "tecnologia" OR "sistemas") ("remoto" OR "home office")'
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
            "tbs": "qdr:w"  # Últimos 7 dias (garante volume bom de vagas reais)
        }
        
        try:
            resposta = requests.post(url, headers=headers, json=payload, timeout=15)
            print(f"Status Serper: {resposta.status_code}")
            if resposta.status_code == 200:
                resultados = resposta.json().get("organic", [])
                print(f"Resultados retornados nesta query: {len(resultados)}")
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
    Você é um recrutador especialista em tecnologia filtrando oportunidades para um estudante de Análise e Desenvolvimento de Sistemas (ADS).
    Analise a lista de resultados de busca abaixo e selecione vagas reais e ativas de ESTÁGIO em TI/Tecnologia que sejam REMOTAS (home office) ou híbridas.

    Regras de filtro:
    - Aceite vagas de estágio em desenvolvimento (web, backend, frontend, mobile), dados, QA, suporte técnico, infraestrutura, segurança ou IA.
    - Descarte artigos de blog, cursos, vídeos ou vagas claramente Sênior/Pleno.
    - Caso o título ou resumo indique estágio em TI remoto (mesmo que seja uma página de portal de vagas), aprove.

    Para cada vaga aprovada, formate exatamente neste padrão (sem usar caracteres especiais quebrados):
    🔹 { "[Título da Vaga / Empresa]" }
    📌 Área/Stack: [Resumo curto das tecnologias ou área]
    🔗 Link: [URL exata]

    Se NENHUMA vaga passar no filtro, responda apenas a palavra: NENHUMA

    Lista de resultados encontrados:
    {json.dumps(vagas_brutas, ensure_ascii=False, indent=2)}
    """

    try:
        response = client.models.generate_content(
            model="gemini-3.8-flash",
            contents=prompt,
        )
        texto = response.text.strip()
        if texto == "NENHUMA" or not texto:
            return None
        return texto
    except Exception as e:
        print(f"Erro na chamada do Gemini: {e}")
        return None


def enviar_telegram(mensagem):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    for i in range(0, len(mensagem), 3900):
        payload = {
            "chat_id": TELEGRAM_CHAT_ID,
            "text": f"🚀 Novas Vagas de Estágio Remoto (TI)\n\n{mensagem[i:i+3900]}",
            "disable_web_page_preview": True
        }
        resp = requests.post(url, json=payload, timeout=15)
        print(f"Status envio Telegram: {resp.status_code} | Resposta: {resp.text}")


def main():
    print("Iniciando varredura...")
    vagas_vistas = carregar_memoria()
    novas_vagas, vagas_vistas_atualizadas = buscar_vagas_google(vagas_vistas)
    
    print(f"Total de links inéditos encontrados: {len(novas_vagas)}")
    
    if novas_vagas:
        relatorio = filtrar_com_gemini(novas_vagas)
        if relatorio:
            print("Vagas relevantes filtradas! Enviando no Telegram...")
            enviar_telegram(relatorio)
        else:
            print("Nenhuma vaga passou no filtro do Gemini.")
            enviar_telegram("🤖 Teste do Robô: A busca funcionou, mas nenhuma vaga passou no filtro desta rodada.")
    else:
        print("Nenhum link novo encontrado.")
        enviar_telegram("⚠️ Teste do Robô: A busca retornou 0 links. Verifique a SERPER_API_KEY nos Secrets do GitHub.")
            
    salvar_memoria(vagas_vistas_atualizadas)
    print("Varredura concluída.")


if __name__ == "__main__":
    main()
