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

# Carrega as variáveis do .env (local) ou do painel do Render (produção)
load_dotenv()

app = Flask(__name__, template_folder='.')

# Configuração da Chave da IA
genai.configure(api_key=os.getenv("MINHA_CHAVE_GEMINI"))

@app.route('/img/<path:filename>')
def custom_static(filename):
    return send_from_directory('img', filename)

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
        
        noticia_existente = colecao_noticias.find_one({"link_original": link})
        if noticia_existente: continue
            
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
            
    # Análise Macro
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

scheduler = BackgroundScheduler()
scheduler.add_job(func=executar_tarefa_agendada, trigger="interval", hours=1)
scheduler.start()
atexit.register(lambda: scheduler.shutdown())

@app.route("/")
def home():
    noticias = list(colecao_noticias.find().sort("data_coleta", -1).limit(5))
    analise = colecao_analises.find_one(sort=[("data_analise", -1)])
    
    txt = analise.get("texto_analise", "Salve Sobrevivente! Analisando mercado...") if analise else "Salve Sobrevivente!"
    
    # Lógica de Imagem
    humor = "pessimista.png"
    if "Otimista" in txt: humor = "otimista.png"
    elif "Neutro" in txt: humor = "neutro.png"

    return render_template("index.html", noticias=noticias, analise_macro=txt, figurinha_marco=humor)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))