from voyages3.localsettings import *
from datetime import datetime
import uuid
import boto3
import os

def get_s3_session():
	session = boto3.Session(
		aws_access_key_id=aws_access_key_id,
		aws_secret_access_key=aws_secret_access_key
	)	
	s3 = session.resource('s3')
	return s3

def push_item_to_s3(filename, body):
    s3 = get_s3_session()
    bucket = s3.Bucket(aws_bucket_name)
    print(f"Uploading {filename} to S3...")
    s3.Bucket(aws_bucket_name).put_object(Key=filename, Body=body)
    return filename