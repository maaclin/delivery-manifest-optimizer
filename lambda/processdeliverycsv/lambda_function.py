import boto3
import csv
import re
import uuid
import time
import json
import urllib.parse

# AWS Services
s3 = boto3.client('s3')
dynamodb = boto3.resource('dynamodb')
delivery_table = dynamodb.Table('DeliveryManagement')  # Stores delivery details
driver_table = dynamodb.Table('DriverLocations')  # Stores driver ETA and locations
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
            FunctionName='OptimizeDriverRoutes',  # Ensure this is the correct Lambda function name
            InvocationType='Event',  # Asynchronous invocation
            Payload=json.dumps({})
        )
        print("✅ Optimization Lambda invoked successfully:", response)
    except Exception as e:
        print("❌ Failed to invoke Optimization Lambda:", str(e))

def process_manifest(bucket, key):
    """Reads the incoming delivery manifest CSV and stores data in DynamoDB."""
    try:
        response = s3.get_object(Bucket=bucket, Key=key)
        content = response['Body'].read().decode('utf-8-sig').splitlines()
        csv_reader = csv.reader(content)
        header = next(csv_reader, None)

        print(f"ℹ️ [INFO] Detected Manifest Headers: {header}")

        required_headers = [
            "Ride Type", "Postcode", "Address Line 1", "Address Line 2",
            "City", "Delivery Instructions", "Customer Name", "Customer Phone Number", "Box Number"
        ]

        header_map = {h.strip(): i for i, h in enumerate(header)}

        missing_headers = [h for h in required_headers if h not in header_map]
        if missing_headers:
            print(f"⚠️ [WARNING] Missing headers in CSV: {missing_headers}")
            return

        valid_entries = []
        skipped_count = 0

        for row_index, row in enumerate(csv_reader, 1):
            try:
                ride_type = row[header_map["Ride Type"]]
                postcode = row[header_map["Postcode"]]
                address_line1 = row[header_map["Address Line 1"]]
                address_line2 = row[header_map["Address Line 2"]]
                city = row[header_map["City"]]
                address = f"{address_line1}, {address_line2}, {city}".strip(", ")
                delivery_notes = row[header_map["Delivery Instructions"]]
                customer_name = row[header_map["Customer Name"]]
                customer_phone = row[header_map["Customer Phone Number"]]
                box_number = row[header_map["Box Number"]]

                # Validate postcode
                if not re.match(r"^[A-Z]{1,2}\d[A-Z\d]? ?\d[A-Z]{2}$", postcode.replace(" ", "").upper()):
                    print(f"⚠️ [WARNING] Invalid postcode at row {row_index}. Skipping.")
                    skipped_count += 1
                    continue

                driver_id = assign_driver(postcode)
                delivery_id = f"DELIVERY#{uuid.uuid4().hex}"
                sort_key = f"POSTCODE#{postcode}#{ride_type}#{box_number}"

                valid_entries.append({
                    'PK': delivery_id,
                    'SK': sort_key,
                    'RideType': ride_type,
                    'DriverID': driver_id,
                    'Address': address,
                    'DeliveryNotes': delivery_notes,
                    'CustomerName': customer_name,
                    'CustomerPhone': customer_phone,
                    'BoxNumber': box_number,
                    'PostcodeRaw': postcode,
                    'CreatedAt': int(time.time())
                })

            except Exception as e:
                print(f"❌ [ERROR] Error processing row {row_index}: {str(e)}")
                skipped_count += 1
                continue

        # Store in DynamoDB
        with delivery_table.batch_writer() as writer:
            for entry in valid_entries:
                writer.put_item(Item=entry)

        print(f"✅ [COMPLETE] Processed {len(valid_entries)} entries. Skipped: {skipped_count}")

        # Move file to processed folder
        processed_key = key.replace('incoming/', 'processed/')
        s3.copy_object(Bucket=bucket, Key=processed_key, CopySource={'Bucket': bucket, 'Key': key})
        s3.delete_object(Bucket=bucket, Key=key)

        # Trigger Optimization Lambda
        invoke_optimization_lambda()

    except Exception as e:
        print(f"❌ [ERROR] Failed to process delivery manifest: {str(e)}")

def update_driver_eta_from_csv(bucket, key):
    """Reads optimized routes CSV and updates DriverLocations in DynamoDB with ETA."""
    try:
        response = s3.get_object(Bucket=bucket, Key=key)
        content = response['Body'].read().decode('utf-8-sig').splitlines()
        csv_reader = csv.reader(content)
        header = next(csv_reader, None)

        print(f"ℹ️ [INFO] Optimized Routes CSV Headers: {header}")

        required_headers = ["DriverID", "Postcode", "EstimatedArrivalTime", "EstimatedDuration"]
        header_map = {h.strip(): i for i, h in enumerate(header)}

        missing_headers = [h for h in required_headers if h not in header_map]
        if missing_headers:
            print(f"⚠️ [WARNING] Missing headers in CSV: {missing_headers}")
            return

        for row in csv_reader:
            driver_id = row[header_map["DriverID"]]
            postcode = row[header_map["Postcode"]]
            eta = row[header_map["EstimatedArrivalTime"]]
            duration = row[header_map["EstimatedDuration"]]

            # Store data in DriverLocations table
            driver_table.put_item(
                Item={
                    'DriverID': driver_id,
                    'Postcode': postcode,
                    'EstimatedArrivalTime': eta,
                    'EstimatedDuration': duration
                }
            )
            print(f"✅ [UPDATED] Stored ETA for driver {driver_id} in DynamoDB.")

    except Exception as e:
        print(f"❌ [ERROR] Failed to process Optimized Routes CSV: {str(e)}")

def lambda_handler(event, context):
    print("🚀 [START] Lambda Function Triggered - Processing Manifest")

    try:
        record = event['Records'][0]
        bucket = record['s3']['bucket']['name']
        key = record['s3']['object']['key']
    except KeyError:
        print("❌ [ERROR] Missing 'Records' in event.")
        return {'statusCode': 400, 'body': 'Invalid event structure'}

    print(f"📂 [FILE] Checking for file: s3://{bucket}/{key}")

    if "incoming" in key and key.endswith('.csv'):
        print("📂 [INFO] Processing Delivery Manifest CSV.")
        process_manifest(bucket, key)

    elif "optimized" in key and key.endswith('.csv'):
        print("📂 [INFO] Processing Optimized Routes CSV for ETA updates.")
        update_driver_eta_from_csv(bucket, key)

    return {'statusCode': 200, 'body': 'File processed successfully'}
