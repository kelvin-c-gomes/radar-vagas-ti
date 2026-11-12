# Radar de Estágios em TI (Marília/SP & Remoto)

Automação em Python que varre a web a cada 3 horas em busca de novas vagas de estágio em tecnologia, filtra os resultados usando IA e envia apenas as melhores oportunidades direto no meu Telegram.

Criei esse projeto para resolver um problema real: ficar abrindo LinkedIn, Gupy, CIEE e portais de empresas várias vezes ao dia para não perder vagas recém-abertas — principalmente aqui na região de Marília/SP ou oportunidades 100% remotas.

---

## Como funciona na prática

O fluxo roda de forma totalmente autônoma na nuvem, sem depender do meu computador ligado:

1. **Agendamento (GitHub Actions):** Um workflow configurado com `cron` dispara o script automaticamente a cada 3 horas (além de permitir execução manual quando eu quiser testar).
2. **Busca na Web (Serper API):** O script faz requisições para a API do Serper buscando vagas publicadas recentemente em plataformas de recrutamento (LinkedIn, Gupy, Sólides, Vagas.com, CIEE) e em empresas de tecnologia da região de Marília/Pompeia (como Tray, TOTVS, Senior, Life, Jacto, etc.).
3. **Controle de Histórico (`vagas_vistas.json`):** Antes de processar qualquer link, o código compara as URLs encontradas com um arquivo JSON salvo no próprio repositório. Se o link já foi analisado antes, ele é descartado na hora para evitar notificações repetidas. Após cada rodada, o GitHub Actions faz o commit automático das novas URLs no histórico.
4. **Curadoria com IA (Google Gemini API):** Os links inéditos são enviados para o Gemini com um prompt estruturado que descarta vagas antigas, links suspeitos ou cargos fora do perfil de estágio, selecionando no máximo as 5 melhores oportunidades e destacando com alerta máximo qualquer vaga em Marília/SP. Implementei também um fallback automático entre modelos (`flash` e `flash-lite`) para evitar falhas caso algum modelo passe por instabilidade ou pico de demanda.
5. **Notificação (Telegram Bot API):** O resultado filtrado é enviado direto para o meu chat pessoal via bot do Telegram.

---

## Tecnologias e ferramentas utilizadas

- **Linguagem:** Python 3
- **APIs:** Serper (Google Search), Google Gemini (`google-genai`), Telegram Bot API
- **Automação & CI/CD:** GitHub Actions
- **Persistência simples:** Arquivo JSON versionado no repositório
- **Segurança:** Chaves de API e tokens isolados via GitHub Repository Secrets

---

## Estrutura do repositório

```text
├── .github/
│   └── workflows/
│       └── radar.yml      # Configuração do agendamento (cron) e commit automático do histórico
├── main.py                # Script principal (busca, filtro de duplicatas, IA e envio no Telegram)
├── vagas_vistas.json      # Memória de URLs já processadas
├── requirements.txt       # Dependências do projeto (requests, google-genai)
└── README.md
