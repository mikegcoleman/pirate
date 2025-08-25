# Pirate LLM API Deployment Makefile
# Usage: make deploy (builds and deploys locally on Windows)
#        make push   (builds and pushes to Docker Hub)

.PHONY: help build deploy rebuild push clean logs health restart

# Default target
help:
	@echo "Pirate LLM API Deployment Commands:"
	@echo "  make deploy  - Restart container with new code (fast)"
	@echo "  make rebuild - Full rebuild and deploy (slow)"
	@echo "  make build   - Build Docker image only"
	@echo "  make push    - Build and push to Docker Hub"
	@echo "  make restart - Quick restart without rebuild"
	@echo "  make clean   - Stop container and remove images"
	@echo "  make logs    - Show container logs"
	@echo "  make health  - Check service health"

# Build the Docker image
build:
	@echo "🔨 Building Docker image..."
	docker build -t mgc0216/pirate-api:latest .

# Deploy locally (restart with volume-mounted code)
deploy:
	@echo "🚀 Deploying LLM API locally..."
	@echo "🔄 Restarting container with new code..."
	docker-compose restart
	@echo "⏳ Waiting for service to be ready..."
	@timeout /t 5 /nobreak > nul
	@$(MAKE) health

# Full rebuild (if you need to rebuild the base image)
rebuild:
	@echo "🚀 Full rebuild and deploy..."
	@echo "⏹️  Stopping existing container..."
	-docker-compose down
	@echo "🔨 Building new image..."
	docker build -t mgc0216/pirate-api:latest .
	@echo "🟢 Starting new container..."
	docker-compose up -d
	@echo "⏳ Waiting for service to be ready..."
	@timeout /t 5 /nobreak > nul
	@$(MAKE) health

# Build and push to Docker Hub
push: build
	@echo "📤 Pushing to Docker Hub..."
	docker push mgc0216/pirate-api:latest
	@echo "✅ Push complete!"

# Clean up containers and images
clean:
	@echo "🧹 Cleaning up..."
	-docker-compose down
	-docker rmi mgc0216/pirate-api:latest
	-docker image prune -f

# Show container logs
logs:
	@echo "📋 Container logs:"
	docker-compose logs --tail=20 -f

# Check service health
health:
	@echo "🏥 Checking service health..."
	@curl -f http://localhost:8080/health || echo "❌ Health check failed"

# Quick restart without rebuild
restart:
	@echo "🔄 Restarting container..."
	docker-compose restart
	@timeout /t 3 /nobreak > nul
	@$(MAKE) health