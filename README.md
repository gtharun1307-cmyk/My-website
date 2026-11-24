# VVITU Payroll System

## Deploy on Render
1. Upload the **contents of this ZIP** to the root of your GitHub repository (so `app.py`, `templates/`, and `static/` are at the same level).
2. Create a Render **Web Service** connected to that repository.
3. Runtime: Python 3.
4. Build command: `pip install -r requirements.txt`
5. Start command: `gunicorn app:app`

The Flask app uses absolute paths for `templates/` and `static/`, based on the location of `app.py`.

## Run locally
```bash
pip install -r requirements.txt
python app.py
```


## Render deployment note (v3)

This version detects `templates/login.html` either directly under the repository root or one level inside the extracted project folder. Make sure the GitHub repository contains the complete `templates/` and `static/` folders; Python code cannot render a template file that was not committed/pushed.

Render settings:
- Build: `pip install -r requirements.txt`
- Start: `gunicorn app:app`
