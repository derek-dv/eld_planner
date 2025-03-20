from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from .osm_integration.osm_client import OSMRouteClient
from .hos_calculator import HOSCalculator
import json

class RouteCalculator(APIView):
    def post(self, request, format=None):
        #try:
        # Extract data from request
        current_location = request.data.get('current_location')
        pickup_location = request.data.get('pickup_location')
        dropoff_location = request.data.get('dropoff_location')
        current_cycle_hours = float(request.data.get('current_cycle_hours', 0))
        
        # Validate inputs
        if not all([current_location, pickup_location, dropoff_location]):
            return Response(
                {"error": "Missing required location data"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Initialize clients
        osm_client = OSMRouteClient()
        hos_calculator = HOSCalculator()
        
        # Calculate route segments
        route_segments = []
        
        # Current to pickup
        current_to_pickup = osm_client.get_route(
            (current_location['lng'], current_location['lat']),
            (pickup_location['lng'], pickup_location['lat'])
        )
        route_segments.append({
            'start_name': current_location.get('name', 'Current Location'),
            'end_name': pickup_location.get('name', 'Pickup Location'),
            'distance_miles': current_to_pickup['distance_miles'],
            'duration_hours': current_to_pickup['duration_hours'],
            'geometry': current_to_pickup['geometry']
        })
        
        # Pickup to dropoff
        pickup_to_dropoff = osm_client.get_route(
            (pickup_location['lng'], pickup_location['lat']),
            (dropoff_location['lng'], dropoff_location['lat'])
        )
        route_segments.append({
            'start_name': pickup_location.get('name', 'Pickup Location'),
            'end_name': dropoff_location.get('name', 'Dropoff Location'),
            'distance_miles': pickup_to_dropoff['distance_miles'],
            'duration_hours': pickup_to_dropoff['duration_hours'],
            'geometry': pickup_to_dropoff['geometry']
        })
        
        # Calculate schedule with HOS rules
        schedule = hos_calculator.calculate_route_schedule(route_segments, current_cycle_hours)
        
        # Generate ELD logs
        eld_logs = hos_calculator.generate_eld_logs(schedule)
        
        # Calculate waypoints for the map
        waypoints = []
        waypoints.append({
            'name': current_location.get('name', 'Current Location'),
            'lat': current_location['lat'],
            'lng': current_location['lng'],
            'type': 'START'
        })
        
        waypoints.append({
            'name': pickup_location.get('name', 'Pickup Location'),
            'lat': pickup_location['lat'],
            'lng': pickup_location['lng'],
            'type': 'PICKUP'
        })
        
        # Add rest stops and fuel stops
        for item in schedule:
            print(item)
            if item['activity_type'] in ['FUEL']:
                waypoints.append({
                    'name': f"{item['activity_type']} Stop",
                        'lat': item['coord'][1],
                        'lng': item['coord'][0],
                        'type': item['activity_type']
                })
            if item['activity_type'] in ['REST', 'BREAK']:
                segment_index = item['location_index']
                    
                waypoints.append({
                    'name': f"{item['activity_type']} Stop",
                    'lat': item['coord'][1],
                    'lng': item['coord'][0],
                    'type': 'REST'
                })
        
        waypoints.append({
            'name': dropoff_location.get('name', 'Dropoff Location'),
            'lat': dropoff_location['lat'],
            'lng': dropoff_location['lng'],
            'type': 'DROPOFF'
        })
        
        # Calculate total trip stats
        total_distance = sum(segment['distance_miles'] for segment in route_segments)
        total_driving_hours = sum(segment['duration_hours'] for segment in route_segments)
        total_trip_days = max(item['day'] for item in schedule)
        
        return Response({
            'route_segments': route_segments,
            'schedule': schedule,
            'eld_logs': eld_logs,
            'waypoints': waypoints,
            'stats': {
                'total_distance': total_distance,
                'total_driving_hours': total_driving_hours,
                'total_trip_days': total_trip_days
            }
        })
        
        # except Exception as e:
            
        #     print(e)
        #     return Response(
        #         {"error": str(e)},
        #         status=status.HTTP_500_INTERNAL_SERVER_ERROR
        #     )
