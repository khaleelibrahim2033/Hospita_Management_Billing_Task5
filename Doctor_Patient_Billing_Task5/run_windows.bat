@echo off
python -m venv .venv
call .venv\Scripts\activate
python -m pip install -r requirements.txt
copy .env.example .env
uvicorn app.main:app --reload
