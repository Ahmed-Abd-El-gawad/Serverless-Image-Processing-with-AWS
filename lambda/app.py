import boto3
from PIL import Image
import io
import os
import uuid

def lambda_handler(event, context):
    s3 = boto3.client('s3')
    rekognition = boto3.client('rekognition')
    dynamodb = boto3.resource('dynamodb')
    sns = boto3.client('sns')
    
    # Get environment variables
    processed_bucket = os.environ['PROCESSED_BUCKET']
    sns_topic_arn = os.environ['SNS_TOPIC_ARN']
    
    try:
        # Extract uploaded file details
        original_bucket = event['Records'][0]['s3']['bucket']['name']
        original_key = event['Records'][0]['s3']['object']['key']
        
        # Generate unique ID for processed files
        file_id = str(uuid.uuid4())
        
        # Process image
        image = Image.open(io.BytesIO(
            s3.get_object(Bucket=original_bucket, Key=original_key)['Body'].read()
        ))
        
        sizes = [(200, 200), (500, 500)]
        for width, height in sizes:
            buffer = io.BytesIO()
            image.resize((width, height)).save(buffer, 'JPEG')
            buffer.seek(0)
            s3.upload_fileobj(buffer, processed_bucket, 
                f"processed/{file_id}-{width}x{height}.jpg")
        
        # Store metadata
        labels = [label['Name'] for label in rekognition.detect_labels(
            Image={'S3Object': {'Bucket': original_bucket, 'Name': original_key}},
            MaxLabels=5
        )['Labels']]
        
        dynamodb.Table('image-metadata').put_item(Item={
            'ImageID': file_id,
            'OriginalKey': original_key,
            'Labels': labels,
            'Sizes': [f"{w}x{h}" for w,h in sizes]
        })
        
        # Send notification
        sns.publish(
            TopicArn=sns_topic_arn,
            Message=f'''Image processed!
            - ID: {file_id}
            - Labels: {", ".join(labels)}
            '''
        )
        
        return {'statusCode': 200}
        
    except Exception as e:
        print(f"Error: {str(e)}")
        return {'statusCode': 500}