import os
import requests
from flask import Flask, render_template, send_from_directory
from pymongo import MongoClient
from apscheduler.schedulers.background import BackgroundScheduler
import atexit
import feedparser
import google.generativeai as genai
from datetime import datetime, timezone
import time
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__, template_folder='.')

# Conexões MongoDB
client_mongo = MongoClient(os.getenv("MINHA_CONEXAO_MONGO"))
db = client_mongo['terminal_db']
colecao_noticias = db['noticias']
colecao_analises = db['analises']
colecao_ranking = db['mercado_top30']

genai.configure(api_key=os.getenv("MINHA_CHAVE_GEMINI"))

# FUNÇÃO ROBUSTA DE RANKING
def atualizar_ranking_cripto():
    api_key = os.getenv("API_KEY_COINMARKETCAP")
    if not api_key: return
    
    try:
        url = 'https://pro-api.coinmarketcap.com/v1/cryptocurrency/listings/latest'
        headers = {'X-CMC_PRO_API_KEY': api_key}
        params = {'start': '1', 'limit': '30', 'convert': 'BRL'}
        response = requests.get(url, headers=headers, params=params, timeout=10)
        if response.status_code == 200:
            dados = response.json()['data']
            colecao_ranking.delete_many({})
            colecao_ranking.insert_many(dados)
    except Exception as e:
        print(f"Erro ao atualizar ranking: {e}")

# ROTA PARA IMAGENS
@app.route('/img/<path:filename>')
def custom_static(filename):
    return send_from_directory('img', filename)

# TAREFA AGENDADA (Notícias + Ranking)
def executar_tarefa_agendada():
    # Atualizar Notícias
    url_rss = "https://news.google.com/rss/search?q=bitcoin&hl=pt-BR&gl=BR&ceid=BR:pt-419"
    feed = feedparser.parse(url_rss)
    model = genai.GenerativeModel('gemini-1.5-flash')
    for item in feed.entries[:5]:
        if not colecao_noticias.find_one({"link_original": item.link}):
            try:
                res = model.generate_content(f"Resuma: {item.title}")
                colecao_noticias.update_one({"link_original": item.link}, {"$set": {
                    "titulo_original": item.title, "data_coleta": datetime.now(timezone.utc),
                    "resumo_ia": res.text.strip()
                }}, upsert=True)
                time.sleep(2)
            except: continue
    
    # Atualizar Ranking
    atualizar_ranking_cripto()

scheduler = BackgroundScheduler()
scheduler.add_job(func=executar_tarefa_agendada, trigger="interval", hours=1)
scheduler.start()
atexit.register(lambda: scheduler.shutdown())

@app.route("/")
def home():
    noticias = list(colecao_noticias.find().sort("data_coleta", -1).limit(5))
    analise = colecao_analises.find_one(sort=[("data_analise", -1)])
    txt = analise.get("texto_analise", "Salve Sobrevivente!")
    humor = "otimista.png" if "Otimista" in txt else ("neutro.png" if "Neutro" in txt else "pessimista.png")
    return render_template("index.html", noticias=noticias, analise_macro=txt, figurinha_marco=humor)

@app.route("/ranking")
def ranking():
    # Se o ranking estiver vazio (primeiro acesso), força a atualização na hora
    moedas = list(colecao_ranking.find().sort("cmc_rank", 1))
    if not moedas:
        atualizar_ranking_cripto()
        moedas = list(colecao_ranking.find().sort("cmc_rank", 1))
    return render_template("ranking.html", moedas=moedas)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))