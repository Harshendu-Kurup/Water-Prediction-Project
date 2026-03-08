### 1. Install Dependencies

```bash
cd backend
pip install -r requirements.txt
```

### 2. Configure Environment & Database

Create environment file:

```bash
cp .env.example .env
```

Update the `.env` file with your PostgreSQL database credentials:

```
DATABASE_URL=postgresql://your_username:your_password@localhost:5432/tank_sensor_db
```

### 3. Run the Server

```bash
python main.py
```

Or using uvicorn directly:

```bash
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

### 4. Access API Documentation

- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc
- API Base: http://localhost:8000/api/v1
