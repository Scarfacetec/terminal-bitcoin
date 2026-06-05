import os
from flask import Flask, render_template, send_from_directory
from pymongo import MongoClient
from apscheduler.schedulers.background import BackgroundScheduler
import atexit
import feedparser
import google.generativeai as genai
from datetime import datetime, timezone
import time
from dotenv import load_dotenv

# Carrega variáveis de ambiente (do .env local ou do painel do Render)
load_dotenv()

app = Flask(__name__, template_folder='.')

# Configuração da Chave da IA
genai.configure(api_key=os.getenv("MINHA_CHAVE_GEMINI"))

# Rota para servir suas imagens da pasta 'img/'
@app.route('/img/<path:filename>')
def custom_static(filename):
    return send_from_directory('img', filename)

# Conexão com MongoDB
try:
    client_mongo = MongoClient(os.getenv("MINHA_CONEXAO_MONGO"))
    db = client_mongo['terminal_db']
    colecao_noticias = db['noticias']
    colecao_analises = db['analises']
    print("✅ Conectado ao MongoDB Atlas!")
except Exception as e:
    print(f"❌ Erro ao conectar no MongoDB: {e}")

def executar_tarefa_agendada():
    print("⏰ [Agendador] Iniciando varredura...")
    
    url_rss = "https://news.google.com/rss/search?q=bitcoin&hl=pt-BR&gl=BR&ceid=BR:pt-419"
    feed = feedparser.parse(url_rss)
    
    if not feed.entries: return
        
    noticias_principais = feed.entries[:5]
    titulos_do_dia = []
    
    model = genai.GenerativeModel('gemini-1.5-flash')

    for item in noticias_principais:
        titulo = item.title
        link = item.link
        titulos_do_dia.append(titulo)
        
        # Evita duplicidade no banco
        if colecao_noticias.find_one({"link_original": link}): continue
            
        try:
            comando = f"Resuma a notícia: {titulo}. Responda apenas com o resumo direto, sem introduções."
            res = model.generate_content(comando)
            
            colecao_noticias.update_one({"link_original": link}, {"$set": {
                "titulo_original": titulo,
                "link_original": link,
                "data_coleta": datetime.now(timezone.utc),
                "resumo_ia": res.text.strip()
            }}, upsert=True)
            time.sleep(2)
        except: continue
            
    # Geração da Análise Macro
    try:
        bloco = "\n".join([f"- {t}" for t in titulos_do_dia])
        comando_macro = f"""
        Analise o mercado de BTC: {bloco}.
        1. Comece com "Salve Sobrevivente!"
        2. Resumo profissional de 3 a 5 linhas.
        3. Termine com: "Sentimento Geral: [Otimista/Pessimista/Neutro]"
        """
        res_macro = model.generate_content(comando_macro)
        colecao_analises.insert_one({
            "texto_analise": res_macro.text.strip(),
            "data_analise": datetime.now(timezone.utc)
        })
    except Exception as e:
        print(f"Erro na análise: {e}")

# Agendamento para rodar de hora em hora
scheduler = BackgroundScheduler()
scheduler.add_job(func=executar_tarefa_agendada, trigger="interval", hours=1)
scheduler.start()
atexit.register(lambda: scheduler.shutdown())

@app.route("/")
def home():
    noticias = list(colecao_noticias.find().sort("data_coleta", -1).limit(5))
    analise = colecao_analises.find_one(sort=[("data_analise", -1)])
    
    # Busca texto ou define padrão
    txt = analise.get("texto_analise", "Salve Sobrevivente! Analisando o mercado...") if analise else "Salve Sobrevivente!"
    
    # 🛡️ LIMPEZA E FORÇAGEM DO BORDÃO
    txt = txt.replace("Prezado Marco", "Salve Sobrevivente!")
    txt = txt.replace("Prezado Marco,", "Salve Sobrevivente!")
    if not txt.startswith("Salve Sobrevivente!"):
        txt = "Salve Sobrevivente! " + txt

    # Lógica de Imagem
    humor = "pessimista.png"
    if "Otimista" in txt: humor = "otimista.png"