#!/usr/bin/env python3
from sqlalchemy import create_engine, text
import os

url = os.getenv('DATABASE_URL', '')
try:
    engine = create_engine(url)
    with engine.connect() as conn:
        result = conn.execute(text('SELECT version()'))
        print(f'✅ Postgres connected: {result.scalar()[:50]}')
        result = conn.execute(text('SELECT current_database()'))
        print(f'✅ Database: {result.scalar()}')
        print('✅ Database connectivity verified!')
except Exception as e:
    print(f'❌ Database connection failed: {e}')
    exit(1)
