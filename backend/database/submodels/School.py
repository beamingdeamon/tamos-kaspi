from django.db import models

class School(models.Model):
    school_identifier = models.CharField(max_length=1000)
    school_bin = models.CharField(max_length=1000)