import feedparser
from google import genai
from pymongo import MongoClient
from datetime import datetime, timezone
import time

# Chaves oficiais mantidas!
MINHA_CHAVE_GEMINI = ""
MINHA_CONEXAO_MONGO = ""

client_gemini = genai.Client(api_key=MINHA_CHAVE_GEMINI)

# Coleções do Banco de Dados
colecao_noticias = None
colecao_analises = None

try:
    client_mongo = MongoClient(MINHA_CONEXAO_MONGO)
    db = client_mongo['terminal_db']
    colecao_noticias = db['noticias']
    # Nova coleção apenas para guardar as análises diárias do Marco Vieira
    colecao_analises = db['analises']
    print("✅ Conexão com o MongoDB Atlas estabelecida com sucesso!")
except Exception as e:
    print(f"❌ Erro crítico ao conectar no MongoDB: {e}")

def rodar_coleta_e_salvar_lote():
    if colecao_noticias is None or colecao_analises is None:
        print("❌ A coleta foi cancelada porque o banco de dados não está conectado.")
        return

    print("⚡ Iniciando rotina oficial do Terminal Bitcoin...")
    
    url_rss = "https://news.google.com/rss/search?q=bitcoin&hl=pt-BR&gl=BR&ceid=BR:pt-419"
    feed = feedparser.parse(url_rss)
    
    if not feed.entries:
        print("❌ Nenhuma notícia encontrada no feed.")
        return
        
    noticias_principais = feed.entries[:5]
    print(f"📌 Encontramos {len(feed.entries)} notícias. Vamos processar as {len(noticias_principais)} principais.\n")
    
    # Lista vazia que vai guardar todos os títulos para a análise macro depois
    titulos_do_dia = []
    
    for indice, item in enumerate(noticias_principais, 1):
        titulo = item.title
        link = item.link
        
        # Guarda o título na nossa lista
        titulos_do_dia.append(titulo)
        
        print(f"🔄 [{indice}/5] Processando: {titulo}")
        
        comando_noticia = f"""
        Com base no título da notícia de Bitcoin abaixo, faça duas coisas:
        1. Crie um resumo ultra curto em exatamente 2 tópicos (bullet points) em português.
        2. Defina o sentimento do mercado em apenas uma palavra: (Otimista, Pessimista ou Neutro).
        
        Título: {titulo}
        """
        
        try:
            resposta = client_gemini.models.generate_content(
                model='gemini-2.5-flash',
                contents=comando_noticia,
            )
            resultado_ia = resposta.text
            
            documento_noticia = {
                "titulo_original": titulo,
                "link_original": link,
                "data_coleta": datetime.now(timezone.utc),
                "resumo_ia": resultado_ia,
                "desenvolvido_por": "Scarface Tec"
            }
            
            colecao_noticias.insert_one(documento_noticia)
            print(f"   ✅ Salva no MongoDB Atlas!")
            
            time.sleep(2) # Pausa rápida
            
        except Exception as e:
            print(f"   ❌ Erro ao processar esta notícia: {e}")
            
    # 🧠 --- HORA DA ANÁLISE MACRO (110%) ---
    print("\n🧠 Gerando a Análise Macro de Mercado para Marco Vieira...")
    
    # Junta todos os títulos capturados em um único bloco de texto
    bloco_de_noticias = "\n".join([f"- {t}" for t in titulos_do_dia])
    
    comando_macro = f"""
    Você é um especialista sênior em análise de mercado de criptomoedas, gerando um relatório diário automatizado para o consultor Marco Vieira.
    Com base em todas as principais notícias coletadas nas últimas 24 horas listadas abaixo, escreva um parágrafo analítico, curto e muito profissional (de 3 a 5 linhas), resumindo o cenário atual e o impacto no preço do Bitcoin.
    Ao final do texto, adicione uma linha isolada escrita: "Sentimento Geral: [Sentimento]" (onde [Sentimento] deve ser apenas Otimista, Pessimista ou Neutro).

    Notícias Coletadas:
    {bloco_de_noticias}
    """
    
    try:
        resposta_macro = client_gemini.models.generate_content(
            model='gemini-2.5-flash',
            contents=comando_macro,
        )
        analise_texto = resposta_macro.text
        
        # Documento da análise macro
        documento_analise = {
            "texto_analise": analise_texto,
            "data_analise": datetime.now(timezone.utc),
            "desenvolvido_por": "Scarface Tec",
            "curadoria": "Marco Vieira"
        }
        
        # Salva na nova coleção do MongoDB
        resultado_macro = colecao_analises.insert_one(documento_analise)
        print("✅ Análise Macro gerada e salva com sucesso no MongoDB Atlas!")
        print(f"   ID da Análise: {resultado_macro.inserted_id}")
        
    except Exception as e:
        print(f"❌ Erro ao gerar a análise macro: {e}")
        
    print("\n🚀 Varredura diária e inteligência macro concluídas com sucesso!")

if __name__ == "__main__":
    rodar_coleta_e_salvar_lote()