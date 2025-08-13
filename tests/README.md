# 🧪 Testing Suite

This directory contains automated tests for validating application functionality and deployment.

## Test Files

- **`test_docker.py`** - Docker container functionality tests
- **`test_deployment.py`** - End-to-end deployment validation

## Running Tests

### Local Testing
```bash
# Run deployment tests
python tests/test_deployment.py

# Run Docker tests
python tests/test_docker.py
```

### Docker Testing
```bash
# Test Docker deployment
docker-compose up property-lookup
python tests/test_deployment.py
```

## Test Coverage

✅ **Container Functionality**
- Container startup and health
- Data initialization process
- Database connectivity
- Port accessibility

✅ **Application Testing**  
- Flask application startup
- Search functionality
- Export capabilities
- Error handling
