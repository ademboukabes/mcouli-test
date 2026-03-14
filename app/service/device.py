from db.generated import devices as device_queries
from app.core.securite import  create_totp_secret
import uuid
from app.core.exceptions import DBException,AppException, DBExceptionImpl
from db.generated.models import UserDevice


class DeviceService:
    device_querier: device_queries.AsyncQuerier

    def init(self: "DeviceService", device_querier: device_queries.AsyncQuerier) -> None:
        self.device_querier = device_querier

    async def create_device(
        self: "DeviceService",
        user_id: uuid.UUID,
        device_name: str,
        device_type: str,
        id: uuid.UUID | None = None,
    ) -> UserDevice | None:
        try :
            DeviceCount = await self.count_devices(user_id=user_id)
            if  DeviceCount >=3:
                raise AppException.bad_request("You can only have 3 devices")
            return await self.device_querier.create_device(
                arg=device_queries.CreateDeviceParams(
                column_1=id,
                user_id=user_id,
                device_name=device_name,
                device_type=device_type,
                totp_secret=create_totp_secret(),
                )

            )
        except Exception as e :
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
            device =  await self.device_querier.get_device__by_id(id=device_id)
            if device is None :
                raise AppException.not_found("device not found ")
            return device
        except Exception as e :
            raise DBExceptionImpl.handle(e)

    async def count_devices(self: "DeviceService", user_id: uuid.UUID) -> int:
        try :
            count =  await self.device_querier.count__user__devices(user_id=user_id)
            if count is None :
                raise AppException.internal_error("db failed to count ")
            return count
        except Exception as e :
            raise  DBExceptionImpl.handle(e)


