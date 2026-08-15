from pathlib import Path
from typing import Protocol

from app.core.config import settings


class StorageAdapter(Protocol):
    def put(self,key:str,data:bytes,content_type:str)->None: ...
    def get(self,key:str)->bytes: ...
    def health(self)->dict: ...


class LocalStorage:
    def put(self,key:str,data:bytes,content_type:str)->None:
        destination=Path(settings.storage_path)/key;destination.parent.mkdir(parents=True,exist_ok=True);destination.write_bytes(data)
    def get(self,key:str)->bytes:
        path=Path(settings.storage_path)/key
        if not path.exists(): raise FileNotFoundError(key)
        return path.read_bytes()
    def health(self)->dict:
        path=Path(settings.storage_path);path.mkdir(parents=True,exist_ok=True);return {"backend":"LOCAL","status":"UP","path":str(path)}


class S3Storage:
    def __init__(self):
        import boto3
        self.client=boto3.client("s3",region_name=settings.s3_region,endpoint_url=settings.s3_endpoint_url)
    def put(self,key:str,data:bytes,content_type:str)->None:
        self.client.put_object(Bucket=settings.s3_bucket,Key=key,Body=data,ContentType=content_type,ServerSideEncryption="AES256")
    def get(self,key:str)->bytes:
        response=self.client.get_object(Bucket=settings.s3_bucket,Key=key)
        return response["Body"].read()
    def health(self)->dict:
        self.client.head_bucket(Bucket=settings.s3_bucket);return {"backend":"S3","status":"UP","bucket":settings.s3_bucket}


def get_storage()->StorageAdapter:
    return S3Storage() if settings.storage_backend.upper()=="S3" else LocalStorage()
