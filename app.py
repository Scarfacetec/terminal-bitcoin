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

def atualizar_ranking_cripto():
    api_key = os.getenv("API_KEY_COINMARKETCAP")
    if not api_key:
        print("❌ ERRO: A variável de ambiente API_KEY_COINMARKETCAP não foi encontrada!")
        return

    url = 'https://pro-api.coinmarketcap.com/v1/cryptocurrency/listings/latest'
    headers = {'X-CMC_PRO_API_KEY': api_key}
    params = {'start': '1', 'limit': '30', 'convert': 'BRL'}
    
    try:
        response = requests.get(url, headers=headers, params=params)
        data = response.json()
        
        if response.status_code == 200:
            lista = data['data']
            colecao_ranking.delete_many({})
            colecao_ranking.insert_many(lista)
            print("✅ Ranking Top 30 atualizado com sucesso!")
        else:
            print(f"❌ Erro na API CoinMarketCap (Status {response.status_code}): {data}")


app = Flask(__name__, template_folder='.')

# --- FORÇA A ATUALIZAÇÃO AO INICIAR O APP ---
try:
    print("🚀 Iniciando atualização forçada do ranking...")
    # (aqui você pode chamar a função ou colocar o código direto)
    atualizar_ranking_cripto()
except Exception as e:
    print(f"⚠️ Erro na inicialização do ranking: {e}")
# --------------------------------------------

genai.configure(api_key=os.getenv("MINHA_CHAVE_GEMINI"))

@app.route('/img/<path:filename>')
def custom_static(filename):
    return send_from_directory('img', filename)

# Conexão MongoDB
client_mongo = MongoClient(os.getenv("MINHA_CONEXAO_MONGO"))
db = client_mongo['terminal_db']
colecao_noticias = db['noticias']
colecao_analises = db['analises']
colecao_ranking = db['mercado_top30']

            
    except Exception as e:
        print(f"❌ Erro crítico ao atualizar ranking: {str(e)}")

def executar_tarefa_agendada():
    print("⏰ [Agendador] Iniciando ciclo de atualizações...")
    # 1. Atualizar Notícias
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
    
    # 2. Atualizar Ranking
    atualizar_ranking_cripto()

scheduler = BackgroundScheduler()
scheduler.add_job(func=executar_tarefa_agendada, trigger="interval", hours=1)
scheduler.start()
atexit.register(lambda: scheduler.shutdown())

@app.route("/")
def home():
    noticias = list(colecao_noticias.find().sort("data_coleta", -1).limit(5))
    analise = colecao_analises.find_one(sort=[("data_analise", -1)])
    txt = analise.get("texto_analise", "Salve Sobrevivente! Analisando...") if analise else "Salve Sobrevivente!"
    
    txt = txt.replace("Prezado Marco", "Salve Sobrevivente!")
    if not txt.startswith("Salve Sobrevivente!"): txt = "Salve Sobrevivente! " + txt
    
    humor = "otimista.png" if "Otimista" in txt else ("neutro.png" if "Neutro" in txt else "pessimista.png")
    return render_template("index.html", noticias=noticias, analise_macro=txt, figurinha_marco=humor)

@app.route("/ranking")
def ranking():
    moedas = list(colecao_ranking.find().sort("cmc_rank", 1))
    return render_template("ranking.html", moedas=moedas)

if __name__ == "__main__":
    # Força uma atualização ao iniciar para não ficar vazio
    try:
        atualizar_ranking_cripto()
        print("✅ Ranking inicializado com sucesso!")
    except Exception as e:
        print(f"⚠️ Erro ao inicializar ranking: {e}")

    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))