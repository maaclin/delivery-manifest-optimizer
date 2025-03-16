import boto3
import requests
import json
import time
import csv
import io
import re
import uuid
import os

# Initialize AWS Services
dynamodb = boto3.resource('dynamodb')
table = dynamodb.Table('DeliveryManagement')
s3 = boto3.client('s3')
BUCKET_NAME = 'delivery-manifest-bucket'

# Geoapify API Key
GEOAPIFY_API_KEY = "1c41c1d950804e16a38f96dee7966703"

# Geoapify API URLs
GEOAPIFY_GEOCODING_URL = "https://api.geoapify.com/v1/geocode/search"
GEOAPIFY_ROUTING_URL = "https://api.geoapify.com/v1/routeplanner"

# Fixed start location
START_LOCATION = "1-3 Britannia Way, London NW10 7PR"

def get_coordinates_from_address(address):
    """
    Convert UK addresses into latitude & longitude using Geoapify Geocoding API.
    Returns a tuple (longitude, latitude).
    """
    print(f"🔍 Geocoding address: {address}")
    
    # Format postcode if it's just a postcode (remove spaces and convert to uppercase)
    postcode_pattern = re.compile(r'^[A-Za-z]{1,2}[0-9][A-Za-z0-9]? ?[0-9][A-Za-z]{2}$')
    if postcode_pattern.match(address.strip()):
        formatted_postcode = address.strip().replace(" ", "").upper()
        # Insert space in the correct position for UK postcode
        if len(formatted_postcode) > 3:
            formatted_postcode = formatted_postcode[:-3] + " " + formatted_postcode[-3:]
        address = formatted_postcode
        print(f"📮 Formatted postcode: {address}")

    # Base parameters for the API request
    params = {
        "apiKey": GEOAPIFY_API_KEY,
        "text": address,
        "format": "json",
        "lang": "en",
        "limit": 1
    }
    
    try:
        response = requests.get(GEOAPIFY_GEOCODING_URL, params=params)
        print(f"Geocoding response status: {response.status_code}")
        response.raise_for_status()
        data = response.json()
        
        if "results" in data and data["results"]:
            result = data["results"][0]
            lat = result.get("lat")
            lon = result.get("lon")
            
            if lat is None or lon is None:
                print(f"⚠ No coordinates found in result for {address}")
                return None
            
            # Validate the result is in London (roughly within M25)
            if not (51.2 <= lat <= 51.8 and -0.6 <= lon <= 0.4):
                print(f"⚠ Warning: Coordinates for {address} are outside London area")
                print(f"   Location found: {result.get('formatted')}")
                print(f"   Coordinates: lat={lat}, lon={lon}")
                return None
                
            print(f"✅ Found coordinates for {address}:")
            print(f"   Location: {result.get('formatted', 'Unknown location')}")
            print(f"   Postcode: {result.get('postcode', 'Unknown postcode')}")
            print(f"   District: {result.get('district', 'Unknown district')}")
            print(f"   Result type: {result.get('result_type', 'Unknown type')}")
            print(f"   Coordinates: lon={lon}, lat={lat}")
            return (lon, lat)
        else:
            print(f"⚠ Geocoding failed for {address}: No results found")
            if "message" in data:
                print(f"   API Message: {data['message']}")
            return None
            
    except Exception as e:
        print(f"⚠ Geocoding request failed for {address}: {str(e)}")
        if hasattr(e, 'response') and hasattr(e.response, 'text'):
            print(f"Response text: {e.response.text}")
        return None

def optimize_route_with_planner(locations, start_coords):
    """
    Optimize route using Geoapify Route Planner API.
    Takes into account real-time traffic and provides the most efficient route.
    Finds the quickest straight-line journey without requiring return to start.
    """
    print(f"🔍 Computing optimal route for {len(locations)} locations using Route Planner...")
    
    # Log the input locations for debugging
    print("Input locations:")
    for idx, loc in enumerate(locations):
        print(f"Location {idx}: lon={loc['lon']}, lat={loc['lat']}")
    print(f"Start coordinates: lon={start_coords[0]}, lat={start_coords[1]}")

    # Create the agent (delivery vehicle)
    agent = {
        "id": "driver1",
        "start_location": start_coords,  # Already in [lon, lat] format
        # We don't specify end_location so vehicle doesn't need to return to start
        "capabilities": ["time_windows"]  # Enable time window support
    }

    # Prepare jobs (delivery locations)
    jobs = []
    for idx, loc in enumerate(locations):
        jobs.append({
            "id": f"delivery_{idx}",
            "location": [loc["lon"], loc["lat"]],
            "duration": 300,  # 5 minutes service time at each stop
            "priority": 1,    # All deliveries have equal priority
            "time_windows": [
                [32400, 64800]  # 9:00 AM to 6:00 PM in seconds from midnight
            ]
        })

    # Prepare the request body
    body = {
        "mode": "drive",
        "agents": [agent],
        "jobs": jobs,
        "options": {
            "traffic": "live",           # Use live traffic data
            "optimize_for": "time",      # Optimize for minimum time
            "travel_time": "enabled",    # Include travel time calculations
            "road_snapping": "enabled",  # Snap routes to roads
            "shortest_path": "enabled"   # Prefer shortest path when possible
        }
    }

    # Build the URL with API key
    url = f"{GEOAPIFY_ROUTING_URL}?apiKey={GEOAPIFY_API_KEY}"

    try:
        print("Sending request to Geoapify Route Planner API...")
        print(f"Request body: {json.dumps(body, indent=2)}")
        
        response = requests.post(url, json=body)
        print(f"Response status code: {response.status_code}")
        
        if response.status_code != 200:
            print(f"API Error Response: {response.text}")
            return None
            
        data = response.json()

        if "features" in data and len(data["features"]) > 0:
            route_feature = data["features"][0]["properties"]
            
            if "actions" not in route_feature:
                print("⚠ No actions found in route response")
                return None

            # Extract the job sequence from actions
            optimized_sequence = []
            
            for action in route_feature["actions"]:
                if action["type"] == "job":
                    job_id = action["job_id"]
                    index = int(job_id.split('_')[1])
                    optimized_sequence.append(index)
                    
                    # Track timing for this stop
                    if "start_time" in action:
                        arrival_time = time.strftime('%H:%M', time.gmtime(action["start_time"]))
                        print(f"Stop {index}: Estimated arrival at {arrival_time}")
            
            if not optimized_sequence:
                print("⚠ No delivery sequence found in route")
                return None

            # Calculate total route statistics
            total_time = route_feature["time"]
            total_distance = route_feature.get("distance", 0)
            print(f"📊 Route Statistics:")
            print(f"   Total duration: {total_time//3600}h {(total_time%3600)//60}m {total_time%60}s")
            print(f"   Total distance: {total_distance/1000:.1f} km")
            print(f"   Number of stops: {len(optimized_sequence)}")
            print(f"   Optimized sequence: {optimized_sequence}")
                        
            return optimized_sequence
        else:
            print("⚠ Route Planner API error: No route found in response")
            
            # Fallback to a simple straight-line distance algorithm if API fails
            print("Falling back to simple straight-line optimization...")
            
            # Simple greedy algorithm for nearest neighbor
            # This is a fallback if the API fails
            remaining = list(range(len(locations)))
            current = None  # Start point
            order = []
            
            # Start with the location closest to the starting point
            nearest = -1
            nearest_dist = float('inf')
            for i, loc in enumerate(locations):
                dx = loc['lon'] - start_coords[0]
                dy = loc['lat'] - start_coords[1]
                dist = (dx * dx + dy * dy) ** 0.5
                if dist < nearest_dist:
                    nearest_dist = dist
                    nearest = i
            
            if nearest >= 0:
                order.append(nearest)
                current = nearest
                remaining.remove(nearest)
            
            # Build rest of route by always going to the nearest unvisited location
            while remaining:
                nearest = -1
                nearest_dist = float('inf')
                for i in remaining:
                    dx = locations[i]['lon'] - locations[current]['lon']
                    dy = locations[i]['lat'] - locations[current]['lat']
                    dist = (dx * dx + dy * dy) ** 0.5
                    if dist < nearest_dist:
                        nearest_dist = dist
                        nearest = i
                
                if nearest >= 0:
                    order.append(nearest)
                    current = nearest
                    remaining.remove(nearest)
            
            print(f"Fallback straight-line optimization: {order}")
            return order

    except Exception as e:
        print(f"⚠ Exception during route optimization: {str(e)}")
        if hasattr(e, 'response') and hasattr(e.response, 'text'):
            print(f"Response text: {e.response.text}")
        return None

def update_route_sequence(driver_id, deliveries, optimized_sequence):
    """
    Update the RouteSequence attribute for each delivery in DynamoDB.
    """
    success_count = 0
    for i, original_index in enumerate(optimized_sequence):
        try:
            delivery = deliveries[original_index]
            delivery_id = delivery["PK"]
            sk_value = delivery["SK"]
            
            # Update DynamoDB with the optimized sequence
            table.update_item(
                Key={"PK": delivery_id, "SK": sk_value},
                UpdateExpression="SET RouteSequence = :seq",
                ExpressionAttributeValues={":seq": i + 1}
            )
            success_count += 1
            
            # Update the local delivery object for CSV export
            deliveries[original_index]["RouteSequence"] = i + 1
            
        except Exception as e:
            print(f"⚠ Failed to update sequence for delivery at index {original_index}: {str(e)}")
    
    print(f"✅ Updated sequence for {success_count}/{len(optimized_sequence)} deliveries")
    return success_count

def export_driver_routes_to_csv(driver_id, deliveries):
    """
    Generate a CSV file for each driver's optimized route and upload it to S3.
    """
    csv_buffer = io.StringIO()
    writer = csv.writer(csv_buffer)
    writer.writerow([
        "RouteSequence", 
        "DeliveryID", 
        "Postcode", 
        "Address", 
        "CustomerName", 
        "CustomerPhone", 
        "EstimatedArrivalTime"
    ])
    
    # Sort deliveries by RouteSequence
    sorted_deliveries = sorted(deliveries, key=lambda x: x.get("RouteSequence", 999))
    
    # Calculate estimated arrival times based on real route timing
    start_time = 9 * 60  # 9:00 AM in minutes from midnight
    
    for idx, delivery in enumerate(sorted_deliveries):
        if "RouteSequence" not in delivery:
            continue
            
        # Calculate estimated arrival time (simple approximation)
        arrival_minutes = start_time + idx * 15
        hours = arrival_minutes // 60
        minutes = arrival_minutes % 60
        arrival_time = f"{hours:02d}:{minutes:02d}"
        
        writer.writerow([
            delivery.get("RouteSequence", ""),
            delivery.get("PK", ""),
            delivery.get("PostcodeRaw", ""),
            delivery.get("Address", ""),
            delivery.get("CustomerName", ""),
            delivery.get("CustomerPhone", ""),
            arrival_time
        ])
    
    # Upload to S3
    timestamp = int(time.time())
    s3_key = f"driver_routes/{driver_id}_optimized_route_{timestamp}.csv"
    s3.put_object(
        Bucket=BUCKET_NAME, 
        Key=s3_key, 
        Body=csv_buffer.getvalue(),
        ContentType='text/csv'
    )
    print(f"✅ Uploaded optimized route CSV for {driver_id} to S3: {s3_key}")
    return s3_key

def lambda_handler(event, context):
    print("🚀 Optimizing Delivery Routes using Geoapify Route Planner with fixed start location...")
    start_time = time.time()

    # Scan DynamoDB for deliveries
    try:
        response = table.scan()
        deliveries = response.get("Items", [])
    except Exception as e:
        print(f"⚠ Failed to scan table {table.name}: {str(e)}")
        return {'statusCode': 500, 'body': 'Failed to scan DynamoDB table'}
    
    if not deliveries:
        print("⚠ No deliveries found in DynamoDB!")
        return {'statusCode': 400, 'body': 'No deliveries found'}

    print(f"📦 Found {len(deliveries)} total deliveries")
    
    # Group deliveries by driver; collect unique addresses
    grouped_deliveries = {}
    unique_addresses = {START_LOCATION}
    
    # Print all addresses/postcodes for debugging
    print("\n📬 Delivery Addresses/Postcodes:")
    for delivery in deliveries:
        postcode = delivery.get("PostcodeRaw", "").strip()
        print(f"Postcode: {postcode}")
        
        if not postcode:
            print(f"⚠ Warning: Delivery {delivery.get('PK', 'unknown')} has no postcode. Skipping.")
            continue
            
        unique_addresses.add(postcode)  # Use postcode instead of full address
        
        driver_id = delivery.get("DriverID", "Unassigned")
        if driver_id not in grouped_deliveries:
            grouped_deliveries[driver_id] = []
            
        grouped_deliveries[driver_id].append(delivery)

    print(f"\n🗺️ Processing {len(unique_addresses)} unique addresses for {len(grouped_deliveries)} drivers")

    # Geocode all unique addresses
    address_to_coords = {}
    for address in unique_addresses:
        coords = get_coordinates_from_address(address)
        if coords:
            address_to_coords[address] = coords
        else:
            print(f"⚠ Could not geocode address: {address}")
    
    if not address_to_coords:
        print("⚠ No valid coordinates fetched for addresses!")
        return {'statusCode': 400, 'body': 'Failed to fetch coordinates'}

    # Get start coordinates from fixed start location
    start_coords = address_to_coords.get(START_LOCATION)
    if not start_coords:
        print(f"⚠ Could not geocode start location: {START_LOCATION}")
        return {'statusCode': 400, 'body': 'Failed to geocode start location'}

    # Store results for the response
    results = {
        "optimized_drivers": 0,
        "total_deliveries_sequenced": 0,
        "driver_routes": {}
    }

    # Optimize routes for each driver
    for driver, stops in grouped_deliveries.items():
        print(f"\n🚗 Optimizing route for {driver}: {len(stops)} stops")
        
        locations = []
        original_indices = []
        postcode_mapping = []  # Store postcodes for each location
        
        # Prepare geocoded locations for this driver's stops
        for index, stop in enumerate(stops):
            postcode = stop.get("PostcodeRaw", "").strip()  # Use PostcodeRaw instead of Address
            coords = address_to_coords.get(postcode)
            
            if not coords:
                print(f"⚠ Warning: No valid coordinates for postcode {postcode}. Skipping.")
                continue
                
            locations.append({"lat": coords[1], "lon": coords[0]})
            original_indices.append(index)
            postcode_mapping.append(postcode)  # Store the postcode
        
        if len(locations) < 2:  # Need at least 2 locations to optimize
            print(f"⚠ Not enough valid stops for {driver} to optimize")
            continue
        
        # Optimize the route using Route Planner API
        optimized_sequence = optimize_route_with_planner(locations, start_coords)
        
        if optimized_sequence:
            # Map optimized indices back to original stops
            original_optimized_sequence = [original_indices[i] for i in optimized_sequence]
            
            # Print the human-readable route
            print("\n📍 Human-Readable Route:")
            print(f"Start: {START_LOCATION}")
            for i, idx in enumerate(optimized_sequence):
                postcode = postcode_mapping[idx]
                print(f"Stop {i+1}: {postcode}")
            
            # Update the route sequence in DynamoDB
            deliveries_updated = update_route_sequence(driver, stops, original_optimized_sequence)
            
            # Export the route to CSV and upload to S3
            s3_key = export_driver_routes_to_csv(driver, stops)
            
            # Update results
            results["optimized_drivers"] += 1
            results["total_deliveries_sequenced"] += deliveries_updated
            results["driver_routes"][driver] = {
                "stops": len(original_optimized_sequence),
                "csv_url": f"s3://{BUCKET_NAME}/{s3_key}",
                "route": [START_LOCATION] + [postcode_mapping[idx] for idx in optimized_sequence]
            }
            
            print(f"✅ Successfully optimized route for {driver}")
        else:
            print(f"⚠ Failed to optimize route for {driver}")
    
    # Calculate execution time
    execution_time = time.time() - start_time
    print(f"⏱️ Route optimization completed in {execution_time:.2f} seconds")
    
    return {
        'statusCode': 200, 
        'body': json.dumps({
            'message': 'Route optimization completed',
            'results': results
        })
    } 