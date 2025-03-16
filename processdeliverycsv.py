import boto3
import csv
import re
import uuid
import time
import json

# AWS Services
s3 = boto3.client('s3')
dynamodb = boto3.resource('dynamodb')
table = dynamodb.Table('DeliveryManagement')
lambda_client = boto3.client('lambda')

# Driver Assignments by Postcode Prefix
DRIVER_ASSIGNMENTS = {
    "W": "Driver 1", "WC": "Driver 2", "EC": "Driver 3",
    "NW": "Driver 4", "N": "Driver 5", "E": "Driver 6",
    "SE": "Driver 7", "SW": "Driver 8"
}

def assign_driver(postcode):
    """Assigns a driver based on the postcode prefix."""
    postcode = postcode.replace(" ", "").upper()  # Normalize format
    for prefix, driver in DRIVER_ASSIGNMENTS.items():
        if postcode.startswith(prefix):
            return driver
    print(f"[WARNING] No driver assigned for postcode {postcode}")
    return "Unassigned"

def invoke_optimization_lambda():
    """Triggers the optimization Lambda function after manifest processing."""
    try:
        response = lambda_client.invoke(
            FunctionName='OptimizeDriverRoutes',  # Replace with the actual function name
            InvocationType='Event',  # Asynchronous invocation
            Payload=json.dumps({})   # No payload needed unless required
        )
        print("✅ Optimization Lambda invoked successfully:", response)
    except Exception as e:
        print("❌ Failed to invoke Optimization Lambda:", str(e))

def lambda_handler(event, context):
    print("🚀 [START] Lambda Function Triggered - Processing Manifest")
    
    # Extract the bucket and key from the S3 event
    try:
        record = event['Records'][0]
        bucket = record['s3']['bucket']['name']
        key = record['s3']['object']['key']
    except KeyError:
        print("❌ [ERROR] Missing 'Records' in event. Check S3 event trigger setup.")
        return {'statusCode': 400, 'body': 'Invalid event structure'}

    print(f"📂 [FILE] Checking for file: s3://{bucket}/{key}")

    # Skip if the key is a directory or not a CSV
    if key.endswith('/') or not key.lower().endswith('.csv'):
        print(f"⚠️ [INFO] Ignoring key {key} - Not a CSV file.")
        return {'statusCode': 200, 'body': f"Ignored key {key}"}
    
    # Fetch CSV file
    try:
        response = s3.get_object(Bucket=bucket, Key=key)
        content = response['Body'].read().decode('utf-8-sig').splitlines()
        print(f"✅ [SUCCESS] Retrieved file: {key}")
    except Exception as e:
        print(f"❌ [ERROR] Failed to fetch file from S3: {str(e)}")
        return {'statusCode': 500, 'body': 'Error fetching file from S3'}

    # Read CSV
    csv_reader = csv.reader(content)
    header = next(csv_reader, None)
    print(f"ℹ️ [INFO] Detected Headers: {header}")

    # Expected Headers
    expected_headers = [
        "Ride Type", "Postcode", "Address Line 1", "Address Line 2",
        "City", "Delivery Instructions", "Customer Name", "Customer Phone Number", "Box Number"
    ]

    # Clean header names and map indices
    cleaned_header = [h.replace('\ufeff', '').strip() for h in header] if header else []
    normalized_headers = [h.lower() for h in cleaned_header]
    normalized_expected = [h.lower() for h in expected_headers]

    # Identify missing headers
    missing_headers = [h for h in normalized_expected if h not in normalized_headers]
    if missing_headers:
        print(f"⚠️ [WARNING] Missing headers: {missing_headers}. Defaulting to empty values.")

    # Map available headers to indices
    header_map = {h.lower(): i for i, h in enumerate(cleaned_header)}

    valid_entries = []
    skipped_count = 0
    
    for row_index, row in enumerate(csv_reader, 1):
        try:
            # Extract fields, defaulting to empty string if missing
            ride_type = row[header_map["ride type"]] if "ride type" in header_map else ""
            postcode = row[header_map["postcode"]] if "postcode" in header_map else ""
            address_line1 = row[header_map["address line 1"]] if "address line 1" in header_map else ""
            address_line2 = row[header_map["address line 2"]] if "address line 2" in header_map else ""
            city = row[header_map["city"]] if "city" in header_map else ""
            address = f"{address_line1}, {address_line2}, {city}".replace(", , ", ", ").strip()
            delivery_notes = row[header_map["delivery instructions"]] if "delivery instructions" in header_map else ""
            customer_name = row[header_map["customer name"]] if "customer name" in header_map else ""
            customer_phone = row[header_map["customer phone number"]] if "customer phone number" in header_map else ""
            box_number = row[header_map["box number"]] if "box number" in header_map else ""

            # Validate postcode
            if not postcode or not re.match(r"^[A-Z]{1,2}\d[A-Z\d]? ?\d[A-Z]{2}$", postcode.replace(" ", "").upper()):
                print(f"⚠️ [WARNING] Invalid or missing postcode at row {row_index}. Skipping.")
                skipped_count += 1
                continue

            driver_id = assign_driver(postcode)
            current_time = int(time.time())
            unique_id = f"{uuid.uuid4().hex}_{current_time}"
            delivery_id = f"DELIVERY#{unique_id}"
            sort_key = f"POSTCODE#{postcode}#{ride_type}#{box_number}#{current_time}"

            valid_entries.append({
                'PK': delivery_id,
                'SK': sort_key,
                'Type': 'Delivery',
                'RideType': ride_type,
                'DriverID': driver_id,
                'Address': address,
                'DeliveryNotes': delivery_notes,
                'CustomerName': customer_name,
                'CustomerPhone': customer_phone,
                'BoxNumber': box_number,
                'PostcodeRaw': postcode,
                'CreatedAt': current_time,
                'RouteSequence': 0
            })
        except Exception as e:
            print(f"❌ [ERROR] Error processing row {row_index}: {str(e)}")
            skipped_count += 1
            continue

    # Batch Insert into DynamoDB
    batch_size = 25
    success_count = 0
    if valid_entries:
        for i in range(0, len(valid_entries), batch_size):
            batch = valid_entries[i:i+batch_size]
            with table.batch_writer() as writer:
                for entry in batch:
                    try:
                        writer.put_item(Item=entry)
                        success_count += 1
                    except Exception as e:
                        print(f"❌ [ERROR] Failed to insert item {entry['PK']}: {str(e)}")

    print(f"✅ [COMPLETE] Processed {success_count} entries. Skipped: {skipped_count}")

    # Move file to processed folder
    if success_count > 0:
        try:
            processed_key = key.replace('incoming/', 'processed/')
            s3.copy_object(Bucket=bucket, Key=processed_key, CopySource={'Bucket': bucket, 'Key': key})
            s3.delete_object(Bucket=bucket, Key=key)
            print(f"📂 [FILE] Moved file to: {processed_key}")
        except Exception as e:
            print(f"❌ [ERROR] Failed to move processed file: {str(e)}")

    # Trigger Optimization Lambda
    print("🚀 Invoking Optimization Lambda...")
    invoke_optimization_lambda()

    return {'statusCode': 200, 'body': 'Manifest processed and optimization invoked'}
