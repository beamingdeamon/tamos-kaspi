from django.db import models

class School(models.Model):
    school_identifier = models.CharField(max_length=1000)
    school_bin = models.CharField(max_length=1000)
    ms_sql_table = models.CharField(max_length=1000, null=True)
    ms_sql_transactions_table = models.CharField(max_length=1000, null=True)
    clazz_name = models.CharField(max_length=1000, null=True)