# 🐳 Docker Deployment Guide

This guide covers containerizing the Harris County Property Lookup Tool using Docker.

## Quick Start

### 1. Prerequisites
- Docker Desktop installed and running
- Docker Compose (included with Docker Desktop)
- Git (to clone the repository)

### 2. Clone and Setup
```bash
git clone https://github.com/PorkChopExpress86/TaxProtest.git
cd TaxProtest
git checkout docker-containerization
```

### 3. Environment Configuration
```bash
# Copy environment template
cp .env.example .env

# Edit .env file with your settings
nano .env  # or your preferred editor
```

### 4. Initialize Data (First Time Only)
```bash
# Download and process Harris County data (~10 minutes)
docker-compose --profile init up data-init

# This will:
# - Download 7 ZIP files from Harris County
# - Extract and process the data
# - Create SQLite database (1.4GB)
# - Add property ratings and features
```

### 5. Start the Application
```bash
# Start the main application
docker-compose up -d

# Access the application
open http://localhost:5000
```

## Docker Deployment Options

### Option 1: Development Mode
```bash
# Start with hot reloading for development
docker-compose up

# This mounts source code for live editing
```

### Option 2: Production Mode
```bash
# Set production environment
export SECRET_KEY="your-production-secret-key"
export FLASK_ENV="production"

# Start in production mode
docker-compose up -d property-lookup
```

### Option 3: Full Stack with Tools
```bash
# Start application + SQLite browser
docker-compose --profile tools up -d

# Access application: http://localhost:5000
# Access database browser: http://localhost:8080
```

## Container Services

### Main Application (`property-lookup`)
- **Port**: 5000
- **Function**: Flask web application
- **Volumes**: 
  - `./data:/app/data` - Database persistence
  - `./Exports:/app/Exports` - CSV exports
  - `./logs:/app/logs` - Application logs

### Data Initialization (`data-init`)
- **Function**: Download and process Harris County data
- **Usage**: Run once for initial setup
- **Command**: `docker-compose --profile init up data-init`

### SQLite Browser (`sqlite-browser`)
- **Port**: 8080
- **Function**: Web-based database browser
- **Usage**: `docker-compose --profile tools up sqlite-browser`

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `SECRET_KEY` | `dev-key` | Flask secret key (CHANGE FOR PRODUCTION) |
| `FLASK_ENV` | `production` | Flask environment mode |
| `DEBUG` | `false` | Enable debug mode |
| `HOST` | `0.0.0.0` | Server bind address |
| `PORT` | `5000` | Server port |

## Volume Management

### Data Persistence
```bash
# Create named volume for data
docker volume create property_data

# Backup database
docker run --rm -v property_data:/data -v $(pwd):/backup alpine \
  tar czf /backup/database_backup.tar.gz -C /data .

# Restore database
docker run --rm -v property_data:/data -v $(pwd):/backup alpine \
  tar xzf /backup/database_backup.tar.gz -C /data
```

### Development Volumes
The docker-compose.yml mounts source code for development:
- `./app.py:/app/app.py` - Main Flask application
- `./templates:/app/templates` - HTML templates
- `./static:/app/static` - Static assets

## Troubleshooting

### Database Issues
```bash
# Check if database exists
docker-compose exec property-lookup ls -la /app/data/

# Rebuild database
docker-compose --profile init up --force-recreate data-init

# Check database size
docker-compose exec property-lookup du -h /app/data/database.sqlite
```

### Application Issues
```bash
# View application logs
docker-compose logs property-lookup

# Access container shell
docker-compose exec property-lookup bash

# Check Flask app directly
docker-compose exec property-lookup python -c "from app import app; print('App loaded successfully')"
```

### Performance Issues
```bash
# Monitor container resources
docker stats harris_property_lookup

# Check container health
docker-compose exec property-lookup python -c "
import sqlite3
conn = sqlite3.connect('/app/data/database.sqlite')
cursor = conn.cursor()
cursor.execute('SELECT COUNT(*) FROM real_acct')
print(f'Database records: {cursor.fetchone()[0]:,}')
conn.close()
"
```

## Production Deployment

### Security Checklist
- [ ] Set strong SECRET_KEY environment variable
- [ ] Use HTTPS reverse proxy (nginx/traefik)
- [ ] Enable container restart policies
- [ ] Set up log rotation
- [ ] Configure firewall rules
- [ ] Regular database backups

### Docker Compose Production
```yaml
# docker-compose.prod.yml
version: '3.8'
services:
  property-lookup:
    build: .
    restart: unless-stopped
    environment:
      - SECRET_KEY=${SECRET_KEY}
      - FLASK_ENV=production
      - DEBUG=false
    volumes:
      - property_data:/app/data
      - ./logs:/app/logs
    networks:
      - web

  nginx:
    image: nginx:alpine
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf
      - ./ssl:/etc/ssl
    depends_on:
      - property-lookup
    networks:
      - web

volumes:
  property_data:

networks:
  web:
    external: true
```

### Run Production
```bash
# Deploy to production
docker-compose -f docker-compose.prod.yml up -d

# Monitor production logs
docker-compose -f docker-compose.prod.yml logs -f
```

## Maintenance

### Update Application
```bash
# Pull latest changes
git pull origin docker-containerization

# Rebuild and restart
docker-compose build --no-cache
docker-compose up -d
```

### Database Updates
```bash
# Update with fresh Harris County data
docker-compose --profile init up --force-recreate data-init
docker-compose restart property-lookup
```

### Container Cleanup
```bash
# Remove unused containers and images
docker system prune -f

# Remove application containers
docker-compose down --volumes --remove-orphans
```

## Performance Optimization

### Container Resources
```bash
# Limit container resources
docker-compose up -d --memory=1g --cpus=2.0
```

### Database Optimization
```bash
# Optimize SQLite database
docker-compose exec property-lookup python -c "
import sqlite3
conn = sqlite3.connect('/app/data/database.sqlite')
conn.execute('VACUUM')
conn.execute('ANALYZE')
conn.close()
print('Database optimized')
"
```

---

## Support

For issues with Docker deployment:
1. Check the troubleshooting section above
2. Review container logs: `docker-compose logs`
3. Verify environment configuration
4. Ensure sufficient disk space (2GB+ recommended)

The containerized application provides the same functionality as the native installation with added benefits of isolation, consistency, and easier deployment across different environments.
