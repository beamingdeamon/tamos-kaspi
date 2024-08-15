from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny
from rest_framework import permissions
from rest_framework.decorators import permission_classes
from django.http import HttpResponse
from rest_framework import status
from database.models import Logs, School


from django.conf import settings


API_KEY = getattr(settings, "API_KEY", None)


@permission_classes((permissions.AllowAny,))
class Kaspi(APIView):
    def get(self, request):
        api_key = request.headers['x-api-key']
        if(api_key != API_KEY):
            return Response("Forbiden", status=status.HTTP_403_FORBIDDEN)
        command = request.GET.get("command")
        account = request.GET.get("account")
        sum = request.GET.get("sum")
        txn_id = request.GET.get("txn_id")
        response = {
                "txn_id": "",
                "result": 0,
                "comment": "",
                "fields": {
                    "Номер договора": {
                        "value": ""
                    },
                    "BIN школы": {
                        "value": ""
                    },
                    "ФИО ребенка": {
                        "value": ""
                    },
                    "Класс/группа": {
                        "value": ""
                    },
                    "Вид оплаты": {
                        "value": ""
                    },
                    "Задолженность по договору": {
                        "value": 0
                    }
                }
            }

        if(command == "check"):
            trimmed_account = account[4:]

            constract_identifier = trimmed_account.split('-')[0]
            try:
                school = School.objects.get(school_identifier=constract_identifier)
            except School.DoesNotExist:
                response['result'] = 1
                return Response(response)
            response['fields']['Номер договора']['value'] = account
            response['fields']['BIN школы']['value'] = school.school_bin
            return Response(response)
        elif(command == "pay"):
            return Response("pay")
        else:
            return Response("Bad Request", status=status.HTTP_400_BAD_REQUEST)
        
