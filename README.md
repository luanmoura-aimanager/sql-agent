# SQL Agent

A Streamlit app that lets you query a SQLite database using plain Portuguese. Powered by Claude via the Anthropic API with a ReAct (tool use) loop.

## How it works

1. You type a question in natural language (e.g. "Quais clientes são de São Paulo?")
2. Claude decides which SQL query to run against the database
3. The query executes and results are returned to Claude
4. Claude answers in Portuguese based on the data

Only `SELECT` queries are allowed — write operations are blocked.

## Database schema

A demo store database with three tables:

| Table | Columns |
|---|---|
| `customers` | id, name, city, email |
| `products` | id, name, category, price |
| `orders` | id, customer_id, product_id, quantity, order_date |

## Deploy on Streamlit Cloud

1. Fork or push this repo to GitHub
2. Go to [share.streamlit.io](https://share.streamlit.io) and connect the repo
3. Set the main file to `app.py`
4. Add your Anthropic API key in **Settings → Secrets**:

```toml
ANTHROPIC_API_KEY = "sk-ant-..."
```

## Run locally

```bash
pip install -r requirements.txt
export ANTHROPIC_API_KEY="sk-ant-..."
streamlit run app.py
```
