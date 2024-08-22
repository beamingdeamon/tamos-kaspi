from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny
from rest_framework import permissions
from rest_framework.decorators import permission_classes
from django.http import HttpResponse
from rest_framework import status
from database.models import Logs, School
from django.db import connections

import datetime



from django.conf import settings


API_KEY = getattr(settings, "API_KEY", None)

def fromCursorToJSON(cursor):
    columns = [col[0] for col in cursor.description]
    return [dict(zip(columns, row)) for row in cursor.fetchall()]


def compareSum(sum, to_pay):
    if float(sum) != float(to_pay):
        return True
    else:
        return False

@permission_classes((permissions.AllowAny,))
class Kaspi(APIView):
    
    
    def get(self, request):
        api_key = request.headers['x-api-key']
        if(api_key != API_KEY):
            return Response("Forbiden", status=status.HTTP_403_FORBIDDEN)
        command = request.GET.get("command")
        account = request.GET.get("account")

        if(command == "check"):
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

            trimmed_account = account[4:]

            contract_identifier = trimmed_account.split('-')[0]
            try:
                school = School.objects.get(school_identifier=contract_identifier)
            except School.DoesNotExist:
                response['result'] = 1
                response['comment'] = "Идентификатор договора не правильно введен"
                return Response(response)
            with connections["ms-sql"].cursor() as cursor:
                cursor.execute(f"SELECT id, full_name, ClassName, ContSum, Contribution, ContractSum FROM tamos_db.dbo.{school.ms_sql_table} WHERE ContractNum = '{account}'")
                contract = fromCursorToJSON(cursor)
                if len(contract) == 0:
                    response['result'] = 2
                    response['comment'] = "Договор не найден"
                    return Response(response)
                if contract[0]['ClassName'] is None:
                    response['result'] = 4
                    response['comment'] = "Договор истек"
                    return Response(response)
                response['fields']['ФИО ребенка']['value'] = contract[0]['full_name']
                response['fields']['Класс/группа']['value'] = contract[0]['ClassName']
                response['fields']['Номер договора']['value'] = account
                response['fields']['BIN школы']['value'] = school.school_bin
                if contract[0]['Contribution']:
                    cursor.execute(f"SELECT id, amount FROM tamos_db.dbo.{school.ms_sql_transactions_table} WHERE agreement_id = {contract[0]['id']} and contribution = 1")
                    contr_trans = fromCursorToJSON(cursor)
                    if len(contr_trans) == 0:
                        response['fields']['Вид оплаты']['value'] = 'Вступительный взнос'
                        response['fields']['Задолженность по договору']['value'] = contract[0]['ContSum']
                        return Response(response)
                cursor.execute(f"SELECT c.ContractSum - SUM(t.amount) as to_pay FROM tamos_db.dbo.{school.ms_sql_table} c JOIN tamos_db.dbo.{school.ms_sql_transactions_table} t on c.id = t.agreement_id WHERE c.id = {contract[0]['id']} GROUP BY c.ContractSum")
                to_pay = fromCursorToJSON(cursor)

                if len(to_pay) == 0:
                    response['fields']['Вид оплаты']['value'] = 'Оплата по договору'
                    response['fields']['Задолженность по договору']['value'] = contract[0]['ContractSum']
                    return Response(response)
                
                response['fields']['Вид оплаты']['value'] = 'Оплата по договору'
                response['fields']['Задолженность по договору']['value'] = to_pay[0]['to_pay']
                return Response(response)
        elif(command == "pay"):
            response = {
                "txn_id": request.GET.get("txn_id"),
                "prv_txn_id" : "",
                "result": 0,
                "comment": ""
            }
            sum = request.GET.get("sum")
            txn_id = request.GET.get("txn_id")
            to_pay_contract = 0
            now = datetime.datetime.now()
            trimmed_account = account[4:]

            contract_identifier = trimmed_account.split('-')[0]
            try:
                school = School.objects.get(school_identifier=contract_identifier)
            except School.DoesNotExist:
                response['result'] = 1
                response['comment'] = "Идентификатор договора не правильно введен"
                return Response(response)
            
            with connections["ms-sql"].cursor() as cursor:
                cursor.execute(f"SELECT id, ContSum, ClassName, Contribution, ContractSum, PaymentTypeID FROM tamos_db.dbo.{school.ms_sql_table} WHERE ContractNum = '{account}'")
                contract = fromCursorToJSON(cursor)

                #Проверки на контракт
                if len(contract) == 0:
                    response['result'] = 2
                    response['comment'] = "Договор не найден"
                    return Response(response)
                if contract[0]['ClassName'] is None:
                    response['result'] = 4
                    response['comment'] = "Договор истек"
                    return Response(response)
                
                # Проверки на вступительный взнос
                if contract[0]['Contribution']:
                    cursor.execute(f"SELECT id, amount FROM tamos_db.dbo.{school.ms_sql_transactions_table} WHERE agreement_id = {contract[0]['id']} and contribution = 1")
                    contr_trans = fromCursorToJSON(cursor)
                    if len(contr_trans) == 0:
                        to_pay_contract = contract[0]['ContSum']
                        if compareSum(sum, to_pay_contract):
                            response['result'] = 5
                            response['comment'] = "Не правильная сумма к оплате"
                            return Response(response)
                        cursor.execute(f'''INSERT INTO tamos_db.dbo.{school.ms_sql_transactions_table} 
                                       (amount, description, is_increase,payment_type,agreement_id,contribution,bank_id,trans_date)
                                        values 
                                       ({sum},'kaspi_transaction',1,{contract[0]['PaymentTypeID']},{contract[0]['id']},1,29817,'{now.strftime("%Y-%m-%d %H:%M:%S")}')''')
                        cursor.execute(f"SELECT id, amount, trans_date FROM tamos_db.dbo.{school.ms_sql_transactions_table} WHERE agreement_id = {contract[0]['id']} and contribution = 1 order by trans_date desc")
                        new_trans = fromCursorToJSON(cursor)[0]
                        if new_trans['trans_date'].strftime("%Y-%m-%dT%H:%M:%S") == now.strftime("%Y-%m-%dT%H:%M:%S"):
                            response['prv_txn_id'] = str(new_trans['id'])
                            response['comment'] = "OK"
                            cursor.execute(f'''INSERT INTO tamos_db.dbo.kaspi_transactions 
                                       (clazz, contract_id, transaction_id,txn_id,date,sum)
                                        values 
                                       ('{school.clazz_name}',{contract[0]['id']},{new_trans['id']},{txn_id},'{now.strftime("%Y-%m-%d %H:%M:%S")}',{sum})''')
                            return Response(response)
                        else:
                            response['result'] = 6
                            response['comment'] = "Транзакция не создалась"

                cursor.execute(f"SELECT c.ContractSum - SUM(t.amount) as to_pay FROM tamos_db.dbo.{school.ms_sql_table} c JOIN tamos_db.dbo.{school.ms_sql_transactions_table} t on c.id = t.agreement_id WHERE c.id = {contract[0]['id']} GROUP BY c.ContractSum")
                to_pay = fromCursorToJSON(cursor)

                if len(to_pay) == 0:
                    to_pay_contract = contract[0]['ContractSum']
                    if compareSum(sum, to_pay_contract):
                        response['result'] = 5
                        response['comment'] = "Не правильная сумма к оплате"
                        return Response(response)
                    cursor.execute(f'''INSERT INTO tamos_db.dbo.{school.ms_sql_transactions_table} 
                                    (amount, description, is_increase,payment_type,agreement_id,contribution,bank_id,trans_date)
                                    values 
                                    ({sum},'kaspi_transaction',1,{contract[0]['PaymentTypeID']},{contract[0]['id']},0,29817,'{now.strftime("%Y-%m-%d %H:%M:%S")}')''')
                    cursor.execute(f"SELECT id, amount, trans_date FROM tamos_db.dbo.{school.ms_sql_transactions_table} WHERE agreement_id = {contract[0]['id']} and contribution = 0 order by trans_date desc")
                    new_trans = fromCursorToJSON(cursor)[0]
                    if new_trans['trans_date'].strftime("%Y-%m-%dT%H:%M:%S") == now.strftime("%Y-%m-%dT%H:%M:%S"):
                        response['prv_txn_id'] = str(new_trans['id'])
                        response['comment'] = "OK"
                        cursor.execute(f'''INSERT INTO tamos_db.dbo.kaspi_transactions 
                                    (clazz, contract_id, transaction_id,txn_id,date,sum)
                                    values 
                                    ('{school.clazz_name}',{contract[0]['id']},{new_trans['id']},{txn_id},'{now.strftime("%Y-%m-%d %H:%M:%S")}',{sum})''')
                        return Response(response)
                    else:
                        response['result'] = 6
                        response['comment'] = "Транзакция не создалась"
                
                to_pay_contract = to_pay[0]['to_pay']
                if compareSum(sum, to_pay_contract):
                    response['result'] = 5
                    response['comment'] = "Не правильная сумма к оплате"
                    return Response(response)
                cursor.execute(f'''INSERT INTO tamos_db.dbo.{school.ms_sql_transactions_table} 
                                (amount, description, is_increase,payment_type,agreement_id,contribution,bank_id,trans_date)
                                values 
                                ({sum},'kaspi_transaction',1,{contract[0]['PaymentTypeID']},{contract[0]['id']},0,29817,'{now.strftime("%Y-%m-%d %H:%M:%S")}')''')
                cursor.execute(f"SELECT id, amount, trans_date FROM tamos_db.dbo.{school.ms_sql_transactions_table} WHERE agreement_id = {contract[0]['id']} and contribution = 0 order by trans_date desc")
                new_trans = fromCursorToJSON(cursor)[0]
                if new_trans['trans_date'].strftime("%Y-%m-%dT%H:%M:%S") == now.strftime("%Y-%m-%dT%H:%M:%S"):
                    response['prv_txn_id'] = str(new_trans['id'])
                    response['comment'] = "OK"
                    cursor.execute(f'''INSERT INTO tamos_db.dbo.kaspi_transactions 
                                (clazz, contract_id, transaction_id,txn_id,date,sum)
                                values 
                                ('{school.clazz_name}',{contract[0]['id']},{new_trans['id']},{txn_id},'{now.strftime("%Y-%m-%d %H:%M:%S")}',{sum})''')
                    return Response(response)
                else:
                    response['result'] = 6
                    response['comment'] = "Транзакция не создалась"
            return Response("pay")
        else:
            return Response("Bad Request", status=status.HTTP_400_BAD_REQUEST)
        
