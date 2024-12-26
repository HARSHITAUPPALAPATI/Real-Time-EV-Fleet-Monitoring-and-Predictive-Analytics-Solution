import requests
import math

# Haversine formula to calculate distance between two points on Earth
def haversine(lat1, lon1, lat2, lon2):
    R = 6371.0  # Radius of Earth in km
    lat1_rad = math.radians(lat1)
    lon1_rad = math.radians(lon1)
    lat2_rad = math.radians(lat2)
    lon2_rad = math.radians(lon2)

    dlon = lon2_rad - lon1_rad
    dlat = lat2_rad - lat1_rad

    a = math.sin(dlat / 2) ** 2 + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(dlon / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    return R * c  # Distance in kilometers

# Get city coordinates using OpenCage API
def get_city_coordinates(api_key, city_name):
    url = f"https://api.opencagedata.com/geocode/v1/json?q={city_name}&key={api_key}"
    response = requests.get(url)
    if response.status_code == 200:
        data = response.json()
        if data['results']:
            lat = data['results'][0]['geometry']['lat']
            lng = data['results'][0]['geometry']['lng']
            return {'lat': lat, 'lng': lng}
    return None

# Find best charging stations based on the battery level and route
def find_best_stations(api_key, source_coords, dest_coords, battery_level):
    # Midpoint coordinates between source and destination
    midpoint_lat = (source_coords['lat'] + dest_coords['lat']) / 2
    midpoint_lng = (source_coords['lng'] + dest_coords['lng']) / 2

    try:
        battery = float(battery_level)  # Convert battery level to a float
    except ValueError:
        return []  # If conversion fails, return an empty list

    max_distance = (battery / 100) * 300  # Max distance based on battery (300 km for 100% battery)

    # Get stations along the route
    url = f"https://api.openchargemap.io/v3/poi/"
    params = {
        'key': api_key,
        'latitude': midpoint_lat,
        'longitude': midpoint_lng,
        'distance': max_distance,
        'maxresults': 10,
        'compact': 'true',
    }
    response = requests.get(url, params=params)
    if response.status_code != 200:
        print(f"Error: {response.status_code}")
        return []

    stations = response.json()

    # Filter stations within the max distance
    filtered_stations = []
    for station in stations:
        address_info = station.get("AddressInfo", {})
        lat = address_info.get("Latitude", None)
        lng = address_info.get("Longitude", None)

        if lat and lng:
            distance = haversine(midpoint_lat, midpoint_lng, lat, lng)
            if distance <= max_distance:
                connections = station.get("Connections", [{}])
                filtered_stations.append({
                    "name": address_info.get("Title", "Unknown Station"),
                    "lat": lat,
                    "lng": lng,
                    "distance": distance,
                    "charging_speed": connections[0].get("PowerKW", 0)  # First connection's power
                })

    # Filter out stations with missing or None values for distance or charging_speed
    filtered_stations = [
        station for station in filtered_stations
        if station["distance"] is not None and station["charging_speed"] is not None
    ]

    # Sort stations by distance (ascending) and charging speed (descending)
    sorted_stations = sorted(filtered_stations, key=lambda x: (x["distance"], -x["charging_speed"]))

    # Return the top 3 stations
    return sorted_stations[:3]
