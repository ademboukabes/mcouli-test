from db.generated import devices as device_queries
from app.core.securite import  create_totp_secret
import uuid
from app.core.exceptions import DBException,AppException, DBExceptionImpl
from db.generated.models import UserDevice


class DeviceService:
    device_querier: device_queries.AsyncQuerier

    def init(self, device_querier: device_queries.AsyncQuerier):
        self.device_querier = device_querier
    @staticmethod
    async def create_device(user_id: uuid.UUID,device_name: str,device_type: str)->UserDevice|None:
        try :
            DeviceCount = await DeviceService.count_devices(user_id=user_id)
            if  DeviceCount >=3:
                raise AppException.bad_request("You can only have 3 devices")
            return await DeviceService.device_querier.create_device(
                user_id=user_id,
                device_name=device_name,
                device_type=device_type,
                totp_secret=create_totp_secret(),
            )
        except Exception as e :
            DBException.handle(e)

    @staticmethod
    async def revoke_device(device_id:uuid.UUID,user_id :uuid.UUID):
        try :
            #here were cacscading the delete of the session  no need to handle it
            await DeviceService.device_querier.revoke_device(
                id=device_id,
                user_id=user_id
            )
        except Exception as e :
            DBException.handle(e)

    @staticmethod
    async def get_all_devices(user_id: uuid.UUID) -> tuple[list[UserDevice], int]:
        devices: list[UserDevice] = []

        async for device in DeviceService.device_querier.list_user_devices(user_id=user_id):
            devices.append(device)

        count = await DeviceService.count_devices(user_id=user_id)

        return devices, count

    @staticmethod
    async def get_device_by_id(device_id:uuid.UUID,user_id:uuid.UUID)->UserDevice|None:
        try :
            device =  await DeviceService.device_querier.get_device__by_id(id=device_id)
            if device is None :
                raise AppException.not_found("device not found ")
        except Exception as e :
             raise DBExceptionImpl.handle(e)

    @staticmethod
    async  def count_devices(user_id:uuid.UUID)->int:
        try :
            count =  await DeviceService.device_querier.count__user__devices(user_id=user_id)
            if count is None :
                raise AppException.internal_error("db failed to count ")
            return count
        except Exception as e :
            raise  DBExceptionImpl.handle(e)






