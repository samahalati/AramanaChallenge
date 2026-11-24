.PHONY: install seed backend frontend build test eval reset docker
install:           ## backend venv + frontend node_modules
	python3 -m venv .venv && . .venv/bin/activate && pip install -r backend/requirements.txt && cd frontend && npm install
seed:              ## migrate + synthetic data + first detection run
	cd backend && python manage.py migrate && python manage.py seed_demo --detect
backend:           ## API on :8000 (http://localhost:8000/api/docs/)
	cd backend && python manage.py runserver 0.0.0.0:8000
frontend:          ## React dev server on :5173 (proxies /api to :8000)
	cd frontend && npm run dev
build:             ## production build of the React app (Django then serves it at :8000)
	cd frontend && npm run build
test:
	cd backend && python -m pytest -q
eval:              ## detection quality vs synthetic ground truth
	cd backend && python manage.py evaluate
reset:
	cd backend && python manage.py seed_demo --reset --detect
