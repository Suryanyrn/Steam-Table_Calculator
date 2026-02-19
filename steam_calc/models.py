# steam_calc/models.py
from django.db import models

class SteamQueryLog(models.Model):
    pressure = models.FloatField(help_text="Pressure in bar")
    temperature = models.FloatField(help_text="Temperature in °C")
    timestamp = models.DateTimeField(auto_now_add=True)
    is_valid = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.pressure} bar, {self.temperature}°C - Valid: {self.is_valid}"