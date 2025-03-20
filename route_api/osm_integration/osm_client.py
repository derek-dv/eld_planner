import requests
import json
from math import radians, cos, sin, asin, sqrt

class OSMRouteClient:
    def __init__(self):
        self.base_url = "https://router.project-osrm.org/route/v1/driving"
    
    def get_route(self, start_coords, end_coords):
        """
        Get route information between two coordinates
        
        Args:
            start_coords: Tuple of (longitude, latitude)
            end_coords: Tuple of (longitude, latitude)
            
        Returns:
            dict: Route information including distance (meters) and duration (seconds)
        """
        # Format coordinates for OSRM API
        coords_str = f"{start_coords[0]},{start_coords[1]};{end_coords[0]},{end_coords[1]}"
        url = f"{self.base_url}/{coords_str}?overview=full&geometries=geojson"
        
        response = requests.get(url)
        if response.status_code != 200:
            raise Exception(f"OpenStreetMap API error: {response.status_code}")
        
        data = response.json()
        if data.get('code') != 'Ok':
            raise Exception(f"OpenStreetMap routing error: {data.get('message', 'Unknown error')}")
        
        route = data['routes'][0]
        
        # Convert meters to miles and seconds to hours
        distance_miles = route['distance'] * 0.000621371  # Convert meters to miles
        duration_hours = route['duration'] / 3600  # Convert seconds to hours
        
        return {
            'distance_miles': distance_miles,
            'duration_hours': duration_hours,
            'geometry': route['geometry'],
        }
    
    @staticmethod
    def haversine_distance(lon1, lat1, lon2, lat2):
        """
        Calculate the great circle distance between two points 
        on the earth (specified in decimal degrees)
        """
        # Convert decimal degrees to radians
        lon1, lat1, lon2, lat2 = map(radians, [lon1, lat1, lon2, lat2])
        
        # Haversine formula
        dlon = lon2 - lon1
        dlat = lat2 - lat1
        a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
        c = 2 * asin(sqrt(a))
        r = 3956  # Radius of earth in miles
        
        return c * r
    
    def get_coordinates_along_route(self, start_coords, end_coords, num_points=10):
        """
        Get evenly spaced coordinates along a route
        """
        route_data = self.get_route(start_coords, end_coords)
        coordinates = route_data['geometry']['coordinates']
        
        # Get evenly spaced indices
        total_points = len(coordinates)
        indices = [int(i * (total_points - 1) / (num_points - 1)) for i in range(num_points)]
        
        # Extract coordinates at those indices
        return [coordinates[i] for i in indices]