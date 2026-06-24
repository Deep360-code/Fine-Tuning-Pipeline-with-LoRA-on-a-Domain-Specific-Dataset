import os
import time
from flask import Flask, request, jsonify
from openai import OpenAI

app = Flask(__name__)

# 1. FIXED: Pointing directly to the dedicated Hugging Face Serverless API gateway
client = OpenAI(
    base_url="https://huggingface.co",
    api_key=os.environ.get("HF_TOKEN")  # Safely injected via your environment variable
)

# 2. Your exact fine-tuned model path on Hugging Face
MODEL_ID = "DeepSharmaDeep/fine_tuned_SQL"

@app.route("/", methods=["GET"])
def home():
    # Serves a clean, beautiful web user interface directly in your browser
    return """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>SQL Generation AI Client</title>
        <style>
            body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #f5f7fb; margin: 0; padding: 40px; display: flex; justify-content: center; }
            .container { background: white; padding: 30px; border-radius: 12px; box-shadow: 0 4px 20px rgba(0,0,0,0.05); width: 100%; max-width: 600px; }
            h2 { color: #1e293b; margin-top: 0; font-size: 22px; }
            textarea { width: 100%; height: 140px; padding: 12px; border: 1px solid #cbd5e1; border-radius: 8px; font-size: 14px; box-sizing: border-box; resize: vertical; font-family: monospace; line-height: 1.5; }
            button { background: #2563eb; color: white; border: none; padding: 12px 20px; font-size: 14px; font-weight: 600; border-radius: 8px; cursor: pointer; margin-top: 12px; width: 100%; transition: background 0.2s; }
            button:hover { background: #1d4ed8; }
            .result-box { margin-top: 24px; padding: 16px; background: #0f172a; color: #38bdf8; border-radius: 8px; font-family: monospace; white-space: pre-wrap; font-size: 14px; display: none; border-left: 4px solid #3b82f6; }
        </style>
    </head>
    <body>
        <div class="container">
            <h2>Text-to-SQL Fine-Tuned Model</h2>
            <p style="color: #64748b; font-size: 14px; margin-bottom: 20px;">Input your database schema and question below to compile a clean SQL instruction string.</p>
            <textarea id="queryInput">Schema:
CREATE TABLE employees (name VARCHAR, department VARCHAR, salary INT);

Question:
List the names of employees in the Engineering department earning more than 100000.</textarea>
            <button onclick="submitQuery()">Generate SQL Query</button>
            <div id="result" class="result-box"></div>
        </div>

        <script>
            async function submitQuery() {
                const queryText = document.getElementById('queryInput').value;
                const resultBox = document.getElementById('result');
                if(!queryText) return alert('Please enter a query context first!');
                
                resultBox.style.display = 'block';
                resultBox.innerText = 'Processing inference request across Hugging Face gateway... (If this is the first call, it may take a minute for the model to wake up)';
                resultBox.style.color = '#94a3b8';

                try {
                    const response = await fetch('/predict', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ query: queryText })
                    });
                    const data = await response.json();
                    if(data.sql_query) {
                        resultBox.innerText = data.sql_query;
                        resultBox.style.color = '#38bdf8';
                    } else {
                        resultBox.innerText = 'Error: ' + (data.error || 'Unknown breakdown');
                        resultBox.style.color = '#f87171';
                    }
                } catch (err) {
                    resultBox.innerText = 'Network error: Container connection tracking broken.';
                    resultBox.style.color = '#f87171';
                }
            }
        </script>
    </body>
    </html>
    """

@app.route("/predict", methods=["POST"])
def predict():
    data = request.get_json() or {}
    user_query = data.get("query", "")
    
    if not user_query:
        return jsonify({"error": "Please provide a 'query' in the JSON body"}), 400
        
    # Retry up to 3 times automatically if the serverless model is loading/spinning up
    for attempt in range(3):
        try:
            response = client.chat.completions.create(
                model=MODEL_ID,
                messages=[
                    {"role": "system", "content": "You are a SQL assistant. Given a table schema and a question, reply with ONLY the SQL query, nothing else."},
                    {"role": "user", "content": user_query}
                ],
                max_tokens=300,
                temperature=0.1
            )
            
            # If the gateway responds with an unexpected raw string
            if isinstance(response, str) and "loading" in response.lower():
                print(f"Model is loading on HF servers, waiting... (Attempt {attempt + 1}/3)")
                time.sleep(20)  
                continue
                
            return jsonify({"sql_query": response.choices.message.content.strip()})
            
        except Exception as e:
            error_msg = str(e)
            # Catching the common 503 "Model is loading" exception state gracefully
            if "loading" in error_msg.lower() or "estimated_time" in error_msg.lower():
                print(f"Model loading exception caught, waiting... (Attempt {attempt + 1}/3)")
                time.sleep(20)
                continue
            return jsonify({"error": error_msg}), 500

    return jsonify({"error": "The model is taking a bit long to cache on Hugging Face. Please try submitting again in a few seconds!"}), 503

if __name__ == "__main__":
    # Binds to port 5002 inside your container network environment
    app.run(host="0.0.0.0", port=5002)
