import asyncio
from app.infra.database import engine
from app.container import Container
from db.generated.models import StaffRole
from app.infra.redis import RedisClient


async def main():
    RedisClient.init(host="localhost", port=6379, password="")
    async with engine.begin() as conn:
        container = Container(conn)

        # Check if exists
        existing = await container.staff_user_service.staff_user_querier.get_staff_user_by_email(
            email="m@example.com"
        )
        if existing:
            print("Admin already exists!")
            return

        print("Creating admin user m@example.com...")
        await container.staff_user_service.create_staff_user(
            email="m@example.com", password="password", role=StaffRole.ADMIN
        )
        print("Admin user created! password is: password")


if __name__ == "__main__":
    asyncio.run(main())
