import asyncio
from sqlalchemy.ext.asyncio import create_async_engine
from app.core.config import settings

async def main():
    url = f"postgresql+asyncpg://{settings.POSTGRES_USER}:{settings.POSTGRES_PASSWORD}@{settings.POSTGRES_HOST}:{settings.POSTGRES_PORT}/{settings.POSTGRES_DB}"
    engine = create_async_engine(url)
    
    async with engine.connect() as conn:
        import sqlalchemy
        
        # Check processing jobs
        jobs = (await conn.execute(sqlalchemy.text("SELECT status, count(*) FROM processing_jobs GROUP BY status"))).fetchall()
        print("=== PROCESSING JOBS STATUS ===")
        for j in jobs:
            print(f"Status: {j[0]}, Count: {j[1]}")
            
        # Check photo faces
        faces = (await conn.execute(sqlalchemy.text("SELECT count(*) FROM photo_faces"))).scalar()
        print(f"\n=== VISAGES DETECTES ===")
        print(f"Nombre total de visages isolés et enregistrés par l'IA : {faces}")

asyncio.run(main())
