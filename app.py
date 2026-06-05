import os
from flask import Flask, render_template, send_from_directory
from pymongo import MongoClient
from apscheduler.schedulers.background import BackgroundScheduler
import atexit
import feedparser
import google.generativeai as genai
import requests
from datetime import datetime, timezone
import time
from dotenv import load_dotenv

load_dotenv()

# 1. DEFINIÇÃO DA FUNÇÃO (No topo, para o Python conhecer ela sempre)
def atualizar_ranking_cripto():
    api_key = os.getenv("API_KEY_COINMARKETCAP")
    if not api_key:
        print("❌ ERRO: API_KEY_COINMARKETCAP não configurada!")
        return
    
    url = 'https://pro-api.coinmarketcap.com/v1/cryptocurrency/listings/latest'
    headers = {'X-CMC_PRO_API_KEY': api_key}
    params = {'start': '1', 'limit': '30', 'convert': 'BRL'}
    
    try:
        response = requests.get(url, headers=headers, params=params)
        if response.status_code == 200:
            lista = response.json()['data']
            colecao_ranking.delete_many({})
            colecao_ranking.insert_many(lista)
            print("✅ Ranking Top 30 atualizado com sucesso!")
        else:
            print(f"❌ Erro API: {response.status_code}")
    except Exception as e:
        print(f"❌ Erro crítico: {e}")

# 2. CONFIGURAÇÕES GERAIS
app = Flask(__name__, template_folder='.')
client_mongo = MongoClient(os.getenv("MINHA_CONEXAO_MONGO"))
db = client_mongo['terminal_db']
colecao_noticias = db['noticias']
colecao_analises = db['analises']
colecao_ranking = db['mercado_top30']
genai.configure(api_key=os.getenv("MINHA_CHAVE_GEMINI"))

# 3. ROTAS E FUNÇÕES
@app.route('/img/<path:filename>')
def custom_static(filename):
    return send_from_directory('img', filename)

def executar_tarefa_agendada():
    # ... (seu código de notícias)
    atualizar_ranking_cripto()

# 4. INICIALIZAÇÃO
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
    moedas = list(colecao_ranking.find().sort("cmc_rank", 1))
    return render_template("ranking.html", moedas=moedas)

if __name__ == "__main__":
    atualizar_ranking_cripto() # Chamada segura aqui
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))