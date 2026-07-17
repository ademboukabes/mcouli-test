from db.generated import devices as device_queries
import uuid
from app.core.exceptions import DBException,AppException, DBExceptionImpl
from db.generated.models import UserDevice


class DeviceService:
    device_querier: device_queries.AsyncQuerier

    def init(self: "DeviceService", device_querier: device_queries.AsyncQuerier) -> None:
        self.device_querier = device_querier

    async def activate_device(
        self: "DeviceService",
        device_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> None:
        try:
            await self.device_querier.activate_device(
                id=device_id,
                user_id=user_id,
            )
        except Exception as e:
            raise DBException.handle(e)

    async def revoke_device(
        self: "DeviceService",
        device_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> None:
        try :
            #here were cacscading the delete of the session  no need to handle it
            await self.device_querier.revoke_device(
                id=device_id,
                user_id=user_id
            )
        except Exception as e :
            raise DBException.handle(e)

    async def update_device_push_token(
        self: "DeviceService",
        device_id: uuid.UUID,
        user_id: uuid.UUID,
        push_token: str,
    ) -> UserDevice:
        try:
            device = await self.device_querier.update_device_push_token(
                id=device_id,
                push_token=push_token,
                user_id=user_id,
            )
            if device is None:
                raise AppException.not_found("Device not found")
            return device
        except Exception as e:
            raise DBException.handle(e)

    async def inactivate_device(
        self: "DeviceService",
        device_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> None:
        try:
            device = await self.device_querier.get_device_by_id(id=device_id, user_id=user_id)
            if device is None or device.user_id != user_id:
                raise AppException.not_found("Device not found")
            await self.device_querier.deactivate_device(
                id=device_id,
                user_id=user_id,
            )
        except Exception as e:
            raise DBException.handle(e)

    async def get_all_devices(self: "DeviceService", user_id: uuid.UUID) -> tuple[list[UserDevice], int]:
        devices: list[UserDevice] = []

        async for device in self.device_querier.list_user_devices(user_id=user_id):
            devices.append(device)

        count = await self.count_devices(user_id=user_id)

        return devices, count

    async def get_device_by_id(
        self: "DeviceService",
        device_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> UserDevice:
        try :
            device =  await self.device_querier.get_device_by_id(id=device_id, user_id=user_id)
            if device is None :
                raise AppException.not_found("device not found ")
            return device
        except Exception as e :
            raise DBExceptionImpl.handle(e)

    async def count_devices(self: "DeviceService", user_id: uuid.UUID) -> int:
        try :
            count =  await self.device_querier.count_user_devices(user_id=user_id)
            if count is None :
                raise AppException.internal_error("db failed to count ")
            return count
        except Exception as e :
            raise  DBExceptionImpl.handle(e)

