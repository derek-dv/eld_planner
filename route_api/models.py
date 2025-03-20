from django.db import models

class Location(models.Model):
    name = models.CharField(max_length=255)
    latitude = models.FloatField()
    longitude = models.FloatField()
    
    def __str__(self):
        return self.name

class RouteSegment(models.Model):
    start_location = models.ForeignKey(Location, on_delete=models.CASCADE, related_name='starting_segments')
    end_location = models.ForeignKey(Location, on_delete=models.CASCADE, related_name='ending_segments')
    distance_miles = models.FloatField()
    estimated_duration_hours = models.FloatField()
    
    def __str__(self):
        return f"{self.start_location} to {self.end_location}"

class RestStop(models.Model):
    STOP_TYPES = (
        ('REST', '10-Hour Rest'),
        ('BREAK', '30-Minute Break'),
        ('FUEL', 'Fuel Stop'),
        ('PICKUP', 'Pickup'),
        ('DROPOFF', 'Dropoff'),
    )
    
    location = models.ForeignKey(Location, on_delete=models.CASCADE)
    stop_type = models.CharField(max_length=10, choices=STOP_TYPES)
    duration_hours = models.FloatField()
    
    def __str__(self):
        return f"{self.get_stop_type_display()} at {self.location}"

class Route(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    starting_location = models.ForeignKey(Location, on_delete=models.CASCADE, related_name='routes_starting')
    pickup_location = models.ForeignKey(Location, on_delete=models.CASCADE, related_name='routes_pickup')
    dropoff_location = models.ForeignKey(Location, on_delete=models.CASCADE, related_name='routes_dropoff')
    initial_hours_used = models.FloatField()
    total_distance = models.FloatField(null=True, blank=True)
    total_duration = models.FloatField(null=True, blank=True)
    segments = models.ManyToManyField(RouteSegment)
    rest_stops = models.ManyToManyField(RestStop)
    
    def __str__(self):
        return f"Route from {self.starting_location} to {self.dropoff_location}"