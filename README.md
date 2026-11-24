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
