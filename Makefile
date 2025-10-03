.PHONY: backend worker ui

backend:
	cd backend && uvicorn app.main:app --reload --port 8080

worker:
	cd worker && uvicorn app.main:app --reload --port 8090

ui:
	cd ui && npm run dev
