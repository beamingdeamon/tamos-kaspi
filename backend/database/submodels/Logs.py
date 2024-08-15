from django.db import models

class Logs(models.Model):
    contract_id = models.CharField(max_length=1000)
    school_bin = models.CharField(max_length=1000)
    sum = models.CharField(max_length=1000)
    txn_id = models.CharField(max_length=1000)