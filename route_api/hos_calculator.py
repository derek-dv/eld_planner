from geopy.distance import geodesic
from collections import deque


class HOSCalculator:
    def __init__(self):
        # Property-carrying driver: 11-hour driving limit, 14-hour on-duty limit, 70 hrs/8 days
        self.max_daily_driving_hours = 11.0
        self.max_daily_duty_hours = 14.0
        self.min_rest_period_hours = 10.0
        self.required_break_after_hours = 8.0
        self.required_break_duration_hours = 0.5
        self.max_cycle_hours = 70.0
        self.cycle_days = 8
        self.fuel_distance_miles = 1000.0
        self.fuel_duration_hours = 1.0
        self.pickup_duration_hours = 1.0
        self.dropoff_duration_hours = 1.0


    @staticmethod
    def find_location_after_distance(route, target_distance_miles):
        """
        Find the point along a route after traveling a specific distance.
        
        Args:
            route: List of [lon, lat] coordinates
            target_distance_miles: Distance to travel along the route
            
        Returns:
            Tuple of ([lon, lat], remaining_route)
        """
        if not route or len(route) < 2:
            # Return the last point if route is empty or has only one point
            return route[-1] if route else [0, 0], []
        
        distance_traveled = 0
        
        for i in range(len(route) - 1):
            start, end = route[i], route[i + 1]
            
            # Check that coordinates are valid
            if len(start) < 2 or len(end) < 2:
                continue
                
            try:
                # Swap to (lat, lon) for geodesic
                segment_distance = geodesic((start[1], start[0]), (end[1], end[0])).miles
            except Exception:
                # Skip this segment if calculation fails
                continue
            
            if distance_traveled + segment_distance >= target_distance_miles:
                # Interpolate between start and end to find exact location
                remaining_distance = target_distance_miles - distance_traveled
                ratio = max(0, min(1, remaining_distance / segment_distance if segment_distance > 0 else 0))
                lon = start[0] + ratio * (end[0] - start[0])
                lat = start[1] + ratio * (end[1] - start[1])
                return [lon, lat], route[i+1:]
            
            distance_traveled += segment_distance
        
        # If we can't reach the target distance, return the last point
        return route[-1], []
    
    def calculate_route_schedule(self, route_segments, initial_hours_used, pickup_location_index=0):
        """
        Calculate a schedule including driving, breaks, and rest periods
        
        Args:
            route_segments: List of dict with distance_miles and duration_hours
            initial_hours_used: Hours already used in the current cycle
            pickup_location_index: Index of segment where pickup occurs (default is 0)
            
        Returns:
            List of dict with activity details and locations
        """
        schedule = []
        current_day_driving = 0.0
        current_day_duty = 0.0
        hours_since_break = 0.0
        cycle_hours_used = initial_hours_used
        current_day = 1
        distance_since_fuel = 0.0
        pickup_done = False
        current_location = [0, 0]  # Default starting location
        
        # Track daily duty hours for the 8-day cycle
        # Initialize with the initial hours used for the first day
        daily_duty_hours = deque([initial_hours_used] + [0.0] * (self.cycle_days - 1), maxlen=self.cycle_days)
        
        for i, segment in enumerate(route_segments):
            segment_driving_hours = segment['duration_hours']
            segment_miles = segment['distance_miles']
            
            speed_mph = segment_miles / segment_driving_hours if segment_driving_hours > 0 else 55.0  # Default speed
            remaining_segment_hours = segment_driving_hours
            
            coords = []
            try:
                coords = segment.get("geometry", {}).get("coordinates", [])
                # Ensure we have valid coordinates
                if not coords or len(coords) < 2:
                    coords = [[0, 0], [0, 0]]  # Default placeholder
                if coords and len(coords) > 0:
                    current_location = coords[0]  # Update current location to start of segment
            except (AttributeError, TypeError):
                coords = [[0, 0], [0, 0]]  # Default placeholder
            
            remaining_coords = coords.copy()
            
            # Handle pickup at the specified location index
            if i == pickup_location_index and not pickup_done:
                schedule.append({
                    'activity_type': 'PICKUP',
                    'location_index': i,
                    'duration_hours': self.pickup_duration_hours,
                    'day': current_day,
                    'start_duty_hours': current_day_duty,
                    'end_duty_hours': current_day_duty + self.pickup_duration_hours,
                    'coord': current_location  # Add coordinates to pickup activity
                })
                
                current_day_duty += self.pickup_duration_hours
                hours_since_break += self.pickup_duration_hours
                cycle_hours_used += self.pickup_duration_hours
                daily_duty_hours[0] += self.pickup_duration_hours  # Update today's hours
                pickup_done = True
                       
            while remaining_segment_hours > 0:
                # Check if 30-min break needed
                if hours_since_break >= self.required_break_after_hours:
                    schedule.append({
                        'activity_type': 'BREAK',
                        'location_index': i,
                        'duration_hours': self.required_break_duration_hours,
                        'day': current_day,
                        'start_duty_hours': current_day_duty,
                        'end_duty_hours': current_day_duty + self.required_break_duration_hours,
                        'coord': current_location  # Add coordinates to break activity
                    })
                    
                    current_day_duty += self.required_break_duration_hours
                    cycle_hours_used += self.required_break_duration_hours
                    daily_duty_hours[0] += self.required_break_duration_hours  # Update today's hours
                    hours_since_break = 0
                
                # Calculate total hours for the current 8-day cycle
                total_cycle_hours = sum(daily_duty_hours)
                
                # Check available driving time for this segment, including 70-hour/8-day rule
                remaining_cycle_hours = max(0, self.max_cycle_hours - total_cycle_hours)
                
                available_day_driving = min(
                    self.max_daily_driving_hours - current_day_driving,  # Daily driving limit
                    self.max_daily_duty_hours - current_day_duty,        # Daily duty limit
                    remaining_cycle_hours,                              # 70-hour/8-day limit
                    remaining_segment_hours                              # Remaining segment to drive
                )
                
                # If we can't drive anymore today or hit cycle limit, take a rest
                if available_day_driving <= 0:
                    # Check if it's due to the 70-hour rule
                    if remaining_cycle_hours <= 0:
                        # Need a 34-hour restart
                        schedule.append({
                            'activity_type': 'RESTART',
                            'location_index': i,
                            'duration_hours': 34.0,
                            'day': current_day,
                            'start_duty_hours': current_day_duty,
                            'end_duty_hours': 0,  # Reset for next day
                            'coord': current_location,
                            'restart_type': '34-hour'
                        })
                        
                        current_day += 2  # 34-hour rest spans at least 2 days
                        current_day_driving = 0
                        current_day_duty = 0
                        hours_since_break = 0
                        
                        # Reset the cycle hours tracking
                        daily_duty_hours = deque([0.0] * self.cycle_days, maxlen=self.cycle_days)
                        cycle_hours_used = 0
                    else:
                        # Regular 10-hour rest period
                        schedule.append({
                            'activity_type': 'REST',
                            'location_index': i,
                            'duration_hours': self.min_rest_period_hours,
                            'day': current_day,
                            'start_duty_hours': current_day_duty,
                            'end_duty_hours': 0,  # Reset for next day
                            'coord': current_location  # Add coordinates to rest activity
                        })
                        
                        current_day += 1
                        current_day_driving = 0
                        current_day_duty = 0
                        hours_since_break = 0
                        
                        # Shift the daily duty hours tracking for the next day
                        daily_duty_hours.append(0.0)  # This will push out the oldest day
                    
                    continue
                
                # Calculate distance covered in this driving session
                distance_covered = speed_mph * available_day_driving
                
                # Find the location after driving this distance
                if remaining_coords and len(remaining_coords) > 1:
                    try:
                        new_location, updated_remaining_coords = self.find_location_after_distance(
                            remaining_coords, 
                            distance_covered
                        )
                        current_location = new_location  # Update current location
                        if updated_remaining_coords:
                            remaining_coords = updated_remaining_coords
                    except Exception:
                        # If there's an error, keep the current location
                        pass
                
                # Add driving activity
                schedule.append({
                    'activity_type': 'DRIVING',
                    'location_index': i,
                    'duration_hours': available_day_driving,
                    'distance_miles': distance_covered,
                    'day': current_day,
                    'start_duty_hours': current_day_duty,
                    'end_duty_hours': current_day_duty + available_day_driving,
                    'coord': current_location,  # Add coordinates to driving activity
                    'cycle_hours_remaining': self.max_cycle_hours - (total_cycle_hours + available_day_driving)
                })
                
                current_day_driving += available_day_driving
                current_day_duty += available_day_driving
                hours_since_break += available_day_driving
                cycle_hours_used += available_day_driving
                daily_duty_hours[0] += available_day_driving  # Update today's hours
                remaining_segment_hours -= available_day_driving
                
                # Update distance since last fuel stop
                distance_since_fuel += distance_covered
                
                # Check if we need to fuel
                if distance_since_fuel >= self.fuel_distance_miles and remaining_coords:
                    try:
                        # Find the exact location for fueling
                        fuel_distance = min(distance_since_fuel, self.fuel_distance_miles)
                        fuel_location, updated_remaining_coords = self.find_location_after_distance(
                            remaining_coords, 
                            fuel_distance
                        )
                        
                        # Update the current location
                        current_location = fuel_location
                        
                        # Update the remaining coordinates if valid
                        if updated_remaining_coords:
                            remaining_coords = updated_remaining_coords
                        
                        # Add fueling activity
                        schedule.append({
                            'activity_type': 'FUEL',
                            'location_index': i,
                            'duration_hours': self.fuel_duration_hours,
                            'coord': current_location,
                            'day': current_day,
                            'start_duty_hours': current_day_duty,
                            'end_duty_hours': current_day_duty + self.fuel_duration_hours,
                        })
                        
                        current_day_duty += self.fuel_duration_hours
                        hours_since_break += self.fuel_duration_hours
                        cycle_hours_used += self.fuel_duration_hours
                        daily_duty_hours[0] += self.fuel_duration_hours  # Update today's hours
                        distance_since_fuel = 0  # Reset the distance counter
                    except Exception as e:
                        # If there's any error, use a simpler approach
                        schedule.append({
                            'activity_type': 'FUEL',
                            'location_index': i,
                            'duration_hours': self.fuel_duration_hours,
                            'coord': current_location,
                            'day': current_day,
                            'start_duty_hours': current_day_duty,
                            'end_duty_hours': current_day_duty + self.fuel_duration_hours,
                        })
                        
                        current_day_duty += self.fuel_duration_hours
                        hours_since_break += self.fuel_duration_hours
                        cycle_hours_used += self.fuel_duration_hours
                        daily_duty_hours[0] += self.fuel_duration_hours  # Update today's hours
                        distance_since_fuel = 0  # Reset the distance counter
        
        # Add dropoff at the final location
        if route_segments:
            # For dropoff, use the final location from the last segment if available
            final_coords = []
            try:
                final_segment = route_segments[-1]
                final_coords = final_segment.get("geometry", {}).get("coordinates", [])
                if final_coords and len(final_coords) > 0:
                    current_location = final_coords[-1]  # Use the last coordinate of the last segment
            except (IndexError, AttributeError, TypeError):
                pass  # Keep current_location if we can't get final coordinates
                
            schedule.append({
                'activity_type': 'DROPOFF',
                'location_index': len(route_segments),
                'duration_hours': self.dropoff_duration_hours,
                'day': current_day,
                'start_duty_hours': current_day_duty,
                'end_duty_hours': current_day_duty + self.dropoff_duration_hours,
                'coord': current_location  # Add coordinates to dropoff activity
            })
        
        return schedule
    
    def generate_eld_logs(self, schedule):
        """
        Generate ELD log data from the schedule
        
        Returns:
            List of daily logs containing on-duty, driving, and off-duty periods
        """
        # Group schedule items by day
        days_schedule = {}
        for item in schedule:
            day = item['day']
            if day not in days_schedule:
                days_schedule[day] = []
            days_schedule[day].append(item)
        
        # Generate logs for each day
        logs = []
        for day, items in sorted(days_schedule.items()):
            daily_log = {
                'day': day,
                'date': f"Day {day}",
                'activities': []
            }
            
            # For each activity, create log entry
            for item in sorted(items, key=lambda x: x['start_duty_hours']):
                activity_type = item['activity_type']
                
                if activity_type == 'DRIVING':
                    status = 'D'  # Driving
                elif activity_type in ['PICKUP', 'DROPOFF', 'FUEL']:
                    status = 'ON'  # On-duty, not driving
                elif activity_type == 'BREAK':
                    status = 'OFF'  # Off-duty
                elif activity_type in ['REST', 'RESTART']:
                    status = 'SB'  # Sleeper berth
                else:
                    status = 'OFF'
                
                start_hour = item['start_duty_hours']
                if activity_type in ['REST', 'RESTART']:
                    # Rest spans to the next day
                    end_hour = 24
                else:
                    end_hour = item['end_duty_hours']
                
                log_entry = {
                    'status': status,
                    'start_hour': start_hour,
                    'end_hour': end_hour,
                    'activity_type': activity_type,
                    'location_index': item.get('location_index')
                }
                
                # Add coordinates to the log entry if available
                if 'coord' in item:
                    log_entry['coord'] = item['coord']
                
                # Add cycle hours remaining if available
                if 'cycle_hours_remaining' in item:
                    log_entry['cycle_hours_remaining'] = item['cycle_hours_remaining']
                
                daily_log['activities'].append(log_entry)
            
            logs.append(daily_log)
        
        return logs