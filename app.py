from flask import Flask, render_template, send_from_directory
from pymongo import MongoClient
from apscheduler.schedulers.background import BackgroundScheduler
import atexit
import feedparser
from google import genai
from datetime import datetime, timezone
import time
import os

app = Flask(__name__, template_folder='.')

# 📂 Rota para o Flask conseguir ler a sua pasta de imagens local
@app.route('/img/<path:filename>')
def custom_static(filename):
    return send_from_directory('img', filename)

# Chaves oficiais mantidas
MINHA_CHAVE_GEMINI = ""
MINHA_CONEXAO_MONGO = ""

client_gemini = genai.Client(api_key=MINHA_CHAVE_GEMINI)

try:
    client_mongo = MongoClient(MINHA_CONEXAO_MONGO)
    db = client_mongo['terminal_db']
    colecao_noticias = db['noticias']
    colecao_analises = db['analises']
    print("✅ Servidor Flask conectado com sucesso ao MongoDB Atlas!")
except Exception as e:
    print(f"❌ Erro ao conectar no MongoDB dentro do Flask: {e}")

def executar_tarefa_agendada():
    print("⏰ [Agendador] Iniciando varredura e atualização do portal...")
    
    url_rss = "https://news.google.com/rss/search?q=bitcoin&hl=pt-BR&gl=BR&ceid=BR:pt-419"
    feed = feedparser.parse(url_rss)
    
    if not feed.entries:
        print("❌ Nenhuma notícia encontrada no feed.")
        return
        
    noticias_principais = feed.entries[:5]
    titulos_do_dia = []
    
    for indice, item in enumerate(noticias_principais, 1):
        titulo = item.title
        link = item.link
        titulos_do_dia.append(titulo)
        
        noticia_existente = colecao_noticias.find_one({"link_original": link})
        if noticia_existente and "resumo_ia" in noticia_existente and "Aqui estão" not in noticia_existente["resumo_ia"]:
            print(f"⏭️ [{indice}/5] Notícia já processada anteriormente. Pulando chamada de IA.")
            continue
            
        print(f"🔄 [{indice}/5] Solicitando novo resumo para IA: {titulo}")
        
        comando_noticia = f"""
        Escreva um resumo ultra curto, de no máximo duas frases, sobre a notícia de Bitcoin abaixo.
        Atenção: Devolva APENAS o texto do resumo corrido. Não crie tópicos, não adicione marcadores, não faça introduções como "Aqui está o resumo" e NÃO inclua análise de sentimento. Seja direto.
        
        Título da Notícia: {titulo}
        """
        
        try:
            resposta = client_gemini.models.generate_content(
                model='gemini-2.5-flash',
                contents=comando_noticia,
            )
            resultado_ia = resposta.text.strip()
            documento_noticia = {
                "titulo_original": titulo,
                "link_original": link,
                "data_coleta": datetime.now(timezone.utc),
                "resumo_ia": resultado_ia,
                "desenvolvido_por": "Scarface Tec"
            }
            colecao_noticias.update_one({"link_original": link}, {"$set": documento_noticia}, upsert=True)
            time.sleep(3)
        except Exception as e:
            print(f"   ⚠️ Falha temporária na API do Gemini. Erro: {e}")
            
    # ANÁLISE MACRO COM SAUDAÇÃO E STATUS ATUALIZADOS
    print("🧠 Atualizando relatório macro consolidado...")
    bloco_de_noticias = "\n".join([f"- {t}" for t in titulos_do_dia])
    
    comando_macro = f"""
    Você é um especialista sênior em análise de mercado de criptomoedas, gerando um relatório diário automatizado para o consultor Marco Vieira.
    Instruções estritas de formatação:
    1. Comece o texto obrigatoriamente com a saudação exata: "Salve Sobrevivente!" (Sem usar "Prezado Marco").
    2. Escreva um parágrafo analítico, curto e muito profissional (de 3 a 5 linhas), resumindo o cenário atual e o impacto no preço do Bitcoin com base nas notícias fornecidas.
    3. Na última linha do texto, de forma isolada, escreva exatamente: "Sentimento Geral: [Sentimento]" (onde [Sentimento] deve ser apenas Otimista, Pessimista ou Neutro).

    Notícias Coletadas:
    {bloco_de_noticias}
    """
    
    try:
        resposta_macro = client_gemini.models.generate_content(
            model='gemini-2.5-flash',
            contents=comando_macro,
        )
        analise_texto = resposta_macro.text.strip()
        documento_analise = {
            "texto_analise": analise_texto,
            "data_analise": datetime.now(timezone.utc),
            "desenvolvido_por": "Scarface Tec",
            "curadoria": "Marco Vieira"
        }
        colecao_analises.insert_one(documento_analise)
        print("✅ Análise Macro atualizada com sucesso!")
    except Exception as e:
        print(f"   ⚠️ Falha ao gerar nova análise macro por limite de cota: {e}")

scheduler = BackgroundScheduler()
scheduler.add_job(func=executar_tarefa_agendada, trigger="interval", hours=1)
scheduler.start()
atexit.register(lambda: scheduler.shutdown())

@app.route("/")
def home():
    noticias_do_banco = list(colecao_noticias.find().sort("data_coleta", -1).limit(5))
    ultima_analise = colecao_analises.find_one(sort=[("data_analise", -1)])
    
    texto_analise_final = "Salve Sobrevivente!\n\nAguardando renovação da janela de cota diária da API para consolidação do relatório macro.\n\nSentimento Geral: Pessimista"
    if ultima_analise:
        texto_analise_final = ultima_analise.get("texto_analise", texto_analise_final)

    # 🛠️ CORREÇÃO CIRÚRGICA: Se o texto antigo vindo do banco começar com "Prezado Marco", trocamos na hora por "Salve Sobrevivente!"
    if texto_analise_final.startswith("Prezado Marco"):
        texto_analise_final = texto_analise_final.replace("Prezado Marco,", "Salve Sobrevivente!")
        texto_analise_final = texto_analise_final.replace("Prezado Marco", "Salve Sobrevivente!")

    # 🧠 LÓGICA DE DETECÇÃO DO HUMOR DO MARCO PELA FIGURINHA
    imagem_humor = "pessimista.png" # Padrão de segurança
    if "Otimista" in texto_analise_final:
        imagem_humor = "otimista.png"
    elif "Neutro" in texto_analise_final:
        imagem_humor = "neutro.png"
    elif "Pessimista" in texto_analise_final:
        imagem_humor = "pessimista.png"

    return render_template("index.html", noticias=noticias_do_banco, analise_macro=texto_analise_final, figurinha_marco=imagem_humor)

if __name__ == "__main__":
    executar_tarefa_agendada()
    app.run(debug=True, port=5000, use_reloader=False)