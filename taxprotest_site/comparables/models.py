from django.contrib.gis.db import models

class PropertyGeo(models.Model):
    acct = models.CharField(max_length=40, primary_key=True)
    latitude = models.FloatField(null=True, blank=True)
    longitude = models.FloatField(null=True, blank=True)
    geom = models.PointField(geography=True, null=True, blank=True)

    class Meta:
        db_table = 'property_geo'

class RealAcct(models.Model):
    acct = models.CharField(max_length=40, primary_key=True)
    site_addr_1 = models.CharField(max_length=255, null=True, blank=True)
    site_addr_3 = models.CharField(max_length=40, null=True, blank=True)

    class Meta:
        db_table = 'real_acct'
